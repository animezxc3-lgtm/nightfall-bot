from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from database import get_all_chats, get_chat_user_week_messages

MOSCOW = ZoneInfo("Europe/Moscow")

def previous_week_period(now=None):
    now = now or datetime.now(MOSCOW)
    current_sunday = (now - timedelta(days=(now.weekday() + 1) % 7)).date()
    end_date = current_sunday
    start_date = current_sunday - timedelta(days=6)
    return start_date.isoformat(), end_date.isoformat()

def run_manual_cleanup(vk, peer_id, min_messages, creator_id, get_admin_level):
    """Запускает чистку в конкретной беседе с заданным порогом (строго меньше)."""
    start_date, end_date = previous_week_period()
    
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id).get("items", [])
    except Exception as exc:
        return f"Ошибка получения участников: {exc}"

    checked = kept = removed = 0
    for member in members:
        uid = member.get("member_id")
        if not uid or uid < 0:
            continue
        checked += 1
        if uid == creator_id or get_admin_level(uid, peer_id) >= 1:
            kept += 1
            continue
        count = get_chat_user_week_messages(peer_id, uid, start_date, end_date)
        if count >= min_messages: # Строго меньше порога - кик
            kept += 1
            continue
        try:
            vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=uid)
            removed += 1
        except Exception:
            pass
    return f"Чистка завершена. Проверено: {checked}, Оставлено: {kept}, Кикнуто: {removed}."