from datetime import datetime
from jobs.professions import PROFESSIONS, get_level_name, get_salary, get_max_level, PROMOTION_DAYS
from database import update_coins, update_power, update_job_field, get_user, set_salary, increment_work_days

POWER_PER_WORK = 15


def work(user_id, *_):
    user = get_user(user_id)
    if not user:
        return 'Профиль не найден.'
    job = user[5]
    level = user[17] or 0
    exp = user[18] or 0
    last = user[19]

    if job == 'Отсутствует' or job not in PROFESSIONS:
        return 'Ты безработный. Используй `лл устроиться`.'

    today = datetime.now().date()
    if last and str(last) == str(today):
        return 'Ты уже работал сегодня. Приходи завтра!'

    salary = get_salary(level)
    set_salary(user_id, salary)
    update_coins(user_id, salary)
    update_power(user_id, POWER_PER_WORK)

    exp += 1
    new_level = level
    if level < get_max_level() and exp >= PROMOTION_DAYS:
        new_level = level + 1
        exp = 0

    increment_work_days(user_id)
    update_job_field(user_id, 'exp', exp)
    update_job_field(user_id, 'level', new_level)
    update_job_field(user_id, 'last_work', today)

    from response_context import get_user_id
    from relationships import get_display_name

    actor = get_user_id()
    name = get_display_name(actor) or 'Пользователь'
    return f'[id{actor}|{name}] отработал рабочий день.'


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

    return f"Ты устроился на работу {PROFESSIONS[profession_key]['name']}! Повышение — каждые 14 отработанных дней."


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