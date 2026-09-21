"""Сборка и автоматическое обновление закрепов бесед."""

import re

from config import (
    PIN_COMMUNITY_LINK,
    PIN_RULES_LINK,
    PIN_CASINO_LINK,
    PIN_ANARCHY_LINK,
    APPLICATIONS_PEER_ID,
    CREATOR_ID,
)

from database import (
    get_all_global_roles,
    get_admins_for_chat,
    get_all_chats,
    get_chat_pin,
    is_chat_hidden,
    reset_chat_pin_cmid,
    db_cursor,
)


DIVIDER = '⋅⋆✦──── ⋆⋅☆⋅⋆ ────✦⋆⋅'


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def _vk_name(vk, uid):
    try:
        info = vk.users.get(user_ids=uid)[0]

        name = (
            f"{info.get('first_name', '')} "
            f"{info.get('last_name', '')}"
        ).strip()

        return name or 'Пользователь'

    except Exception:
        return 'Пользователь'


def _mention(vk, uid):
    return f'[id{uid}|{_vk_name(vk, uid)}]'


def _chat_title(vk, peer_id):
    try:
        data = vk.messages.getConversationsById(
            peer_ids=peer_id
        ).get('items') or []

        if data:
            settings = data[0].get('chat_settings', {})
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


# ============================================================
# ФОРМИРОВАНИЕ ТЕКСТА ЗАКРЕПА
# ============================================================

def build_pin_text(vk, peer_id):
    """
    Формирует актуальный текст закрепа.

    Роли:
        1–4 — только текущая беседа.
        5–6 — глобальные, отображаются во всех беседах.
    """

    title = _chat_title(vk, peer_id)
    header = _header_line(title)

    roles = {
        1: [],
        2: [],
        3: [],
        4: [],
        5: [],
        6: [],
    }

    seen = set()

    # --------------------------------------------------------
    # ГЛОБАЛЬНЫЕ РОЛИ 5–6
    # --------------------------------------------------------

    for uid, level in get_all_global_roles():

        if level not in (5, 6):
            continue

        if uid in seen:
            continue

        roles[level].append(uid)
        seen.add(uid)

    # Создатель всегда отображается как роль 6.
    if CREATOR_ID not in seen:
        roles[6].append(CREATOR_ID)
        seen.add(CREATOR_ID)

    # --------------------------------------------------------
    # ЛОКАЛЬНЫЕ РОЛИ 1–4
    # --------------------------------------------------------

    for uid, level in get_admins_for_chat(peer_id):

        if level not in (1, 2, 3, 4):
            continue

        if uid in seen:
            continue

        roles[level].append(uid)
        seen.add(uid)

    # --------------------------------------------------------
    # ТЕКСТ
    # --------------------------------------------------------

    lines = [
        header,
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

    # --------------------------------------------------------
    # РОЛЬ 6
    # --------------------------------------------------------

    lines.append('➤ 👑 Лелуш ви Британия:')

    if roles[6]:
        for uid in roles[6]:
            lines.append(f'- {_mention(vk, uid)}')
    else:
        lines.append('absent')

    lines.extend([
        '',
        DIVIDER,
        '',
    ])

    # --------------------------------------------------------
    # РОЛЬ 5
    # --------------------------------------------------------

    lines.append('➤ ⚖ Вершитель правосудия:')

    if roles[5]:
        for uid in roles[5]:
            lines.append(f'- {_mention(vk, uid)}')
    else:
        lines.append('absent')

    lines.extend([
        '',
        DIVIDER,
        '',
    ])

    # --------------------------------------------------------
    # РОЛИ 4–1
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # ДОПОЛНИТЕЛЬНО
    # --------------------------------------------------------

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


# ============================================================
# ПОЛУЧЕНИЕ CONVERSATION MESSAGE ID
# ============================================================

def _extract_cmid(vk, message_id):
    """
    Получает conversation_message_id по обычному message_id.
    """

    if not message_id:
        return None

    try:
        info = vk.messages.getById(
            message_ids=message_id
        )

        items = info.get('items') or []

        if items:
            return items[0].get('conversation_message_id')

    except Exception as e:
        print(
            f'⚠️ Не удалось получить conversation_message_id '
            f'для message_id={message_id}: {e}'
        )

    return None


# ============================================================
# СОЗДАНИЕ НОВОГО СООБЩЕНИЯ
# ============================================================

def send_new_pin(vk, peer_id, text):
    """
    Создаёт новое сообщение закрепа и сохраняет его ID в БД.

    Возвращает:
        (message_id, conversation_message_id)
    """

    try:
        result = vk.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=text,
            disable_mentions=True,
            dont_parse_links=1,
        )

    except Exception as e:
        print(
            f'⚠️ Не удалось отправить новое сообщение '
            f'закрепа в {peer_id}: {e}'
        )

        return None, None

    message_id = result if isinstance(result, int) else None

    cmid = _extract_cmid(
        vk,
        message_id
    )

    # Сохраняем ID сообщения.
    with db_cursor(True) as (_, c):

        c.execute(
            """
            INSERT INTO chat_pins(
                peer_id,
                conversation_message_id,
                message_id,
                updated_at
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)

            ON CONFLICT(peer_id) DO UPDATE SET
                conversation_message_id =
                    excluded.conversation_message_id,

                message_id =
                    excluded.message_id,

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                peer_id,
                cmid,
                message_id,
            )
        )

    print(
        f'📌 Новый закреп в {peer_id}: '
        f'message_id={message_id}, cmid={cmid}'
    )

    return message_id, cmid


# ============================================================
# РЕДАКТИРОВАНИЕ СУЩЕСТВУЮЩЕГО ЗАКРЕПА
# ============================================================

def edit_pin(vk, peer_id, text, pin):
    """
    Редактирует существующее сообщение закрепа.

    Сначала используется conversation_message_id.
    Если он не работает — используется message_id.

    Возвращает True при успехе.
    """

    if not pin:
        return False

    cmid = pin[0]
    message_id = pin[1]

    # --------------------------------------------------------
    # Попытка через conversation_message_id
    # --------------------------------------------------------

    if cmid:

        try:
            vk.messages.edit(
                peer_id=peer_id,
                conversation_message_id=cmid,
                message=text,
                disable_mentions=True,
                dont_parse_links=1,
            )

            print(
                f'✏️ Закреп {peer_id} обновлён '
                f'через conversation_message_id={cmid}'
            )

            return True

        except Exception as e:
            print(
                f'⚠️ Не удалось изменить закреп '
                f'через cmid={cmid} в {peer_id}: {e}'
            )

    # --------------------------------------------------------
    # Попытка через message_id
    # --------------------------------------------------------

    if message_id:

        try:
            vk.messages.edit(
                peer_id=peer_id,
                message_id=message_id,
                message=text,
                disable_mentions=True,
                dont_parse_links=1,
            )

            print(
                f'✏️ Закреп {peer_id} обновлён '
                f'через message_id={message_id}'
            )

            return True

        except Exception as e:
            print(
                f'⚠️ Не удалось изменить закреп '
                f'через message_id={message_id} в {peer_id}: {e}'
            )

    return False


# ============================================================
# ОБНОВЛЕНИЕ ЗАКРЕПА ОДНОЙ БЕСЕДЫ
# ============================================================

def update_pin_in_chat(vk, peer_id, notify=False):
    """
    Обновляет закреп конкретной беседы.

    Если закреп уже существует в БД:
        редактирует его.

    Если старое сообщение больше недоступно:
        создаёт новое.

    Если закрепа ещё нет:
        создаёт сообщение.

    ВАЖНО:
    Само сообщение не закрепляется автоматически.
    После первого использования его нужно один раз закрепить
    в VK вручную.
    """

    text = build_pin_text(
        vk,
        peer_id
    )

    pin = get_chat_pin(peer_id)

    # --------------------------------------------------------
    # Уже есть сохранённый закреп
    # --------------------------------------------------------

    if pin and (pin[0] or pin[1]):

        if edit_pin(
            vk,
            peer_id,
            text,
            pin
        ):
            return True, 'updated'

        # Старый ID больше не работает.
        reset_chat_pin_cmid(peer_id)

        message_id, cmid = send_new_pin(
            vk,
            peer_id,
            text
        )

        if message_id:
            return True, 'recreated'

        return False, 'error'

    # --------------------------------------------------------
    # Закреп ещё не создан
    # --------------------------------------------------------

    message_id, cmid = send_new_pin(
        vk,
        peer_id,
        text
    )

    if message_id:
        return True, 'created'

    return False, 'error'


# ============================================================
# ОБНОВЛЕНИЕ ТОЛЬКО СУЩЕСТВУЮЩЕГО ЗАКРЕПА
# ============================================================

def refresh_pin_if_exists(vk, peer_id):
    """
    Обновляет закреп только если он уже зарегистрирован в БД.

    Новое сообщение не создаёт.
    """

    pin = get_chat_pin(peer_id)

    if not pin or (not pin[0] and not pin[1]):
        return False, 'no_pin'

    text = build_pin_text(
        vk,
        peer_id
    )

    if edit_pin(
        vk,
        peer_id,
        text,
        pin
    ):
        return True, 'updated'

    # Старый ID оказался недействительным.
    reset_chat_pin_cmid(peer_id)

    return False, 'reset'


# ============================================================
# ОБНОВЛЕНИЕ ВСЕХ ЗАКРЕПОВ
# ============================================================

def update_all_pins(vk):
    """
    Обновляет закрепы всех бесед, которые:
        - есть в БД;
        - не являются беседой заявок;
        - не скрыты.

    Новые закрепы автоматически здесь не создаются.
    """

    chats = get_all_chats()
    results = []

    for peer_id, _ in chats:

        if peer_id == APPLICATIONS_PEER_ID:
            continue

        if is_chat_hidden(peer_id):
            continue

        ok, status = refresh_pin_if_exists(
            vk,
            peer_id
        )

        results.append(
            (
                peer_id,
                status
            )
        )

    return results


# ============================================================
# ОБНОВЛЕНИЕ ЗАКРЕПА ПОСЛЕ ИЗМЕНЕНИЯ АДМИНИСТРАЦИИ
# ============================================================

def refresh_after_admin_change(vk, peer_id=None, global_change=False):
    """
    Вызывается после изменения состава администрации.

    global_change=True:
        обновляются закрепы всех бесед.

    global_change=False:
        обновляется только указанная беседа.
    """

    if global_change:

        print(
            '🔄 Изменение глобальной администрации — '
            'обновляю закрепы всех бесед.'
        )

        results = update_all_pins(vk)

        updated = sum(
            1
            for _, status in results
            if status == 'updated'
        )

        print(
            f'📌 Обновлено глобальных закрепов: {updated}'
        )

        return results

    if peer_id is None:
        return None

    print(
        f'🔄 Изменение администрации в беседе {peer_id} — '
        f'обновляю закреп.'
    )

    return refresh_pin_if_exists(
        vk,
        peer_id
    )