"""
Закрепы администрации: текст + обновление при смене ролей.
Логика и формат — как в старом pin_manager.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from bot.core import database as db
from bot.core.config import settings

logger = logging.getLogger(__name__)

DIVIDER = "⋅⋆✦──── ⋆⋅☆⋅⋆ ────✦⋆⋅"
INFO_HEADER = "⋅⋆✦──── ⋆⋅info⋅⋆ ────✦⋆⋅"
EXTRA_HEADER = "⋅⋆✦──── ⋆⋅Доп. Беседы⋅⋆ ────✦⋆⋅"


def _vk_name(vk: Any, uid: int) -> str:
    try:
        info = vk.users.get(user_ids=uid)[0]
        return (f"{info.get('first_name', '')} {info.get('last_name', '')}").strip() or "Пользователь"
    except Exception:
        return "Пользователь"


def _mention(vk: Any, uid: int) -> str:
    return f"[id{uid}|{_vk_name(vk, uid)}]"


def _chat_title(vk: Any, peer_id: int) -> str:
    try:
        result = vk.messages.getConversationsById(peer_ids=peer_id)
        items = result.get("items") or []
        if items:
            return (items[0].get("chat_settings") or {}).get("title") or ""
    except Exception as e:
        logger.warning("Не удалось получить название беседы %s: %s", peer_id, e)
    return ""


def _header_line(title: str) -> str:
    title = (title or "").strip()
    if not title:
        return "🌙 NightFall 🌙"
    match = re.match(r"^(.*?)(\d+)\s*$", title)
    if match:
        return f"🌙 {match.group(1).strip()} {match.group(2)} 🌙"
    return f"🌙 {title} 🌙"


def _global_roles_list() -> list[tuple[int, int]]:
    """[(user_id, level), ...]"""
    out = []
    try:
        for row in db.get_all_global_roles():
            out.append((int(row["user_id"]), int(row["level"])))
    except Exception as e:
        logger.warning("%s", e)
    return out


def _chat_admins(peer_id: int) -> list[tuple[int, int]]:
    out = []
    try:
        for row in db.get_admins_for_chat(peer_id):
            out.append((int(row["user_id"]), int(row["level"])))
    except Exception as e:
        logger.warning("%s", e)
    return out


def build_pin_text(vk: Any, peer_id: int) -> str:
    title = _chat_title(vk, peer_id)
    is_extra = peer_id in settings.extra_chats
    is_citadel = peer_id == settings.citadel_chat

    roles: dict[int, list[int]] = {1: [], 2: [], 3: [], 4: [], 5: [], 6: [], 7: []}
    seen: set[int] = set()

    for uid, level in _global_roles_list():
        if uid in seen:
            continue
        if level in (6, 7):
            roles[level].append(uid)
            seen.add(uid)

    if settings.creator_id not in seen:
        roles[7].append(settings.creator_id)
        seen.add(settings.creator_id)

    for uid, level in _chat_admins(peer_id):
        if uid in seen:
            continue
        if level in (1, 2, 3, 4, 5):
            roles[level].append(uid)
            seen.add(uid)

    lines = [_header_line(title), ""]
    lines.append(INFO_HEADER)
    lines.append("")
    lines.append("— 📄Правила проекта")
    lines.append(f"[{settings.pin_rules_link}|Ознакомиться с правилами]")
    lines.append("— 📄Меню проекта:")
    lines.append("[https://vk.ru/topic-241462477_69686220|Перейти в меню]")
    lines.append("— 📄Сообщество проекта:")
    lines.append(f"[{settings.pin_community_link}|Перейти в сообщество]")

    if not is_citadel:
        lines.append("— 📄Заявки на пост администрации:")
        lines.append("«лл заявка» в ЛС бота.")

    lines.append("")
    lines.append(DIVIDER)
    lines.append("")

    for level, emoji, label in (
        (7, "👑", "Лелуш ви Британия"),
        (6, "⚖", "Вершитель правосудия"),
    ):
        lines.append(f"➤ {emoji} {label}:")
        if roles[level]:
            for uid in roles[level]:
                lines.append(f"- {_mention(vk, uid)}")
        else:
            lines.append("absent")
        lines.extend(["", DIVIDER, ""])

    if is_citadel:
        lines.append("➤ 🌟 Кураторы:")
        lines.append("")
        chat_list = []
        for i, mc in enumerate(settings.main_chats, 1):
            chat_list.append((f"NightFall {i}", mc))
        chat_list.append(("NF || Anarchy", settings.anarchy_chat))
        chat_list.append(("NF || Casino", settings.casino_chat))
        for name, c_peer in chat_list:
            curator_id = None
            for uid, lvl in _chat_admins(c_peer):
                if lvl == 5:
                    curator_id = uid
                    break
            if curator_id:
                lines.append(f"{name} — {_mention(vk, curator_id)}")
            else:
                lines.append(f"{name} — absent")
        lines.append("")
        lines.append(DIVIDER)

    elif is_extra:
        lines.append("➤ 🌟 Куратор:")
        if roles[5]:
            for uid in roles[5]:
                lines.append(f"- {_mention(vk, uid)}")
        else:
            lines.append("absent")
        lines.extend(["", DIVIDER])

    else:
        for level, emoji, label in (
            (5, "🌟", "Куратор"),
            (4, "📱", "Администратор"),
            (3, "🎯", "Рекрутеры"),
            (2, "⚡", "Активисты"),
            (1, "🎓", "Стажёры"),
        ):
            lines.append(f"➤ {emoji} {label}:")
            if roles[level]:
                for uid in roles[level]:
                    lines.append(f"- {_mention(vk, uid)}")
            else:
                lines.append("absent")
            lines.append("")

        lines.append(EXTRA_HEADER)
        lines.append("")
        lines.append("📌NF || Casino:")
        lines.append(settings.pin_casino_link)
        lines.append("📌NF || Anarchy:")
        lines.append(settings.pin_anarchy_link)

    return "\n".join(lines)


def get_real_pinned_message(vk: Any, peer_id: int) -> Optional[dict]:
    try:
        result = vk.messages.getConversationsById(peer_ids=peer_id)
        items = result.get("items") or []
        if not items:
            return None
        pinned = (items[0].get("chat_settings") or {}).get("pinned_message")
        if not pinned:
            return None
        return {
            "message_id": pinned.get("id"),
            "conversation_message_id": pinned.get("conversation_message_id"),
            "from_id": pinned.get("from_id"),
            "text": pinned.get("text", ""),
        }
    except Exception as e:
        logger.warning("Ошибка получения закрепа %s: %s", peer_id, e)
        return None


def edit_pin(vk: Any, peer_id: int, text: str, pin_dict: dict) -> bool:
    cmid = pin_dict.get("conversation_message_id")
    mid = pin_dict.get("message_id")
    try:
        if cmid:
            vk.messages.edit(
                peer_id=peer_id,
                conversation_message_id=int(cmid),
                message=text,
                disable_mentions=0,
            )
            db.set_chat_pin(peer_id, int(cmid), int(mid) if mid else None)
            return True
        if mid:
            vk.messages.edit(
                peer_id=peer_id,
                message_id=int(mid),
                message=text,
                disable_mentions=0,
            )
            db.set_chat_pin(peer_id, None, int(mid))
            return True
    except Exception as e:
        logger.warning("edit_pin %s: %s", peer_id, e)
    return False


def send_new_pin(vk: Any, peer_id: int, text: str) -> tuple[Optional[int], Optional[int]]:
    try:
        mid = vk.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=text,
            disable_mentions=0,
        )
        # try pin
        try:
            vk.messages.pin(peer_id=peer_id, message_id=mid)
        except Exception as e:
            logger.warning("pin message %s: %s", peer_id, e)
        pinned = get_real_pinned_message(vk, peer_id)
        cmid = pinned.get("conversation_message_id") if pinned else None
        db.set_chat_pin(peer_id, cmid, mid)
        return mid, cmid
    except Exception as e:
        logger.warning("send_new_pin %s: %s", peer_id, e)
        return None, None


def refresh_pin_if_exists(vk: Any, peer_id: int) -> tuple[bool, str]:
    pinned = get_real_pinned_message(vk, peer_id)
    if not pinned:
        # try from DB
        row = db.get_chat_pin(peer_id)
        if not row or (not row["conversation_message_id"] and not row["message_id"]):
            return False, "no_pin"
        pin_dict = {
            "conversation_message_id": row["conversation_message_id"],
            "message_id": row["message_id"],
        }
        text = build_pin_text(vk, peer_id)
        if edit_pin(vk, peer_id, text, pin_dict):
            return True, "updated"
        return False, "edit_error"

    text = build_pin_text(vk, peer_id)
    pin_dict = {
        "conversation_message_id": pinned.get("conversation_message_id"),
        "message_id": pinned.get("message_id"),
    }
    if edit_pin(vk, peer_id, text, pin_dict):
        return True, "updated"
    return False, "edit_error"


def update_pin_in_chat(vk: Any, peer_id: int) -> tuple[bool, str]:
    ok, reason = refresh_pin_if_exists(vk, peer_id)
    if ok:
        return ok, reason
    if reason == "no_pin":
        text = build_pin_text(vk, peer_id)
        mid, cmid = send_new_pin(vk, peer_id, text)
        if mid:
            return True, "created"
        return False, "error"
    return ok, reason


def update_all_pins(vk: Any) -> list[tuple[int, str]]:
    results = []
    peers = list(settings.main_chats) + list(settings.extra_chats) + [settings.citadel_chat]
    # plus any from DB
    try:
        for p in db.get_all_chats():
            if p not in peers and p != settings.applications_peer_id:
                peers.append(p)
    except Exception:
        pass

    for peer_id in peers:
        if peer_id == settings.applications_peer_id:
            continue
        try:
            _, reason = refresh_pin_if_exists(vk, peer_id)
            results.append((peer_id, reason))
            logger.info("Pin %s: %s", peer_id, reason)
        except Exception as e:
            logger.exception("Pin update %s: %s", peer_id, e)
            results.append((peer_id, "error"))
    return results


def refresh_after_admin_change(vk: Any, peer_id: int | None = None, global_change: bool = False):
    """Вызывать после выдачи/снятия прав."""
    if global_change:
        logger.info("Глобальная смена ролей — обновляю все закрепы")
        return update_all_pins(vk)
    if peer_id is None:
        return False, "no_peer"
    logger.info("Смена ролей в %s — обновляю закреп", peer_id)
    return update_pin_in_chat(vk, peer_id)
