import json
import logging
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll

from bot.core.config import settings
from bot.core.database import (
    migrate_database,
    ensure_chat,
    add_message_count,
    is_banned,
    user_exists,
    create_user,
    get_welcome_data,
    record_chat_join,
)
from bot.core.logging_setup import setup_logging
from bot.core.router import router
from bot.utils.vk_helpers import get_user_name, send_message, user_mention
import bot.handlers  # noqa: F401 — регистрация команд

logger = logging.getLogger("main")
_processed = set()
MAX_PROCESSED = 2000



def send_welcome(vk, peer_id: int, user_id: int) -> None:
    """Приветствие при входе в беседу."""
    try:
        info = vk.users.get(user_ids=user_id)[0]
        name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip() or "Участник"
    except Exception:
        name = "Участник"
    mention = user_mention(user_id, name)
    text, photo = get_welcome_data(peer_id)
    if not text:
        text = f"Добро пожаловать, {mention}!"
    else:
        text = (
            text.replace("{name}", name)
            .replace("{id}", str(user_id))
            .replace("{profile}", f"https://vk.com/id{user_id}")
        )
        text = re.sub(r"\(user\)", lambda _m: mention, text, flags=re.IGNORECASE)
    args = {"peer_id": peer_id, "random_id": 0, "message": text}
    if photo:
        args["attachment"] = photo
    try:
        vk.messages.send(**args)
    except Exception as e:
        logger.warning("Приветствие %s: %s", peer_id, e)


def main():
    setup_logging()
    migrate_database()
    logger.info("Бот запущен.")

    vk_session = vk_api.VkApi(token=settings.token)
    vk = vk_session.get_api()
    try:
        from bot.services.pin_service import update_all_pins
        update_all_pins(vk)
        logger.info("Закрепы синхронизированы.")
    except Exception as e:
        logger.warning("Ошибка синхронизации закрепов: %s", e)

    lp = VkBotLongPoll(vk_session, settings.group_id)

    for event in lp.listen():
        try:
            event_id = getattr(event, "event_id", None)
            if event_id is not None:
                if event_id in _processed:
                    continue
                _processed.add(event_id)
                if len(_processed) > MAX_PROCESSED:
                    _processed.clear()

            if event.type == VkBotEventType.MESSAGE_EVENT:
                obj = event.object
                payload = (
                    json.loads(obj.payload)
                    if isinstance(obj.payload, str)
                    else (obj.payload or {})
                )
                cmd = payload.get("cmd") if isinstance(payload, dict) else None
                if cmd:
                    try:
                        vk.messages.sendMessageEventAnswer(
                            event_id=obj.event_id,
                            user_id=obj.user_id,
                            peer_id=obj.peer_id,
                        )
                    except Exception:
                        pass
                    cmid = getattr(obj, "conversation_message_id", None)
                    router.dispatch_button(
                        cmd,
                        int(obj.user_id),
                        int(obj.peer_id),
                        vk,
                        payload,
                        conversation_message_id=int(cmid) if cmid else None,
                    )
                continue

            if event.type != VkBotEventType.MESSAGE_NEW:
                continue

            msg = event.object.message
            if not msg:
                continue

            action = msg.get("action") if isinstance(msg, dict) else getattr(msg, "action", None)
            if action:
                action_type = action.get("type") if isinstance(action, dict) else getattr(action, "type", None)
                member_id = (
                    action.get("member_id")
                    if isinstance(action, dict)
                    else getattr(action, "member_id", None)
                )
                peer = int(msg.get("peer_id") if isinstance(msg, dict) else msg.peer_id)
                from_id = int(msg.get("from_id") if isinstance(msg, dict) else msg.from_id)

                # --- Выход из беседы (самоисключение) ---
                if (
                    peer > 2_000_000_000
                    and action_type == "chat_kick_user"
                    and member_id
                    and int(member_id) == from_id
                ):
                    left_id = int(member_id)
                    # Админов и твинков не трогаем
                    is_admin = False
                    try:
                        from bot.services.admin_service import AdminService
                        is_admin = AdminService().is_admin(left_id, peer) or left_id == settings.creator_id
                    except Exception:
                        pass
                    is_tw = False
                    try:
                        is_tw = bool(db_is_twink(left_id)) if False else __import__("bot.core.database", fromlist=["is_twink"]).is_twink(left_id)
                    except Exception:
                        pass
                    if not is_admin and not is_tw:
                        try:
                            vk.messages.removeChatUser(chat_id=peer - 2000000000, user_id=left_id)
                        except Exception:
                            pass
                        try:
                            vk.messages.send(
                                peer_id=peer,
                                random_id=0,
                                message="Империи нужны воистину верные люди.",
                                disable_mentions=True,
                            )
                        except Exception:
                            pass
                    continue

                if action_type in ("chat_invite_user", "chat_invite_user_by_link"):
                    if member_id and int(member_id) > 0 and peer > 2_000_000_000:
                        uid = int(member_id)
                        if not user_exists(uid):
                            create_user(uid, get_user_name(vk, uid))
                        ensure_chat(peer)
                        record_chat_join(peer, uid, invited_by=from_id if from_id > 0 else None)
                        # Забаненных сразу кикаем
                        if is_banned(uid):
                            try:
                                vk.messages.removeChatUser(chat_id=peer - 2000000000, user_id=uid)
                                vk.messages.send(
                                    peer_id=peer,
                                    random_id=0,
                                    message="Забаненный пользователь был исключён.",
                                    disable_mentions=True,
                                )
                            except Exception:
                                pass
                        else:
                            send_welcome(vk, peer, uid)
                    continue

            uid = int(msg["from_id"] if isinstance(msg, dict) else msg.from_id)
            peer = int(msg["peer_id"] if isinstance(msg, dict) else msg.peer_id)
            text = (msg.get("text") if isinstance(msg, dict) else (msg.text or "") or "").strip()

            if uid <= 0 or is_banned(uid):
                continue

            if not user_exists(uid):
                create_user(uid, get_user_name(vk, uid))

            if peer > 2_000_000_000:
                ensure_chat(peer)
                add_message_count(uid, peer)

            # Сбор фото для отчёта по норме (только ЛС)
            try:
                from bot.handlers.norm_commands import try_collect_norm_photo
                if try_collect_norm_photo(uid, peer, msg, vk):
                    continue
            except Exception:
                logger.exception("norm photo collect")

            try:
                from bot.handlers.internship_commands import try_collect_isp_photo
                if try_collect_isp_photo(uid, peer, msg, vk):
                    continue
            except Exception:
                logger.exception("isp photo collect")

            # Ответы на заявку (ЛС, без префикса)
            if text and peer < 2_000_000_000:
                try:
                    from bot.handlers.application_commands import process_application_text
                    if process_application_text(vk, uid, peer, text):
                        continue
                except Exception:
                    logger.exception("application text")

            if text:
                router.dispatch_text(text, uid, peer, vk, event)

        except Exception:
            logger.exception("Ошибка в цикле")


if __name__ == "__main__":
    main()
