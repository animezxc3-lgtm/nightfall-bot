from database import (
    get_user,
    set_nickname,
    get_messages_stats,
    get_warning_count,
    get_chat_join_date,
    get_power_rank,
)
from relationships import (
    get_display_name,
    get_partner_id,
    get_children,
    get_parents,
    get_family_surname,
)


def _profile_link(user_id, fallback='Пользователь'):
    name = get_display_name(user_id) or fallback
    return f'[id{user_id}|{name}]'


def get_profile_data(user_id, peer_id=None):
    """
    Возвращает:
        (текст профиля, attachment)

    attachment имеет формат:
        photo-OWNER_ID_PHOTO_ID

    Если аватар не установлен:
        attachment = None
    """

    u = get_user(user_id)

    if not u:
        return 'Профиль не найден.', None

    uid = u[0]
    name = u[1]
    nick = u[2]
    power = u[3]
    coins = u[4]
    job = u[5]
    salary = u[6]
    housing = u[8]
    car = u[9]
    phone = u[10]

    # Индекс 21 = profile_image
    profile_image = u[21]

    # --------------------------------------------------------
    # Дата появления
    # --------------------------------------------------------

    join_date = (
        get_chat_join_date(peer_id, user_id)
        if peer_id
        else None
    )

    if not join_date:
        join_date = u[14] if len(u) > 14 else None

    if join_date:
        join_date = str(join_date)[:10]

        try:
            y, m, d = join_date.split('-')
            join_date = f'{d}.{m}.{y}'
        except ValueError:
            pass
    else:
        join_date = '—'

    # --------------------------------------------------------
    # Отношения / семья
    # --------------------------------------------------------

    partner = get_partner_id(user_id)
    parents = get_parents(user_id)
    children = get_children(user_id)

    # --------------------------------------------------------
    # Права
    # --------------------------------------------------------

    from admin_commands import (
        get_admin_level,
        ROLE_NAMES,
    )

    level = (
        get_admin_level(
            user_id,
            peer_id
        )
        if peer_id
        else 0
    )

    rights_display = ROLE_NAMES.get(
        level,
        'Участник'
    )

    # --------------------------------------------------------
    # Предупреждения
    # --------------------------------------------------------

    warning_count = get_warning_count(
        user_id,
        peer_id
    )

    # --------------------------------------------------------
    # Отображаемое имя
    # --------------------------------------------------------

    display = (
        nick
        or (
            name.split()[0]
            if name
            else 'Пользователь'
        )
    )

    power_rank = get_power_rank(
        power
    )

    # --------------------------------------------------------
    # Текст профиля
    # --------------------------------------------------------

    lines = [
        f'👤 {_profile_link(user_id, display)}',
        f'🔒 Права: {rights_display}',
        f'⚡ Сила Гиаса: {power} // {power_rank}',
        f'🪙 Монеты: {coins}',
        f'💼 Работа: {job}',
        f'💰 Зарплата: {salary} 🪙',
        f'❤️ Партнёр: {_profile_link(partner) if partner else "Нет"}',
        f'👪 Родителей: {len(parents)}',
        f'🧒 Детей: {len(children)}/5',
        f'🏠 Жильё: {housing}',
        f'🚗 Машина: {car}',
        f'📱 Телефон: {phone}',
        f'⚠️ Предупреждения: {warning_count}/3',
        f'📆 Дата появления: {join_date}',
    ]

    # --------------------------------------------------------
    # АВАТАР
    #
    # ВАЖНО:
    # НЕ добавляем photo-... в текст.
    #
    # Он будет передан VK API как attachment.
    # --------------------------------------------------------

    attachment = None

    if profile_image:
        profile_image = str(profile_image).strip()

        if profile_image.startswith('photo'):
            attachment = profile_image

    return (
        '\n'.join(lines),
        attachment,
    )


def get_profile(user_id, peer_id=None):
    """
    Совместимая старая функция.

    Возвращает только текст.
    """

    text, _ = get_profile_data(
        user_id,
        peer_id
    )

    return text


def get_balance(user_id, vk=None):
    u = get_user(user_id)

    if not u:
        return 'Профиль не найден.'

    display = (
        u[2]
        or (
            u[1].split()[0]
            if u[1]
            else 'Пользователь'
        )
    )

    link = f'[id{user_id}|{display}]'

    return (
        f'👤 {link}\n'
        f'⚡ Сила Гиаса: {u[3]}\n'
        f'🪙 Монеты: {u[4]}'
    )


def set_nickname_command(user_id, nick):
    if not 1 <= len(nick) <= 30:
        return 'Ник должен быть от 1 до 30 символов.'

    set_nickname(user_id, nick)

    return f'Ник установлен: {nick}'


def get_activity(user_id):
    s = get_messages_stats(user_id)

    return (
        '📊 Активность\n'
        f'📅 Сегодня: {s["today"]}\n'
        f'📆 За неделю: {s["week"]}\n'
        f'📆 За месяц: {s["month"]}\n'
        f'📈 За всё время: {s["total"]}'
    )