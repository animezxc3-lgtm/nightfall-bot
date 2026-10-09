from datetime import datetime
from jobs.professions import PROFESSIONS, get_level_name, get_salary, get_max_level, PROMOTION_DAYS
from database import update_coins, update_power, update_job_field, get_user, set_salary, increment_work_days

POWER_PER_WORK = 15


def work(user_id, *_):
    """Возвращает (text, promoted_text_or_None)."""
    user = get_user(user_id)
    if not user:
        return 'Профиль не найден.', None

    job = user[5]
    level = user[17] or 0
    exp = user[18] or 0
    last = user[19]

    if job == 'Отсутствует' or job not in PROFESSIONS:
        return 'Ты безработный. Используй `лл устроиться`.', None

    today = datetime.now().date()
    if last and str(last) == str(today):
        return 'Ты уже работал сегодня. Приходи завтра!', None

    salary = get_salary(level)
    set_salary(user_id, salary)
    update_coins(user_id, salary)
    update_power(user_id, POWER_PER_WORK)

    exp += 1
    new_level = level
    promoted = False

    if level < get_max_level() and exp >= PROMOTION_DAYS:
        new_level = level + 1
        exp = 0
        promoted = True

    increment_work_days(user_id)
    update_job_field(user_id, 'exp', exp)
    update_job_field(user_id, 'level', new_level)
    update_job_field(user_id, 'last_work', today)

    text = 'отработал рабочий день.'

    promoted_text = None
    if promoted:
        promoted_text = f'повышен до {get_level_name(job, new_level)}!'

    return text, promoted_text


def hire(user_id, profession_key, *_):
    user = get_user(user_id)
    if not user:
        return 'Профиль не найден.'
    if user[5] != 'Отсутствует' and user[5] in PROFESSIONS:
        return f'Ты уже работаешь: {PROFESSIONS[user[5]]["name"]}. Сначала используй `лл уволиться`.'
    if profession_key not in PROFESSIONS:
        return 'Такой профессии нет.'

    update_job_field(user_id, 'job_name', profession_key)
    update_job_field(user_id, 'level', 0)
    update_job_field(user_id, 'exp', 0)
    update_job_field(user_id, 'last_work', None)

    return f'устроился на работу {PROFESSIONS[profession_key]["name"]}.'


def fire(user_id, *_):
    user = get_user(user_id)
    if not user:
        return 'Профиль не найден.'
    if user[5] == 'Отсутствует' or user[5] not in PROFESSIONS:
        return 'Ты и так безработный.'

    update_job_field(user_id, 'job_name', 'Отсутствует')
    update_job_field(user_id, 'level', 0)
    update_job_field(user_id, 'exp', 0)
    update_job_field(user_id, 'last_work', None)

    return 'Ты уволился. Профессия, ступень и прогресс сброшены.'


def job_stats(target_id, viewer_id=None):
    """Статистика работы для команды лл работа."""
    user = get_user(target_id)
    if not user:
        return None

    job = user[5]
    level = user[17] or 0
    exp = user[18] or 0

    if job == 'Отсутствует' or job not in PROFESSIONS:
        if viewer_id is not None and viewer_id == target_id:
            return 'У вас нет работы.'
        return None  # значит «У пользователя нет работы» — обработает вызывающий

    job_name = PROFESSIONS[job]['name']
    level_name = get_level_name(job, level)
    salary = get_salary(level)

    return {
        'job_name': job_name,
        'level_name': level_name,
        'salary': salary,
        'days': exp,
    }