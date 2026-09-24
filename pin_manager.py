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


# ============================================================
# ИМЯ / УПОМИНАНИЕ
# ============================================================

def _vk_name(vk, uid):
    try:
        info = vk.users.get(
            user_ids=uid
        )[0]

        return (
            f"{info.get('first_name', '')} "
            f"{info.get('last_name', '')}"
        ).strip() or 'Пользователь'

    except Exception:
        return 'Пользователь'


def _mention(vk, uid):
    return f'[id{uid}|{_vk_name(vk, uid)}]'


# ============================================================
# НАЗВАНИЕ БЕСЕДЫ
# ============================================================

def _chat_title(vk, peer_id):
    try:
        result = vk.messages.getConversationsById(
            peer_ids=peer_id
        )

        items = result.get('items') or []

        if items:
            settings = items[0].get(
                'chat_settings',
                {}
            )

            return settings.get(
                'title'
            ) or ''

    except Exception as e:
        print(
            f'⚠️ Не удалось получить название '
            f'беседы {peer_id}: {e}'
        )

    return ''


def _header_line(title):
    title = (title or '').strip()

    if not title:
        return '🌙 NightFall 🌙'

    match = re.match(
        r'^(.*?)(\d+)\s*$',
        title
    )

    if match:
        return (
            f'🌙 {match.group(1).strip()} '
            f'{match.group(2)} 🌙'
        )

    return f'🌙 {title} 🌙'


# ============================================================
# ТЕКСТ ЗАКРЕПА
# ============================================================

def build_pin_text(vk, peer_id):
    """
    Формирует актуальный текст закрепа.

    Роли 1–4:
        только текущая беседа.

    Роли 5–6:
        глобальные, поэтому отображаются
        во всех беседах.
    """

    title = _chat_title(
        vk,
        peer_id
    )

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

    # Создатель всегда является ролью 6.
    if CREATOR_ID not in seen:
        roles[6].append(
            CREATOR_ID
        )
        seen.add(CREATOR_ID)

    # --------------------------------------------------------
    # ЛОКАЛЬНЫЕ РОЛИ 1–4
    # --------------------------------------------------------

    for uid, level in get_admins_for_chat(
        peer_id
    ):

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

    # --------------------------------------------------------
    # РОЛЬ 6
    # --------------------------------------------------------

    lines.append(
        '➤ 👑 Лелуш ви Британия:'
    )

    if roles[6]:
        for uid in roles[6]:
            lines.append(
                f'- {_mention(vk, uid)}'
            )
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

    lines.append(
        '➤ ⚖ Вершитель правосудия:'
    )

    if roles[5]:
        for uid in roles[5]:
            lines.append(
                f'- {_mention(vk, uid)}'
            )
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

        lines.append(
            f'➤ {emoji} {label}:'
        )

        if roles[level]:
            for uid in roles[level]:
                lines.append(
                    f'- {_mention(vk, uid)}'
                )
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
# ПОИСК РЕАЛЬНОГО ЗАКРЕПЛЁННОГО СООБЩЕНИЯ
# ============================================================

def get_real_pinned_message(vk, peer_id):
    """
    Получает именно то сообщение, которое сейчас закреплено
    в беседе через VK API.

    Это важно: БД может не содержать ID закрепа, поэтому
    нельзя полагаться только на chat_pins.
    """

    try:
        result = vk.messages.getConversationsById(
            peer_ids=peer_id
        )

        items = result.get('items') or []

        if not items:
            print(
                f'⚠️ VK не вернул информацию '
                f'о беседе {peer_id}'
            )
            return None

        settings = items[0].get(
            'chat_settings'
        ) or {}

        pinned = settings.get(
            'pinned_message'
        )

        if not pinned:
            print(
                f'📌 В беседе {peer_id} '
                f'нет закреплённого сообщения.'
            )
            return None

        message_id = pinned.get(
            'id'
        )

        cmid = pinned.get(
            'conversation_message_id'
        )

        from_id = pinned.get(
            'from_id'
        )

        text = pinned.get(
            'text',
            ''
        )

        print(
            f'📌 Найден закреп {peer_id}: '
            f'message_id={message_id}, '
            f'cmid={cmid}, '
            f'from_id={from_id}'
        )

        return {
            'message_id': message_id,
            'conversation_message_id': cmid,
            'from_id': from_id,
            'text': text,
        }

    except Exception as e:
        print(
            f'❌ Ошибка получения закрепа '
            f'беседы {peer_id}: {e}'
        )

        return None


# ============================================================
# СОХРАНЕНИЕ ID ЗАКРЕПА
# ============================================================

def remember_pinned_message(
    peer_id,
    pinned
):
    """
    Сохраняет найденный VK закреп в БД.
    """

    if not pinned:
        return False

    message_id = pinned.get(
        'message_id'
    )

    cmid = pinned.get(
        'conversation_message_id'
    )

    if not message_id and not cmid:
        return False

    try:
        set_chat_pin(
            peer_id,
            conversation_message_id=cmid,
            message_id=message_id,
        )

        return True

    except Exception as e:
        print(
            f'⚠️ Не удалось сохранить закреп '
            f'{peer_id}: {e}'
        )

        return False


# ============================================================
# СОЗДАНИЕ НОВОГО ЗАКРЕПА
# ============================================================

def send_new_pin(vk, peer_id, text):
    """
    Отправляет новое сообщение закрепа и сохраняет его ID в БД.
    Возвращает (message_id, cmid).
    """

    try:
        result = vk.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=text,
            disable_mentions=True,
        )

    except Exception as e:
        print(
            f'⚠️ Не удалось отправить новое сообщение '
            f'закрепа в {peer_id}: {e}'
        )
        return None, None

    message_id = result if isinstance(result, int) else None
    cmid = None

    if message_id:
        try:
            info = vk.messages.getById(
                message_ids=message_id
            )
            items = info.get('items') or []

            if items:
                cmid = items[0].get(
                    'conversation_message_id'
                )

        except Exception as e:
            print(
                f'⚠️ getById не сработал '
                f'для {peer_id}: {e}'
            )

    try:
        set_chat_pin(
            peer_id,
            conversation_message_id=cmid,
            message_id=message_id,
        )

        print(
            f'📌 Новый закреп в {peer_id}: '
            f'message_id={message_id}, cmid={cmid}'
        )

    except Exception as e:
        print(
            f'⚠️ Ошибка записи chat_pins: {e}'
        )

    return message_id, cmid


# ============================================================
# ПОЛУЧЕНИЕ ID ЗАКРЕПА
# ============================================================

def get_pin_ids(vk, peer_id):
    """
    Сначала пытается получить закреп из БД.

    Если его там нет — ищет настоящее закреплённое
    сообщение через VK API.
    """

    pin = get_chat_pin(
        peer_id
    )

    if pin and (
        pin[0] or pin[1]
    ):
        return {
            'conversation_message_id': pin[0],
            'message_id': pin[1],
        }

    # БД ничего не знает.
    pinned = get_real_pinned_message(
        vk,
        peer_id
    )

    if not pinned:
        return None

    remember_pinned_message(
        peer_id,
        pinned
    )

    return {
        'conversation_message_id':
            pinned.get(
                'conversation_message_id'
            ),
        'message_id':
            pinned.get(
                'message_id'
            ),
        'from_id':
            pinned.get(
                'from_id'
            ),
    }


# ============================================================
# РЕДАКТИРОВАНИЕ
# ============================================================

def edit_pin(
    vk,
    peer_id,
    text,
    pin
):
    """
    Редактирует существующее сообщение.

    В первую очередь используется
    conversation_message_id — это основной
    идентификатор сообщения внутри беседы.
    """

    if not pin:
        return False

    cmid = pin.get(
        'conversation_message_id'
    )

    message_id = pin.get(
        'message_id'
    )

    # --------------------------------------------------------
    # Через conversation_message_id
    # --------------------------------------------------------

    if cmid:

        try:
            vk.messages.edit(
                peer_id=peer_id,
                conversation_message_id=cmid,
                message=text,
                disable_mentions=True,
            )

            print(
                f'✅ Закреп {peer_id} '
                f'успешно отредактирован '
                f'через cmid={cmid}'
            )

            return True

        except Exception as e:
            print(
                f'⚠️ Не удалось изменить '
                f'закреп {peer_id} '
                f'через cmid={cmid}: {e}'
            )

    # --------------------------------------------------------
    # Резервный вариант
    # --------------------------------------------------------

    if message_id:

        try:
            vk.messages.edit(
                peer_id=peer_id,
                message_id=message_id,
                message=text,
                disable_mentions=True,
            )

            print(
                f'✅ Закреп {peer_id} '
                f'успешно отредактирован '
                f'через message_id={message_id}'
            )

            return True

        except Exception as e:
            print(
                f'⚠️ Не удалось изменить '
                f'закреп {peer_id} '
                f'через message_id={message_id}: {e}'
            )

    return False


# ============================================================
# ОБНОВЛЕНИЕ ЗАКРЕПА
# ============================================================

def refresh_pin_if_exists(
    vk,
    peer_id
):
    """
    Обновляет существующее закреплённое сообщение.

    Если его нет в БД, сначала самостоятельно находит
    его через VK API.

    НОВОЕ сообщение здесь НЕ создаётся.
    """

    # Сначала пробуем взять ID из БД.
    pin = get_chat_pin(peer_id)

    if pin and (pin[0] or pin[1]):
        pin_dict = {
            'conversation_message_id': pin[0],
            'message_id': pin[1],
        }

        text = build_pin_text(vk, peer_id)

        if edit_pin(vk, peer_id, text, pin_dict):
            return True, 'updated'

        # Старые ID устарели.
        reset_chat_pin_cmid(peer_id)

    # В БД нет — пробуем через VK API.
    pinned = get_real_pinned_message(
        vk,
        peer_id
    )

    if not pinned:
        return False, 'no_pin'

    from_id = pinned.get('from_id')
    expected_from_id = -abs(int(GROUP_ID))

    if from_id != expected_from_id:
        print(
            f'⚠️ Закреп в {peer_id} '
            f'не принадлежит боту: '
            f'from_id={from_id}, '
            f'ожидался {expected_from_id}. '
            f'VK не позволит боту изменить '
            f'чужое сообщение.'
        )
        return False, 'not_bot_message'

    remember_pinned_message(peer_id, pinned)

    text = build_pin_text(vk, peer_id)

    pin_dict = {
        'conversation_message_id':
            pinned.get('conversation_message_id'),
        'message_id':
            pinned.get('message_id'),
    }

    if edit_pin(vk, peer_id, text, pin_dict):
        return True, 'updated'

    print(
        f'❌ VK не позволил отредактировать '
        f'закреп в {peer_id}.'
    )

    reset_chat_pin_cmid(peer_id)

    return False, 'edit_error'


# ============================================================
# ПОЛНОЕ ОБНОВЛЕНИЕ
# ============================================================

def update_pin_in_chat(vk, peer_id, notify=False):
    """
    Если закреп есть — редактирует.
    Если нет — создаёт новый.
    """

    result = refresh_pin_if_exists(vk, peer_id)

    if result[0]:
        return result  # updated

    if result[1] == 'no_pin':
        text = build_pin_text(vk, peer_id)
        message_id, cmid = send_new_pin(vk, peer_id, text)

        if message_id:
            return True, 'created'

        return False, 'error'

    # Есть, но не редактируется (например, чужой или ошибка VK).
    return result


# ============================================================
# ОБНОВЛЕНИЕ ВСЕХ БЕСЕД
# ============================================================

def update_all_pins(vk):
    """
    Проверяет и обновляет закрепы всех известных бесед.
    Роли 5–6 должны обновлять закрепы всех бесед.
    """

    results = []

    for peer_id, _ in get_all_chats():

        if peer_id == APPLICATIONS_PEER_ID:
            continue

        if is_chat_hidden(peer_id):
            continue

        result = refresh_pin_if_exists(
            vk,
            peer_id
        )

        results.append(
            (
                peer_id,
                result[1]
            )
        )

    return results


# ============================================================
# ОБНОВЛЕНИЕ ПОСЛЕ ИЗМЕНЕНИЯ АДМИНИСТРАЦИИ
# ============================================================

def refresh_after_admin_change(
    vk,
    peer_id=None,
    global_change=False
):
    """
    Вызывается после изменения администрации.

    Локальная роль 1–4:
        обновляется одна беседа.

    Глобальная роль 5–6:
        обновляются все беседы.
    """

    if global_change:

        print(
            '🔄 Изменена глобальная администрация. '
            'Обновляю закрепы всех бесед.'
        )

        return update_all_pins(
            vk
        )

    if peer_id is None:
        return False, 'no_peer'

    print(
        f'🔄 Изменена администрация '
        f'в беседе {peer_id}. '
        f'Обновляю закреп.'
    )

    return refresh_pin_if_exists(
        vk,
        peer_id
    )