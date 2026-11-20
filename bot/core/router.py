"""
Простой, но мощный роутер команд.

Использование:

    from bot.core.router import router

    @router.command("профиль", aliases=["profile", "я"])
    def cmd_profile(ctx: CommandContext) -> None:
        ...

    @router.command("баланс")
    def cmd_balance(ctx: CommandContext) -> None:
        ...
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CommandContext:
    """Контекст выполнения команды."""
    user_id: int
    peer_id: int
    text: str                    # полный текст сообщения
    command: str                 # распознанная команда (без префикса)
    args: str                    # всё, что после команды
    args_list: list[str]         # args.split()
    vk: Any                      # vk_api
    is_chat: bool
    event: Any = None            # сырой event (опционально)
    payload: dict = field(default_factory=dict)  # для кнопок


CommandHandler = Callable[[CommandContext], Any]


class Router:
    def __init__(self, prefixes: tuple[str, ...] = ("лл",)):
        self.prefixes = prefixes
        self._commands: dict[str, CommandHandler] = {}
        self._aliases: dict[str, str] = {}
        self._button_handlers: dict[str, CommandHandler] = {}

    # ------------------------------------------------------------------
    # Регистрация текстовых команд
    # ------------------------------------------------------------------

    def command(
        self,
        name: str,
        *,
        aliases: Optional[list[str]] = None,
        admin_level: int = 0,
        creator_only: bool = False,
    ) -> Callable[[CommandHandler], CommandHandler]:
        """
        Декоратор регистрации команды.

        admin_level — минимальный уровень админки (0 = все)
        creator_only — только создатель
        """
        def decorator(func: CommandHandler) -> CommandHandler:
            key = name.lower().strip()
            if key in self._commands:
                logger.warning("Команда %r перезаписана", key)
            self._commands[key] = func

            # Метаданные для middleware
            func._admin_level = admin_level  # type: ignore[attr-defined]
            func._creator_only = creator_only  # type: ignore[attr-defined]

            for alias in aliases or []:
                self._aliases[alias.lower().strip()] = key
            return func
        return decorator

    def button(self, cmd: str) -> Callable[[CommandHandler], CommandHandler]:
        """Регистрация обработчика callback-кнопки."""
        def decorator(func: CommandHandler) -> CommandHandler:
            self._button_handlers[cmd] = func
            return func
        return decorator

    # ------------------------------------------------------------------
    # Диспетчеризация
    # ------------------------------------------------------------------

    def extract_command(self, text: str) -> tuple[Optional[str], str]:
        """
        Возвращает (command, args) или (None, "") если это не команда.
        Поддерживает многословные команды (самый длинный матч).
        """
        if not text:
            return None, ""

        stripped = text.strip()
        lowered = stripped.lower()
        for prefix in self.prefixes:
            if lowered.startswith(prefix.lower()):
                rest = stripped[len(prefix):].strip()
                if not rest:
                    return None, ""
                rest_lower = rest.lower()
                # Собираем все возможные имена команд (основные + алиасы)
                candidates = list(self._commands.keys()) + list(self._aliases.keys())
                # Сортируем по длине убыв., чтобы сначала матчить длинные
                candidates.sort(key=len, reverse=True)
                for cand in candidates:
                    if rest_lower == cand or rest_lower.startswith(cand + " "):
                        args = rest[len(cand):].strip()
                        return cand, args
                # Fallback: первое слово
                parts = rest.split(maxsplit=1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                return cmd, args
        return None, ""

    def resolve(self, raw_command: str) -> Optional[CommandHandler]:
        cmd = raw_command.lower().strip()
        if cmd in self._commands:
            return self._commands[cmd]
        if cmd in self._aliases:
            return self._commands[self._aliases[cmd]]
        return None

    def dispatch_text(
        self,
        text: str,
        user_id: int,
        peer_id: int,
        vk: Any,
        event: Any = None,
    ) -> bool:
        """
        Пытается обработать сообщение как команду.
        Возвращает True, если команда была найдена и вызвана.
        """
        cmd_name, args = self.extract_command(text)
        if cmd_name is None:
            return False

        handler = self.resolve(cmd_name)
        if handler is None:
            return False

        # Проверка прав доступа
        admin_level = getattr(handler, "_admin_level", 0)
        creator_only = getattr(handler, "_creator_only", False)
        if admin_level > 0 or creator_only:
            from bot.services.admin_service import AdminService
            admin = AdminService()
            if creator_only and not admin.is_creator(user_id):
                try:
                    vk.messages.send(
                        peer_id=peer_id,
                        random_id=0,
                        message="⛔ Команда доступна только создателю.",
                        disable_mentions=True,
                    )
                except Exception:
                    pass
                return True
            if admin_level > 0 and not admin.is_admin(user_id, peer_id, min_level=admin_level):
                try:
                    vk.messages.send(
                        peer_id=peer_id,
                        random_id=0,
                        message="⛔ Недостаточно прав для этой команды.",
                        disable_mentions=True,
                    )
                except Exception:
                    pass
                return True

        ctx = CommandContext(
            user_id=user_id,
            peer_id=peer_id,
            text=text,
            command=cmd_name,
            args=args,
            args_list=args.split() if args else [],
            vk=vk,
            is_chat=peer_id > 2_000_000_000,
            event=event,
        )

        try:
            handler(ctx)
        except Exception:
            logger.exception(
                "Ошибка в команде %r (user=%s, peer=%s)",
                cmd_name, user_id, peer_id,
            )
            try:
                vk.messages.send(
                    peer_id=peer_id,
                    random_id=0,
                    message="⚠️ Произошла ошибка при выполнении команды. Администраторы уже уведомлены.",
                    disable_mentions=True,
                )
            except Exception:
                pass
        return True

    def dispatch_button(
        self,
        cmd: str,
        user_id: int,
        peer_id: int,
        vk: Any,
        payload: dict,
        conversation_message_id: int | None = None,
        event: Any = None,
    ) -> bool:
        handler = self._button_handlers.get(cmd)
        if handler is None:
            return False

        ctx = CommandContext(
            user_id=user_id,
            peer_id=peer_id,
            text="",
            command=cmd,
            args="",
            args_list=[],
            vk=vk,
            is_chat=peer_id > 2_000_000_000,
            event=event,
            payload=payload,
        )
        # Для удобства кладём conversation_message_id в payload
        if conversation_message_id is not None:
            ctx.payload["_conversation_message_id"] = conversation_message_id

        try:
            handler(ctx)
        except Exception:
            logger.exception(
                "Ошибка в кнопке %r (user=%s, peer=%s)",
                cmd, user_id, peer_id,
            )
        return True

    def list_commands(self) -> list[str]:
        return sorted(self._commands.keys())


# Глобальный роутер — префикс только «лл»
router = Router(prefixes=("лл",))
