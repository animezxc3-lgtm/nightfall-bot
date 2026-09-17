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
    is_chat_hidden,
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
    """Отправляет новое сообщение закрепа и сохраняет message_id и cmid."""
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

    set_chat_pin(peer_id, conversation_message_id=cmid, message_id=message_id)
    return message_id


def update_pin_in_chat(vk, peer_id, notify=False):
    """Обновляет закреп в одной беседе. Возвращает (ok, status)."""
    text = build_pin_text(vk, peer_id)
    pin = get_chat_pin(peer_id)  # (cmid, message_id, updated_at) или None

    if pin and (pin[0] or pin[1]):
        cmid = pin[0]
        message_id = pin[1]

        edited = False

        if cmid:
            try:
                vk.messages.edit(
                    peer_id=peer_id,
                    conversation_message_id=cmid,
                    message=text,
                    disable_mentions=True,
                    dont_parse_links=1,
                )
                edited = True
            except Exception as e:
                print(f'⚠️ edit по cmid не сработал в {peer_id}: {e}')

        if not edited and message_id:
            try:
                vk.messages.edit(
                    peer_id=peer_id,
                    message_id=message_id,
                    message=text,
                    disable_mentions=True,
                    dont_parse_links=1,
                )
                edited = True
            except Exception as e:
                print(f'⚠️ edit по message_id не сработал в {peer_id}: {e}')

        if edited:
            return True, 'updated'

        print(f'⚠️ Закреп в {peer_id} не редактируется, создаю новый.')
        _send_new_pin(vk, peer_id, text)
        return True, 'recreated'

    _send_new_pin(vk, peer_id, text)
    return True, 'created'


def update_all_pins(vk):
    """Обновляет закрепы во всех беседах, кроме скрытых и беседы заявок."""
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