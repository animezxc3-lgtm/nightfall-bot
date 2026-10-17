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
    get_family_surname,
    get_days_in_relationship,
)
from jobs.professions import PROFESSIONS, get_level_name
from admin_commands import get_admin_level, ROLE_NAMES


def _profile_link(user_id, fallback='Пользователь'):
    name = get_display_name(user_id) or fallback
    return f'[id{user_id}|{name}]'


def _format_job(job_key, job_level):
    if not job_key or job_key not in PROFESSIONS:
        return 'Отсутствует'
    job_name = PROFESSIONS[job_key]['name']
    level_name = get_level_name(job_key, job_level or 0)
    return f'{job_name} | {level_name}'


def get_profile_data(user_id, peer_id=None):
    u = get_user(user_id)

    if not u:
        return 'Профиль не найден.', None

    # Индексы get_user:
    # 0 user_id | 1 name | 2 nickname | 3 soul_gems | 4 power | 5 coins
    # 6 job | 7 salary | 8 work_days | 9 housing | 10 car | 11 phone
    # 12 role | 13 rights | 14 warnings | 15 join_date | 16 messages_total
    # 17 banned | 18 job_level | 19 job_exp | 20 job_last_work
    # 21 family_surname | 22 profile_image | 23 custom_role | 24 admin_warnings
    # 25 last_message_at | 26 status | 27 gif_link | 28 salary_multiplier

    uid = u[0]
    name = u[1]
    nick = u[2]
    soul_gems = u[3] or 0
    power = u[4] or 0
    coins = u[5]
    job_key = u[6]
    housing = u[9]
    car = u[10]
    phone = u[11]
    job_level = u[18] or 0
    profile_image = u[22]
    gif_link = u[27] or ''
    status = u[26] or ''

    job_display = _format_job(job_key, job_level)
    power_rank = get_power_rank(power)

    join_date = (
        get_chat_join_date(peer_id, user_id)
        if peer_id
        else None
    )
    if not join_date:
        join_date = u[15] if len(u) > 15 else None
    if join_date:
        join_date = str(join_date)[:10]
        try:
            y, m, d = join_date.split('-')
            join_date = f'{d}.{m}.{y}'
        except ValueError:
            pass
    else:
        join_date = '—'

    partner = get_partner_id(user_id)
    days = get_days_in_relationship(user_id) if partner else None
    days_line = str(days) if days is not None else '—'

    level = get_admin_level(user_id, peer_id) if peer_id else 0
    rights_display = ROLE_NAMES.get(level, 'Участник')

    warning_count = get_warning_count(user_id, peer_id)

    display = nick or (name.split()[0] if name else 'Пользователь')

    lines = [f'👤 {_profile_link(user_id, display)}']

    # Статус — только если куплен
    if status:
        lines.append(f'📝 Статус: {status}')

    lines.append(f'⚡ Сила Гиаса: {power} // {power_rank}')

    # Камни — только админам (уровень >= 1)
    if level >= 1:
        lines.append(f'💎 Камни души: {soul_gems}')

    lines.extend([
        f'🪙 Монеты: {coins}',
        f'💼 Работа: {job_display}',
        f'❤️ Партнёр: {_profile_link(partner) if partner else "Нет"}',
        f'❤️ Дней в отношениях: {days_line}',
        f'🏠 Жильё: {housing}',
        f'🚗 Машина: {car}',
        f'📱 Телефон: {phone}',
        f'⚠️ Предупреждения: {warning_count}/3',
        f'🔒 Права: {rights_display}',
        f'📆 Дата появления: {join_date}',
    ])

    attachment = None
    # Приоритет: gif_link (документ), потом profile_image (фото)
    if gif_link:
        gif_link = str(gif_link).strip()
        if gif_link.startswith('https://vk.com/doc') or gif_link.startswith('https://vk.ru/doc'):
            # VK принимает doc-ссылки как attachment
            attachment = gif_link
    if not attachment and profile_image:
        profile_image = str(profile_image).strip()
        if profile_image.startswith('photo'):
            attachment = profile_image

    return '\n'.join(lines), attachment


def get_profile(user_id, peer_id=None):
    text, _ = get_profile_data(user_id, peer_id)
    return text


def get_balance(user_id, vk=None):
    u = get_user(user_id)
    if not u:
        return 'Профиль не найден.'

    # Индексы: 1 name | 2 nickname | 3 soul_gems | 4 power | 5 coins
    name = u[1]
    nick = u[2]
    soul_gems = u[3] or 0
    power = u[4] or 0
    coins = u[5]

    display = nick or (name.split()[0] if name else 'Пользователь')
    link = f'[id{user_id}|{display}]'
    power_rank = get_power_rank(power)

    lines = [f'👤 {link}', f'⚡ Сила Гиаса: {power} // {power_rank}']

    # Камни показываем только админам
    from admin_commands import get_admin_level
    level = get_admin_level(user_id, None) if vk else 0
    if level >= 1:
        lines.append(f'💎 Камни души: {soul_gems}')

    lines.append(f'🪙 Монеты: {coins}')
    return '\n'.join(lines)


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