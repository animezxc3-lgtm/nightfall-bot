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
    salary = int(base_salary * multiplier) # Явно переводим в int

    set_salary(user_id, salary)
    update_coins(user_id, salary)
    update_power(user_id, POWER_PER_WORK)  # идёт в power (Сила Гиаса)

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