"""Работа с закреплённым сообщением администрации."""

import re

from config import (
    PIN_COMMUNITY_LINK,
    PIN_RULES_LINK,
    PIN_CASINO_LINK,
    PIN_ANARCHY_LINK,
    APPLICATIONS_PEER_ID,
    CREATOR_ID,
    GROUP_ID,
)

from database import (
    get_all_global_roles,
    get_admins_for_chat,
    get_all_chats,
    get_chat_pin,
    set_chat_pin,
    reset_chat_pin_cmid,
    is_chat_hidden,
)


DIVIDER = '⋅⋆✦──── ⋆⋅☆⋅⋆ ────✦⋆⋅'


def _vk_name(vk, uid):
    try:
        info = vk.users.get(user_ids=uid)[0]
        return (f"{info.get('first_name', '')} {info.get('last_name', '')}").strip() or 'Пользователь'
    except Exception:
        return 'Пользователь'


def _mention(vk, uid):
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

    roles = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
    seen = set()

    for uid, level in get_all_global_roles():
        if level not in (5, 6):
            continue
        if uid in seen:
            continue
        roles[level].append(uid)
        seen.add(uid)

    if CREATOR_ID not in seen:
        roles[6].append(CREATOR_ID)
        seen.add(CREATOR_ID)

    for uid, level in get_admins_for_chat(peer_id):
        if level not in (1, 2, 3, 4):
            continue
        if uid in seen:
            continue
        roles[level].append(uid)
        seen.add(uid)

    lines = [
        _header_line(title),
        '',
        'ⵈ━═══╗Информация╔═══━ⵈ',
        '',
        '╰┈➤📓Обязательно прочитайте правила проекта!',
        PIN_RULES_LINK,
        '',
        '╰┈➤📓Заявки на пост администрации:',
        'лл заявка (в ЛС)',
        '',
        DIVIDER,
        '',
    ]

    lines.append('➤ 👑 Лелуш ви Британия:')
    if roles[6]:
        for uid in roles[6]:
            lines.append(f'- {_mention(vk, uid)}')
    else:
        lines.append('absent')

    lines.extend(['', DIVIDER, ''])

    lines.append('➤ ⚖ Вершитель правосудия:')
    if roles[5]:
        for uid in roles[5]:
            lines.append(f'- {_mention(vk, uid)}')
    else:
        lines.append('absent')

    lines.extend(['', DIVIDER, ''])

    local_roles = [
        (4, '📱', 'Главный администратор'),
        (3, '⚙', 'Заместитель главного администратора'),
        (2, '⚒', 'Администраторы'),
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

    lines.extend([
        'ⵈ━═══╗Дополнительно╔═══━ⵈ',
        '',
        '╰┈➤ 📌Сообщество проекта:',
        PIN_COMMUNITY_LINK,
        '╰┈➤ 📌NF || Casino:',
        PIN_CASINO_LINK,
        '╰┈➤ 📌NF || Anarchy:',
        PIN_ANARCHY_LINK,
    ])

    return '\n'.join(lines)


def get_real_pinned_message(vk, peer_id):
    try:
        result = vk.messages.getConversationsById(peer_ids=peer_id)
        items = result.get('items') or []
        if not items:
            return None
        settings = items[0].get('chat_settings') or {}
        pinned = settings.get('pinned_message')
        if not pinned:
            return None

        return {
            'message_id': pinned.get('id'),
            'conversation_message_id': pinned.get('conversation_message_id'),
            'from_id': pinned.get('from_id'),
            'text': pinned.get('text', ''),
        }
    except Exception as e:
        print(f'❌ Ошибка получения закрепа беседы {peer_id}: {e}')
        return None


def remember_pinned_message(peer_id, pinned):
    if not pinned:
        return False
    message_id = pinned.get('message_id')
    cmid = pinned.get('conversation_message_id')
    if not message_id and not cmid:
        return False
    try:
        set_chat_pin(peer_id, conversation_message_id=cmid, message_id=message_id)
        return True
    except Exception as e:
        print(f'Не удалось сохранить закреп {peer_id}: {e}')
        return False


def send_new_pin(vk, peer_id, text):
    try:
        result = vk.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=text,
            disable_mentions=True,
        )
    except Exception as e:
        print(f'Не удалось отправить новое сообщение закрепа в {peer_id}: {e}')
        return None, None

    message_id = result if isinstance(result, int) else None
    cmid = None

    if message_id:
        try:
            info = vk.messages.getById(message_ids=message_id)
            items = info.get('items') or []
            if items:
                cmid = items[0].get('conversation_message_id')
        except Exception as e:
            print(f'getById не сработал для {peer_id}: {e}')

    try:
        set_chat_pin(peer_id, conversation_message_id=cmid, message_id=message_id)
        print(f'📌 Новый закреп в {peer_id}: message_id={message_id}, cmid={cmid}')
    except Exception as e:
        print(f'Ошибка записи chat_pins: {e}')

    return message_id, cmid


def edit_pin(vk, peer_id, text, pin):
    if not pin:
        return False

    cmid = pin.get('conversation_message_id') if isinstance(pin, dict) else pin[0]
    message_id = pin.get('message_id') if isinstance(pin, dict) else pin[1]

    if cmid:
        try:
            vk.messages.edit(
                peer_id=peer_id,
                conversation_message_id=cmid,
                message=text,
                disable_mentions=True,
            )
            print(f'✅ Закреп {peer_id} отредактирован через cmid={cmid}')
            return True
        except Exception as e:
            print(f'Не удалось изменить закреп {peer_id} через cmid={cmid}: {e}')

    if message_id:
        try:
            vk.messages.edit(
                peer_id=peer_id,
                message_id=message_id,
                message=text,
                disable_mentions=True,
            )
            print(f'✅ Закреп {peer_id} отредактирован через message_id={message_id}')
            return True
        except Exception as e:
            print(f'Не удалось изменить закреп {peer_id} через message_id={message_id}: {e}')

    return False


def refresh_pin_if_exists(vk, peer_id):
    pin = get_chat_pin(peer_id)

    if pin and (pin[0] or pin[1]):
        pin_dict = {
            'conversation_message_id': pin[0],
            'message_id': pin[1],
        }
        text = build_pin_text(vk, peer_id)
        if edit_pin(vk, peer_id, text, pin_dict):
            return True, 'updated'
        reset_chat_pin_cmid(peer_id)

    pinned = get_real_pinned_message(vk, peer_id)
    if not pinned:
        return False, 'no_pin'

    from_id = pinned.get('from_id')
    expected_from_id = -abs(int(GROUP_ID))

    if from_id != expected_from_id:
        print(f'Закреп в {peer_id} не принадлежит боту: from_id={from_id}')
        return False, 'not_bot_message'

    remember_pinned_message(peer_id, pinned)

    text = build_pin_text(vk, peer_id)
    pin_dict = {
        'conversation_message_id': pinned.get('conversation_message_id'),
        'message_id': pinned.get('message_id'),
    }

    if edit_pin(vk, peer_id, text, pin_dict):
        return True, 'updated'

    reset_chat_pin_cmid(peer_id)
    return False, 'edit_error'


def update_pin_in_chat(vk, peer_id, notify=False):
    result = refresh_pin_if_exists(vk, peer_id)
    if result[0]:
        return result

    if result[1] == 'no_pin':
        text = build_pin_text(vk, peer_id)
        message_id, cmid = send_new_pin(vk, peer_id, text)
        if message_id:
            return True, 'created'
        return False, 'error'

    return result


def update_all_pins(vk):
    """Обновляет закрепы ТОЛЬКО в беседах с числом в названии."""
    chats = get_all_chats()
    if not chats:
        return []

    ids = [p for p, _ in chats]
    names = {}
    try:
        data = vk.messages.getConversationsById(peer_ids=','.join(map(str, ids))).get('items', [])
        for x in data:
            pid = int(x.get('peer', {}).get('id'))
            names[pid] = (x.get('chat_settings', {}).get('title') or '').strip()
    except Exception as e:
        print(f'Не удалось получить названия бесед: {e}')

    results = []
    for peer_id, _ in chats:
        if peer_id == APPLICATIONS_PEER_ID:
            continue
        title = names.get(peer_id, '')
        if not re.search(r'\d+\s*$', title):
            continue
        result = refresh_pin_if_exists(vk, peer_id)
        results.append((peer_id, result[1]))
    return results


def refresh_after_admin_change(vk, peer_id=None, global_change=False):
    if global_change:
        print('🔄 Изменена глобальная администрация. Обновляю закрепы.')
        return update_all_pins(vk)

    if peer_id is None:
        return False, 'no_peer'

    print(f'🔄 Изменена администрация в беседе {peer_id}. Обновляю закреп.')
    return refresh_pin_if_exists(vk, peer_id)