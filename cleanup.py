from datetime import datetime, timedelta
from database import get_chat_user_week_messages, get_chat_join_date

def previous_week_period(now=None):
    now = now or datetime.now()
    current_sunday = (now - timedelta(days=(now.weekday() + 1) % 7)).date()
    end_date = current_sunday
    start_date = current_sunday - timedelta(days=6)
    return start_date.isoformat(), end_date.isoformat()

def run_manual_cleanup(vk, peer_id, min_messages, creator_id, get_admin_level):
    start_date, end_date = previous_week_period()
    
    # Получаем список участников (включая удаленные)
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id).get("items", [])
    except Exception as exc:
        return f"Ошибка получения участников: {exc}"

    checked = kept = removed = 0
    for member in members:
        uid = member.get("member_id")
        if not uid or uid < 0:
            continue
            
        # Пропускаем удаленные аккаунты (если бот может определить)
        if member.get("join_date") is None and uid > 0:
             # В VK API join_date может отсутствовать, это не значит, что аккаунт удален,
             # но если профиль не грузится, мы его пропускаем.
             pass

        checked += 1
        if uid == creator_id or get_admin_level(uid, peer_id) >= 1:
            kept += 1
            continue

        # Проверка: если человек зашел на этой неделе (в период чистки или позже) - не кикаем
        join_date = get_chat_join_date(peer_id, uid)
        if join_date:
            try:
                jd = datetime.strptime(join_date[:10], "%Y-%m-%d").date()
                # Если дата вступления >= дата начала чистки, пропускаем
                if jd >= datetime.strptime(start_date, "%Y-%m-%d").date():
                    kept += 1
                    continue
            except Exception:
                pass

        # Считаем сообщения
        count = get_chat_user_week_messages(peer_id, uid, start_date, end_date)
        if count >= min_messages: 
            kept += 1
            continue
            
        # Кикаем
        try:
            vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=uid)
            removed += 1
        except Exception:
            pass
            
    return f"Чистка завершена. Проверено: {checked}, Оставлено: {kept}, Кикнуто: {removed}."