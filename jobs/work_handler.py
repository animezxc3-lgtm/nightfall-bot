from datetime import datetime
from jobs.professions import PROFESSIONS, get_level_name, get_salary, get_max_level, PROMOTION_DAYS
from database import (
    update_coins, update_power, update_job_field, get_user,
    set_salary, increment_work_days, get_salary_multiplier
)

POWER_PER_WORK = 15


def work(user_id, *_):
    """Возвращает (text, promoted_text_or_None)."""
    user = get_user(user_id)
    if not user:
        return 'Профиль не найден.', None

    # 6 job | 7 salary | 8 work_days | 18 job_level | 19 job_exp | 20 job_last_work
    job = user[6]
    level = user[18] or 0
    exp = user[19] or 0
    last = user[20]

    if job == 'Отсутствует' or job not in PROFESSIONS:
        return 'Ты безработный. Используй `лл устроиться`.', None

    today = datetime.now().date()
    if last and str(last) == str(today):
        return 'Ты уже работал сегодня. Приходи завтра!', None

    base_salary = get_salary(level)
    multiplier = get_salary_multiplier(user_id) or 1.0
    salary = int(base_salary * multiplier)

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
    # 6 — job
    if user[6] != 'Отсутствует' and user[6] in PROFESSIONS:
        return f'Ты уже работаешь: {PROFESSIONS[user[6]]["name"]}. Сначала используй `лл уволиться`.'
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
    # 6 — job
    if user[6] == 'Отсутствует' or user[6] not in PROFESSIONS:
        return 'Ты и так безработный.'

    update_job_field(user_id, 'job_name', 'Отсутствует')
    update_job_field(user_id, 'level', 0)
    update_job_field(user_id, 'exp', 0)
    update_job_field(user_id, 'last_work', None)
    set_salary(user_id, 0)

    return 'Ты уволился. Профессия, ступень и прогресс сброшены.'


def job_stats(target_id, viewer_id=None):
    """Статистика работы для команды лл работа."""
    user = get_user(target_id)
    if not user:
        return None

    # 6 job | 18 job_level | 19 job_exp
    job = user[6]
    level = user[18] or 0
    exp = user[19] or 0

    if job == 'Отсутствует' or job not in PROFESSIONS:
        if viewer_id is not None and viewer_id == target_id:
            return 'У вас нет работы.'
        return None

    job_name = PROFESSIONS[job]['name']
    level_name = get_level_name(job, level)
    base_salary = get_salary(level)
    multiplier = get_salary_multiplier(target_id) or 1.0
    actual_salary = int(base_salary * multiplier)

    return {
        'job_name': job_name,
        'level_name': level_name,
        'salary': actual_salary,
        'base_salary': base_salary,
        'multiplier': multiplier,
        'days': exp,
        'power_per_work': POWER_PER_WORK,
    }