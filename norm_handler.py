from datetime import datetime, timedelta
from database import (
    get_messages_stats, create_norm_report, add_norm_photo, 
    get_admin_tags_stats, db_cursor, get_admin_level_for_chat, get_all_global_roles, get_admins_for_chat
)
from admin_commands import get_display_admin_level, ROLE_NAMES
from config import CONTROL_CHAT

DIVIDER = '⋅⋆✦──── ⋆⋅☆⋅⋆ ────✦⋆⋅'

def _get_week_start():
    now = datetime.now()
    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0).strftime("%Y-%m-%d")

def generate_and_send_report(user_id, vk, photos):
    from relationships import get_display_name
    from keyboards import norm_review_keyboard
    import json
    
    # 1. Данные пользователя
    try:
        info = vk.users.get(user_ids=user_id)[0]
        name = f"{info.get('first_name','')} {info.get('last_name','')}".strip()
    except Exception:
        name = get_display_name(user_id) or f'Пользователь'
    user_link = f'[id{user_id}|{name}]'
    
    # 2. Права и беседы
    level = get_display_admin_level(user_id)
    role_name = ROLE_NAMES.get(level, 'Участник')
    
    # Получаем беседы, где у него есть права
    with db_cursor() as (_, c):
        rows = c.execute("SELECT peer_id FROM admin_chat_rights WHERE user_id=? AND level > 0", (user_id,)).fetchall()
    
    chats = []
    for (pid,) in rows:
        try:
            data = vk.messages.getConversationsById(peer_ids=pid).get('items', [])
            title = data[0].get('chat_settings', {}).get('title', str(pid)) if data else str(pid)
            chats.append(title)
        except:
            chats.append(str(pid))
            
    chats_str = ', '.join(chats) if chats else 'Нет'
    
    # 3. Статистика
    week_start_str = _get_week_start()
    
    # Сообщения (суммарно за неделю)
    msg_stats = get_messages_stats(user_id)
    week_msgs = msg_stats.get('week', 0)
    
    # Приглашения за неделю
    with db_cursor() as (_, c):
        inv_row = c.execute("SELECT COUNT(*) FROM chat_members WHERE invited_by=? AND substr(first_join_at,1,10)>=?", (user_id, week_start_str)).fetchone()
        week_invites = inv_row[0] if inv_row else 0

    # Теги
    tags_stats = get_admin_tags_stats(user_id, week_start_str)
    
    # 4. Формируем текст (БЕЗ ЗВЕЗДОЧЕК)
    lines = [
        f'Отчёт от {user_link}',
        f'Права: {role_name}',
        f'Беседы: {chats_str}',
        DIVIDER,
        f'Активность администратора\nЗа неделю: {week_msgs}',
        DIVIDER,
        f'Количество сделанных all\nЗа неделю: {tags_stats.get("all", 0)}',
        DIVIDER,
        f'Количество сделанных online\nЗа неделю: {tags_stats.get("online", 0)}',
        DIVIDER,
        f'Количество добавленных человек\nЗа неделю: {week_invites}',
        DIVIDER,
    ]
    
    text = '\n'.join(lines)
    
    # 5. Создаем запись в БД
    report_id = create_norm_report(user_id, text)
    for photo in photos:
        add_norm_photo(report_id, photo)
        
    # 6. Кому отправлять на проверку
    reviewers = set()
    for (pid,) in rows:
        try:
            admins = get_admins_for_chat(pid)
            for auid, alvl in admins:
                if alvl >= 5:
                    reviewers.add(auid)
        except: pass
        
    try:
        for guid, glvl in get_all_global_roles():
            if glvl >= 6:
                reviewers.add(guid)
    except: pass
    
    reviewers_links = []
    for rid in reviewers:
        try:
            u_info = vk.users.get(user_ids=rid)[0]
            rname = f"{u_info.get('first_name','')} {u_info.get('last_name','')}".strip()
            reviewers_links.append(f'[id{rid}|{rname}]')
        except:
            reviewers_links.append(f'[id{rid}|Куратор]')

    reviewers_text = ', '.join(reviewers_links) if reviewers_links else 'Нет кураторов'
    text += f'\n\nПроверяют: {reviewers_text}'
    
    # 7. Отправляем
    kb = norm_review_keyboard(report_id)
    args = {
        'peer_id': CONTROL_CHAT,
        'random_id': 0,
        'message': text,
        'keyboard': json.dumps(kb, ensure_ascii=False),
        'disable_mentions': True
    }
    
    if photos:
        args['attachment'] = ','.join(photos[:10])
        remaining = photos[10:]
    else:
        remaining = []
        
    try:
        vk.messages.send(**args)
        if remaining:
            vk.messages.send(peer_id=CONTROL_CHAT, random_id=0, message='Остальные фото:', attachment=','.join(remaining), disable_mentions=True)
    except Exception as e:
        print(f'Ошибка отправки отчета: {e}')

def check_norm_rights(reviewer_id, report_user_id):
    """Проверяет, имеет ли право ревьюер одобрять отчет."""
    from database import get_global_role
    
    g = int(get_global_role(reviewer_id) or 0)
    if g >= 6: return True
    
    with db_cursor() as (_, c):
        rows = c.execute("SELECT peer_id FROM admin_chat_rights WHERE user_id=? AND level > 0", (report_user_id,)).fetchall()
        
    for (pid,) in rows:
        if int(get_admin_level_for_chat(pid, reviewer_id) or 0) >= 5:
            return True
            
    return False