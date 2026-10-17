"""Еженедельный созыв админов + проверка нормы."""

from database import (
    get_all_admin_week_stats, reset_admin_week_stats,
    get_global_role, get_admin_level_for_chat, db_cursor,
    get_user, update_gems, get_messages_stats,
    get_admin_week_stats,
)
from admin_commands import ROLE_NAMES, get_admin_level
from relationships import get_display_name


def _mention(uid):
    name = get_display_name(uid) or 'Пользователь'
    return f'[id{uid}|{name}]'


# Награды по уровням (за неделю)
# messages: сколько сообщений за 1 порцию
# gems: сколько камней за порцию
# invites: сколько добавлений за 1 порцию
# invites_gems: сколько камней за порцию добавлений
REWARDS = {
    2: {'messages': 200, 'gems': 2, 'invites': None, 'invites_gems': 0},   # Активист
    3: {'messages': None, 'gems': 0, 'invites': 5, 'invites_gems': 4},     # Рекрутер
    4: {'messages': 200, 'gems': 2, 'invites': 5, 'invites_gems': 4},      # ЗК
    5: {'messages': 200, 'gems': 2, 'invites': 5, 'invites_gems': 4},      # Куратор
    6: {'messages': 200, 'gems': 3, 'invites': 5, 'invites_gems': 5},      # Вершитель
}


def get_user_level(user_id):
    """Возвращает уровень пользователя (глобальный или максимальный локальный)."""
    g = get_global_role(user_id)
    if g in (6, 7):  # <-- ИСПРАВЛЕНО: только Вершитель и Лелуш
        return g
    with db_cursor() as (_, c):
        r = c.execute("SELECT MAX(level) FROM admin_chat_rights WHERE user_id=?", (user_id,)).fetchone()
        if r and r[0]:
            return int(r[0])
    return 0


def check_user_norma(user_id):
    """
    Проверяет, сдал ли пользователь норму по факту (сообщения/добавления).
    Возвращает (ok, reason).
    """
    level = get_user_level(user_id)
    if level < 2:
        return False, 'ты не администратор'

    reward = REWARDS.get(level)
    if not reward:
        return False, f'для уровня {level} норма не определена'

    stats = get_admin_week_stats(user_id)
    messages = stats.get('messages', 0)
    invites = stats.get('invites', 0)

    # Для Активиста — только сообщения
    if level == 2:
        if reward['messages'] and messages >= reward['messages']:
            return True, 'норма по сообщениям выполнена'
        return False, f'нужно {reward["messages"]} сообщений, у тебя {messages}'

    # Для Рекрутера — только добавления
    if level == 3:
        if reward['invites'] and invites >= reward['invites']:
            return True, 'норма по добавлениям выполнена'
        return False, f'нужно {reward["invites"]} добавлений, у тебя {invites}'

    # Для ЗК/Куратора/Вершителя — сообщения ИЛИ добавления
    msg_ok = reward['messages'] and messages >= reward['messages']
    inv_ok = reward['invites'] and invites >= reward['invites']

    if msg_ok and inv_ok:
        return True, 'норма по сообщениям и добавлениям выполнена'
    if msg_ok:
        return True, 'норма по сообщениям выполнена'
    if inv_ok:
        return True, 'норма по добавлениям выполнена'

    return False, (
        f'нужно {reward["messages"]} сообщений (у тебя {messages}) '
        f'или {reward["invites"]} добавлений (у тебя {invites})'
    )


def send_weekly_report(vk, report_peer_id):
    """Отправляет созыв в беседу отчётности и начисляет камни."""
    stats = get_all_admin_week_stats()

    if not stats:
        try:
            vk.messages.send(
                peer_id=report_peer_id,
                random_id=0,
                message='⋅⋆✦──── ⋆⋅Созыв⋅⋆ ────✦⋆⋅\n\nНеделя без отчётов.',
                disable_mentions=True,
            )
        except Exception as e:
            print(f'⚠️ Не удалось отправить созыв: {e}')
        return

    # Группируем по уровням
    by_level = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}

    for user_id, messages, invites, reports, gems_awarded in stats:
        level = get_user_level(user_id)
        if level in by_level:
            by_level[level].append((user_id, messages, invites, reports, gems_awarded))

    lines = ['⋅⋆✦──── ⋆⋅Созыв⋅⋆ ────✦⋆⋅', '']

    role_titles = {
        6: 'Вершитель правосудия',
        5: 'Кураторы',
        4: 'Заместители Куратора',
        3: 'Рекрутеры',
        2: 'Активисты',
        1: 'Стажёры',
    }
    role_emojis = {
        6: '⚖',
        5: '📱',
        4: '⚙',
        3: '🎯',
        2: '⚡',
        1: '🎓',
    }

    for level in (6, 5, 4, 3, 2, 1):
        users = by_level[level]
        if not users:
            continue

        title = role_titles.get(level, 'Без роли')
        emoji = role_emojis.get(level, '👤')
        lines.append(f'⋅⋆✦──── ⋆⋅{emoji} {title}⋅⋆ ────✦⋆⋅')
        lines.append('')

        if level == 1:
            lines.append('Стажёры не участвуют в системе норм.')
            lines.append('')
            continue

        reward = REWARDS.get(level, {})

        for user_id, messages, invites, reports, gems_awarded in users:
            mention = _mention(user_id)
            parts = []
            total_gems = 0

            # Сообщения
            if reward.get('messages') and messages >= reward['messages']:
                count = messages // reward['messages']
                gems = count * reward['gems']
                total_gems += gems
                parts.append(f'+{gems} 💎 за сообщения')

            # Добавления
            if reward.get('invites') and invites >= reward['invites']:
                count = invites // reward['invites']
                gems = count * reward['invites_gems']
                total_gems += gems
                parts.append(f'+{gems} 💎 за добавления')

            # Отчёты (для ЗК и выше)
            if level >= 4 and reports > 0:
                total_gems += reports
                parts.append(f'+{reports} 💎 за отчёты')

            # Начисляем камни
            if total_gems > 0:
                update_gems(user_id, total_gems)
                parts.append(f'итого: **{total_gems} 💎**')
                lines.append(f'{mention} — ' + ', '.join(parts) + '.')
            else:
                lines.append(f'{mention} — норма не сдана.')

        lines.append('')

    # Обнуляем статистику
    reset_admin_week_stats()

    text = '\n'.join(lines)

    # VK лимит 4096, если больше — режем
    if len(text) > 4000:
        text = text[:3950] + '\n\n... (сообщение обрезано)'

    try:
        vk.messages.send(
            peer_id=report_peer_id,
            random_id=0,
            message=text,
            disable_mentions=True,
        )
    except Exception as e:
        print(f'⚠️ Не удалось отправить созыв: {e}')