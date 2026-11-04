"""Работа с закреплённым сообщением администрации."""

import re
import json
from config import (
    PIN_COMMUNITY_LINK, PIN_RULES_LINK, PIN_CASINO_LINK, PIN_ANARCHY_LINK,
    APPLICATIONS_PEER_ID, CREATOR_ID, GROUP_ID, MAIN_CHATS, EXTRA_CHATS, CITADEL_CHAT
)

from database import (
    get_all_global_roles, get_admins_for_chat, get_all_chats,
    get_chat_pin, set_chat_pin, reset_chat_pin_cmid, is_chat_hidden,
)

# Разделители
DIVIDER = '⋅⋆✦──── ⋆⋅☆⋅⋆ ────✦⋆⋅'
INFO_HEADER = '⋅⋆✦──── ⋆⋅info⋅⋆ ────✦⋆⋅'
EXTRA_HEADER = '⋅⋆✦──── ⋆⋅Доп. Беседы⋅⋆ ────✦⋆⋅'

def _vk_name(vk, uid):
    try:
        info = vk.users.get(user_ids=uid)[0]
        return (f"{info.get('first_name', '')} {info.get('last_name', '')}").strip() or 'Пользователь'
    except Exception: 
        return 'Пользователь'

def _mention(vk, uid): 
    # Возвращает кликабельную ссылку на профиль с именем
    return f'[id{uid}|{_vk_name(vk, uid)}]'

def _chat_title(vk, peer_id):
    try:
        result = vk.messages.getConversationsById(peer_ids=peer_id)
        items = result.get('items') or []
        if items:
            settings = items[0].get('chat_settings', {})
            return settings.get('title') or ''
    except Exception as e: 
        print(f'⚠️ Не удалось получить название беседы {peer_id}: {e}')
    return ''

def _header_line(title):
    title = (title or '').strip()
    if not title: 
        return '🌙 NightFall 🌙'
    match = re.match(r'^(.*?)(\d+)\s*$', title)
    if match: 
        return f'🌙 {match.group(1).strip()} {match.group(2)} 🌙'
    return f'🌙 {title} 🌙'

def build_pin_text(vk, peer_id):
    title = _chat_title(vk, peer_id)
    
    is_extra = peer_id in EXTRA_CHATS
    is_citadel = peer_id == CITADEL_CHAT
    
    # Собираем роли
    roles = {1: [], 2: [], 3: [], 4: [], 5: [], 6: [], 7: []}
    seen = set()

    try:
        for uid, level in get_all_global_roles():
            if uid in seen: continue
            if level in (6, 7):
                roles[level].append(uid)
                seen.add(uid)
    except Exception as e: print(f'⚠️ {e}')
        
    if CREATOR_ID not in seen:
        roles[7].append(CREATOR_ID)
        seen.add(CREATOR_ID)

    try:
        for uid, level in get_admins_for_chat(peer_id):
            if uid in seen: continue
            if level in (1, 2, 3, 4, 5):
                roles[level].append(uid)
                seen.add(uid)
    except Exception as e: print(f'⚠️ {e}')

    # Начинаем формировать текст
    lines = [_header_line(title), '']
    
    # Блок info
    lines.append(INFO_HEADER)
    lines.append('')
    lines.append('— 📄Правила проекта')
    lines.append(f'[{PIN_RULES_LINK}|Ознакомиться с правилами]')
    lines.append('— 📄Меню проекта:')
    lines.append('[https://vk.ru/topic-241462477_69686220|Перейти в меню]')
    lines.append('— 📄Сообщество проекта:')
    lines.append(f'[{PIN_COMMUNITY_LINK}|Перейти в сообщество]')
    
    # Если это НЕ Цитадель, добавляем заявки
    if not is_citadel:
        lines.append('— 📄Заявки на пост администрации:')
        lines.append('«лл заявка» в ЛС бота.')
        
    lines.append('')
    
    lines.append(DIVIDER)
    lines.append('')

    # Глобальные роли
    global_roles = [(7, '👑', 'Лелуш ви Британия'), (6, '⚖', 'Вершитель правосудия')]
    for level, emoji, label in global_roles:
        lines.append(f'➤ {emoji} {label}:')
        if roles[level]:
            for uid in roles[level]: 
                lines.append(f'- {_mention(vk, uid)}')
        else: 
            lines.append('absent')
        lines.extend(['', DIVIDER, ''])

    # СПЕЦИАЛЬНЫЙ БЛОК ДЛЯ ЦИТАДЕЛИ
    if is_citadel:
        lines.append('➤ 🌟 Кураторы:')
        lines.append('')
        
        chat_list = []
        for i, mc in enumerate(MAIN_CHATS, 1):
            chat_list.append((f'NightFall {i}', mc))
        chat_list.append(('NF || Anarchy', EXTRA_CHATS[0]))
        chat_list.append(('NF || Casino', EXTRA_CHATS[1]))
        
        for name, c_peer in chat_list:
            curator_id = None
            try:
                for uid, lvl in get_admins_for_chat(c_peer):
                    if lvl == 5:
                        curator_id = uid
                        break
            except Exception:
                pass
                
            if curator_id:
                lines.append(f'{name} — {_mention(vk, curator_id)}')
            else:
                lines.append(f'{name} — absent')
                
        lines.append('')
        lines.append(DIVIDER)
    
    # БЛОК ДЛЯ ДОП. БЕСЕД (Анархия/Казино)
    elif is_extra:
        lines.append('➤ 🌟 Куратор:')
        if roles[5]:
            for uid in roles[5]: 
                lines.append(f'- {_mention(vk, uid)}')
        else: 
            lines.append('absent')
        lines.extend(['', DIVIDER])
    
    # БЛОК ДЛЯ ОСНОВНЫХ БЕСЕД
    else:
        local_roles = [
            (5, '🌟', 'Куратор'),
            (4, '📱', 'Администратор'),
            (3, '🎯', 'Рекрутеры'),
            (2, '⚡', 'Активисты'),
            (1, '🎓', 'Стажёры'),
        ]
        for level, emoji, label in local_roles:
            lines.append(f'➤ {emoji} {label}:')
            if roles[level]:
                for uid in roles[level]: 
                    lines.append(f'- {_mention(vk, uid)}')
            else: 
                lines.append('absent')
            lines.append('')

        # Подвал для основных бесед
        lines.append(EXTRA_HEADER)
        lines.append('')
        lines.append('📌NF || Casino:')
        lines.append(PIN_CASINO_LINK)
        lines.append('📌NF || Anarchy:')
        lines.append(PIN_ANARCHY_LINK)

    return '\n'.join(lines)


# --- НИЖЕ ИДУТ ФУНКЦИИ ОТПРАВКИ, ИХ МЕНЯТЬ НЕ НУЖНО ---

def get_real_pinned_message(vk, peer_id):
    try:
        result = vk.messages.getConversationsById(peer_ids=peer_id)
        items = result.get('items') or []
        if not items: return None
        settings = items[0].get('chat_settings') or {}
        pinned = settings.get('pinned_message')
        if not pinned: return None
        return {
            'message_id': pinned.get('id'),
            'conversation_message_id': pinned.get('conversation_message_id'),
            'from_id': pinned.get('from_id'),
            'text': pinned.get('text', ''),
        }
    except Exception as e:
        print(f'❌ Ошибка получения закрепа беседы {peer_id}: {e}')
        return {'_error': True}

def remember_pinned_message(peer_id, pinned):
    if not pinned: return False
    message_id = pinned.get('message_id')
    cmid = pinned.get('conversation_message_id')
    if not message_id and not cmid: return False
    try:
        set_chat_pin(peer_id, conversation_message_id=cmid, message_id=message_id)
        return True
    except Exception as e: return False

def send_new_pin(vk, peer_id, text):
    try:
        result = vk.messages.send(peer_id=peer_id, random_id=0, message=text, disable_mentions=True)
    except Exception as e:
        print(f'Не удалось отправить закреп: {e}'); return None, None

    message_id = result if isinstance(result, int) else None
    cmid = None

    if message_id:
        try:
            info = vk.messages.getById(message_ids=message_id)
            items = info.get('items') or []
            if items: cmid = items[0].get('conversation_message_id')
        except Exception as e: print(f'getById: {e}')

    pinned_ok = False
    if cmid:
        try: vk.messages.pin(peer_id=peer_id, conversation_message_id=cmid); pinned_ok = True
        except Exception as e: print(f'⚠️ Не удалось закрепить: {e}')

    try: set_chat_pin(peer_id, conversation_message_id=cmid, message_id=message_id)
    except Exception as e: print(f'Ошибка записи chat_pins: {e}')
    return message_id, cmid

def edit_pin(vk, peer_id, text, pin):
    if not pin: return False
    cmid = pin.get('conversation_message_id') if isinstance(pin, dict) else pin[0]
    message_id = pin.get('message_id') if isinstance(pin, dict) else pin[1]

    if cmid:
        try:
            vk.messages.edit(peer_id=peer_id, conversation_message_id=cmid, message=text, disable_mentions=True)
            print(f'✅ Закреп {peer_id} отредактирован через cmid={cmid}')
            return True
        except Exception as e: print(f'Не удалось изменить: {e}')

    if message_id:
        try:
            vk.messages.edit(peer_id=peer_id, message_id=message_id, message=text, disable_mentions=True)
            print(f'✅ Закреп {peer_id} отредактирован через message_id={message_id}')
            return True
        except Exception as e: print(f'Не удалось изменить: {e}')

    return False

def refresh_pin_if_exists(vk, peer_id):
    pinned = get_real_pinned_message(vk, peer_id)
    if pinned and pinned.get('_error'): return False, 'api_error'
    if not pinned:
        reset_chat_pin_cmid(peer_id); return False, 'no_pin'

    expected_from_id = -abs(int(GROUP_ID))
    if pinned.get('from_id') != expected_from_id:
        print(f'Закреп в {peer_id} не принадлежит боту.')
        return False, 'not_bot_message'

    remember_pinned_message(peer_id, pinned)
    text = build_pin_text(vk, peer_id)
    pin_dict = {'conversation_message_id': pinned.get('conversation_message_id'), 'message_id': pinned.get('message_id')}

    if edit_pin(vk, peer_id, text, pin_dict): return True, 'updated'

    reset_chat_pin_cmid(peer_id); return False, 'edit_error'

def update_pin_in_chat(vk, peer_id, notify=False):
    result = refresh_pin_if_exists(vk, peer_id)
    if result[0]: return result
    if result[1] == 'no_pin':
        text = build_pin_text(vk, peer_id)
        message_id, cmid = send_new_pin(vk, peer_id, text)
        if message_id: return True, 'created'
        return False, 'error'
    return result

def update_all_pins(vk):
    chats = get_all_chats()
    results = []
    for peer_id, _ in chats:
        if peer_id == APPLICATIONS_PEER_ID: continue
        try:
            if is_chat_hidden(peer_id): continue
        except Exception: pass
        try:
            result = refresh_pin_if_exists(vk, peer_id)
            results.append((peer_id, result[1]))
        except Exception as e:
            print(f'❌ Ошибка обновления {peer_id}: {e}'); results.append((peer_id, 'error'))
    return results

def refresh_after_admin_change(vk, peer_id=None, global_change=False):
    if global_change:
        print('🔄 Изменена глобальная администрация. Обновляю закрепы.')
        return update_all_pins(vk)
    if peer_id is None: return False, 'no_peer'
    print(f'🔄 Изменена администрация в беседе {peer_id}. Обновляю закреп.')
    return update_pin_in_chat(vk, peer_id)