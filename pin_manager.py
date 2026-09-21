"""Сборка и обновление закрепов бесед."""
import json
import re

from config import (
    PIN_COMMUNITY_LINK, PIN_RULES_LINK,
    PIN_CASINO_LINK, PIN_ANARCHY_LINK,
    APPLICATIONS_PEER_ID, CREATOR_ID,
)
from database import (
    get_all_global_roles, get_admins_for_chat,
    get_all_chats, get_chat_pin, set_chat_pin,
    is_chat_hidden, set_chat_pin_cmid, reset_chat_pin_cmid,
)


ROLE_LINES = [
    (6, '👑', 'Лелуш ви Британия'),
    (5, '⚖', 'Вершитель правосудия'),
    (4, '📱', 'Главный администратор'),
    (3, '⚙', 'Заместитель главного администратора'),
    (2, '⚒', 'Администраторы'),
    (1, '🎓', 'Стажёры'),
]

DIVIDER = '⋅⋆✦──── ⋆⋅☆⋅⋆ ────✦⋆⋅'


def _vk_name(vk, uid):
    try:
        info = vk.users.get(user_ids=uid)[0]
        return f"{info.get('first_name','')} {info.get('last_name','')}".strip() or 'Пользователь'
    except Exception:
        return 'Пользователь'


def _mention(vk, uid):
    return f'[id{uid}|{_vk_name(vk, uid)}]'


def _chat_title(vk, peer_id):
    try:
        data = vk.messages.getConversationsById(peer_ids=peer_id).get('items') or []
        if data:
            return data[0].get('chat_settings', {}).get('title') or ''
    except Exception as e:
        print(f'⚠️ Не удалось получить название беседы {peer_id}: {e}')
    return ''


def _header_line(title):
    title = (title or '').strip()
    if not title:
        return '🌙 NightFall 🌙'
    m = re.match(r'^(.*?)(\d+)\s*$', title)
    if m:
        return f'🌙 {m.group(1).strip()} {m.group(2)} 🌙'
    return f'🌙 {title} 🌙'


def build_pin_text(vk, peer_id):
    title = _chat_title(vk, peer_id)
    header = _header_line(title)

    roles = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
    seen = set()

    for uid, level in get_all_global_roles():
        if level in (5, 6) and uid not in seen:
            roles[level].append(uid)
            seen.add(uid)

    if CREATOR_ID not in seen:
        roles[6].append(CREATOR_ID)
        seen.add(CREATOR_ID)

    for uid, level in get_admins_for_chat(peer_id):
        if level in (1, 2, 3, 4) and uid not in seen:
            roles[level].append(uid)
            seen.add(uid)

    lines = [header, '']
    lines.append('ⵈ━═══╗Информация╔═══━ⵈ')
    lines.append('')
    lines.append('╰┈➤📓Обязательно прочитайте правила проекта!')
    lines.append(PIN_RULES_LINK)
    lines.append('╰┈➤📓Заявки на пост администрации:')
    lines.append('лл заявка (в ЛС)')
    lines.append('')
    lines.append(DIVIDER)
    lines.append('')

    lines.append('➤ 👑 Лелуш ви Британия:')
    if roles[6]:
        for uid in roles[6]:
            lines.append(f'- {_mention(vk, uid)}')
    else:
        lines.append('absent')
    lines.append('')
    lines.append(DIVIDER)
    lines.append('')

    lines.append('➤ ⚖ Вершитель правосудия:')
    if roles[5]:
        for uid in roles[5]:
            lines.append(f'- {_mention(vk, uid)}')
    else:
        lines.append('absent')
    lines.append('')
    lines.append(DIVIDER)
    lines.append('')

    for level, emoji, label in [(4, '📱', 'Главный администратор'),
                                (3, '⚙', 'Заместитель главного администратора'),
                                (2, '⚒', 'Администраторы'),
                                (1, '🎓', 'Стажёры')]:
        lines.append(f'➤ {emoji} {label}:')
        if roles[level]:
            for uid in roles[level]:
                lines.append(f'- {_mention(vk, uid)}')
        else:
            lines.append('absent')
        lines.append('')

    lines.append('ⵈ━═══╗Дополнительно╔═══━ⵈ')
    lines.append('')
    lines.append('╰┈➤ 📌Сообщество проекта:')
    lines.append(PIN_COMMUNITY_LINK)
    lines.append('╰┈➤ 📌NF || Casino:')
    lines.append(PIN_CASINO_LINK)
    lines.append('╰┈➤ 📌NF || Anarchy:')
    lines.append(PIN_ANARCHY_LINK)

    return '\n'.join(lines)


def _send_new_pin(vk, peer_id, text):
    """Отправляет новое сообщение закрепа и сразу получает cmid через getById."""
    try:
        result = vk.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=text,
            disable_mentions=True,
            dont_parse_links=1,
        )
    except Exception as e:
        print(f'⚠️ Не удалось отправить закреп в {peer_id}: {e}')
        return None

    message_id = result if isinstance(result, int) else None
    cmid = None

    if message_id:
        try:
            info = vk.messages.getById(message_ids=message_id)
            items = info.get('items') or []
            if items:
                cmid = items[0].get('conversation_message_id')
        except Exception as e:
            print(f'⚠️ getById не сработал для {peer_id}: {e}')

    with __import__('database').db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO chat_pins(peer_id, conversation_message_id, message_id, updated_at)
            VALUES(?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(peer_id) DO UPDATE SET
                conversation_message_id=excluded.conversation_message_id,
                message_id=excluded.message_id,
                updated_at=CURRENT_TIMESTAMP
        """, (peer_id, cmid, message_id))

    print(f'📌 Закреп {peer_id}: message_id={message_id}, cmid={cmid}')
    return cmid


def update_pin_in_chat(vk, peer_id, notify=False):
    """Полное обновление закрепа: создать новый, если нет; редактировать, если есть.
    Используется по команде `лл установить закреп` и `лл обновить закрепы`."""
    text = build_pin_text(vk, peer_id)
    pin = get_chat_pin(peer_id)

    if pin and pin[0]:
        cmid = pin[0]
        try:
            vk.messages.edit(
                peer_id=peer_id,
                conversation_message_id=cmid,
                message=text,
                disable_mentions=True,
                dont_parse_links=1,
            )
            return True, 'updated'
        except Exception as e:
            print(f'⚠️ edit по cmid не сработал в {peer_id}: {e}')
            reset_chat_pin_cmid(peer_id)
            return True, 'reset'

    if pin and not pin[0]:
        print(f'⏳ Закреп в {peer_id} ожидает cmid, пропуск.')
        return True, 'waiting'

    _send_new_pin(vk, peer_id, text)
    return True, 'created'


def refresh_pin_if_exists(vk, peer_id):
    """Обновляет закреп ТОЛЬКО если он уже есть (cmid сохранён).
    Новое сообщение НЕ создаёт."""
    pin = get_chat_pin(peer_id)
    if not pin or not pin[0]:
        return False, 'no_pin'
    text = build_pin_text(vk, peer_id)
    try:
        vk.messages.edit(
            peer_id=peer_id,
            conversation_message_id=pin[0],
            message=text,
            disable_mentions=True,
            dont_parse_links=1,
        )
        return True, 'updated'
    except Exception as e:
        print(f'⚠️ Не удалось обновить закреп {peer_id}: {e}')
        reset_chat_pin_cmid(peer_id)
        return False, 'reset'


def update_all_pins(vk):
    """Массовое обновление — создаёт/редактирует, кроме скрытых и беседы заявок."""
    chats = get_all_chats()
    results = []
    for peer_id, _ in chats:
        if peer_id == APPLICATIONS_PEER_ID:
            continue
        if is_chat_hidden(peer_id):
            continue
        ok, status = update_pin_in_chat(vk, peer_id)
        results.append((peer_id, status))
    return results