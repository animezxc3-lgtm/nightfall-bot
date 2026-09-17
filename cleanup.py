"""Weekly VK conversation cleanup.

Every Sunday at 21:00 Moscow time, chats with cleanup enabled are checked.
A member needs at least 50 messages during the finished weekly period to stay.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from database import get_all_chats, get_chat_user_week_messages, get_db

CLEANUP_THRESHOLD = 50
MOSCOW = ZoneInfo("Europe/Moscow")


def previous_week_period(now=None):
    now = now or datetime.now(MOSCOW)
    # The finished period is Monday 00:00 through Sunday 20:59:59.
    current_sunday = (now - timedelta(days=(now.weekday() + 1) % 7)).date()
    end_date = current_sunday
    start_date = current_sunday - timedelta(days=6)
    return start_date.isoformat(), end_date.isoformat()


def run_cleanup(vk, creator_id, get_admin_level):
    start_date, end_date = previous_week_period()
    results=[]
    for peer_id, enabled in get_all_chats():
        if not enabled:
            continue
        try:
            members = vk.messages.getConversationMembers(peer_id=peer_id).get("items", [])
        except Exception as exc:
            results.append((peer_id, 0, 0, f"Ошибка получения участников: {exc}"))
            continue
        checked=kept=removed=0
        for member in members:
            uid=member.get("member_id")
            if not uid or uid < 0:
                continue
            checked += 1
            if uid == creator_id or get_admin_level(uid, peer_id) >= 1:
                kept += 1
                continue
            count=get_chat_user_week_messages(peer_id, uid, start_date, end_date)
            if count >= CLEANUP_THRESHOLD:
                kept += 1
                continue
            try:
                vk.messages.removeChatUser(chat_id=peer_id-2000000000, user_id=uid)
                removed += 1
            except Exception:
                pass
        results.append((peer_id, checked, kept, removed))
    return results
