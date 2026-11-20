"""
Вспомогательные функции для работы с VK API.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


def send_message(
    vk: Any,
    peer_id: int,
    message: str,
    *,
    keyboard: Optional[dict] = None,
    attachment: Optional[str] = None,
    disable_mentions: bool = True,
    random_id: int = 0,
) -> Optional[int]:
    """Безопасная отправка сообщения. Возвращает message_id или None."""
    import json

    args: dict[str, Any] = {
        "peer_id": peer_id,
        "message": message,
        "random_id": random_id,
        "disable_mentions": disable_mentions,
    }
    if keyboard is not None:
        args["keyboard"] = json.dumps(keyboard, ensure_ascii=False, separators=(",", ":"))
    if attachment:
        args["attachment"] = attachment

    try:
        return vk.messages.send(**args)
    except Exception as exc:
        logger.warning("Не удалось отправить сообщение в %s: %s", peer_id, exc)
        return None


def edit_message(
    vk: Any,
    peer_id: int,
    conversation_message_id: int,
    message: str,
    *,
    keyboard: Optional[dict] = None,
    attachment: Optional[str] = None,
) -> bool:
    import json

    args: dict[str, Any] = {
        "peer_id": peer_id,
        "conversation_message_id": conversation_message_id,
        "message": message,
        "disable_mentions": True,
    }
    if keyboard is not None:
        args["keyboard"] = json.dumps(keyboard, ensure_ascii=False, separators=(",", ":"))
    if attachment:
        args["attachment"] = attachment

    try:
        vk.messages.edit(**args)
        return True
    except Exception as exc:
        logger.debug("Не удалось отредактировать сообщение: %s", exc)
        return False


def user_mention(user_id: int, name: str = "пользователь") -> str:
    return f"[id{user_id}|{name}]"


def parse_target_id(text: str) -> Optional[int]:
    """
    Извлекает user_id из упоминания, ссылки или простого числа.
    """
    if not text:
        return None
    text = text.strip()

    # [id123|Name]
    m = re.search(r"\[id(\d+)\|", text)
    if m:
        return int(m.group(1))

    # @id123 или id123
    m = re.search(r"(?:@)?id(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # Просто число
    m = re.fullmatch(r"(\d{3,15})", text)
    if m:
        return int(m.group(1))

    return None


def get_user_name(vk: Any, user_id: int, fallback: str = "Участник") -> str:
    try:
        info = vk.users.get(user_ids=user_id)[0]
        first = info.get("first_name", "")
        last = info.get("last_name", "")
        name = f"{first} {last}".strip()
        return name or fallback
    except Exception:
        return fallback
