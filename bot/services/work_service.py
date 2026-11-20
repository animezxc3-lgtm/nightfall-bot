"""
Система работы и профессий.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from bot.core import database as db

PROFESSIONS: dict[str, dict] = {
    "шлюха": {
        "name": "🍆 Шлюха",
        "levels": [
            "Подзаборная", "Работница вокзала", "Элитная путана",
            "Содержанка", "Любовница олигарха", "Онлифанс модель",
        ],
    },
    "алкаш": {
        "name": "🍺 Алкаш",
        "levels": [
            "Собутыльник", "Постоянный клиент", "Знаток «Боярышника»",
            "Легенда двора", "Душа компании", "Король пивной",
        ],
    },
    "тиммейт": {
        "name": "🎯 Тиммейт из ада",
        "levels": [
            "Рандом", "Токсик", "АФК", "Фидлер", "ММР-судья", "Счёт 4/11",
        ],
    },
    "врач": {
        "name": "🩺 Врач",
        "levels": [
            "Медик-стажёр", "Интерн", "Доктор",
            "Специалист", "Ведущий доктор", "Главный доктор",
        ],
    },
    "вор": {
        "name": "🥷 Вор",
        "levels": [
            "Карманник", "Домушник", "Грабитель",
            "Профессионал", "Авторитет", "Вор в законе",
        ],
    },
}

SALARIES = [10_000, 20_000, 30_000, 40_000, 50_000, 60_000]
PROMOTION_DAYS = 14
POWER_PER_WORK = 15
MAX_LEVEL = len(SALARIES) - 1


def get_level_name(job_key: str, level: int) -> str:
    levels = PROFESSIONS.get(job_key, {}).get("levels", [])
    if 0 <= level < len(levels):
        return levels[level]
    return "Неизвестная ступень"


def get_salary(level: int) -> int:
    if 0 <= level < len(SALARIES):
        return SALARIES[level]
    return 0


def _get_salary_multiplier(user_id: int) -> float:
    row = db.get_user(user_id)
    if not row:
        return 1.0
    return float(row["salary_multiplier"] or 1.0)


def work(user_id: int) -> tuple[str, Optional[str]]:
    """Возвращает (основной_текст, текст_повышения_или_None)."""
    user = db.get_user(user_id)
    if not user:
        return "Профиль не найден.", None

    job = user["job"] or "Отсутствует"
    level = int(user["job_level"] or 0)
    exp = int(user["job_exp"] or 0)
    last = user["job_last_work"]

    if job == "Отсутствует" or job not in PROFESSIONS:
        return "Ты безработный. Используй `лл устроиться`.", None

    today = date.today().isoformat()
    if last and str(last)[:10] == today:
        return "Ты уже работал сегодня. Приходи завтра!", None

    base = get_salary(level)
    multiplier = _get_salary_multiplier(user_id)
    salary = int(base * multiplier)

    db.update_user_field(user_id, "salary", salary)
    db.update_coins(user_id, salary)
    db.update_power(user_id, POWER_PER_WORK)

    exp += 1
    new_level = level
    promoted = False
    if level < MAX_LEVEL and exp >= PROMOTION_DAYS:
        new_level = level + 1
        exp = 0
        promoted = True

    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "UPDATE users SET work_days = COALESCE(work_days, 0) + 1, "
            "job_exp = ?, job_level = ?, job_last_work = ? WHERE user_id = ?",
            (exp, new_level, today, user_id),
        )

    text = "отработал рабочий день."
    promoted_text = None
    if promoted:
        promoted_text = f"повышен до {get_level_name(job, new_level)}!"
    return text, promoted_text


def hire(user_id: int, profession_key: str) -> str:
    user = db.get_user(user_id)
    if not user:
        return "Профиль не найден."

    current = user["job"] or "Отсутствует"
    if current != "Отсутствует" and current in PROFESSIONS:
        name = PROFESSIONS[current]["name"]
        return f"Ты уже работаешь: {name}. Сначала используй `лл уволиться`."

    if profession_key not in PROFESSIONS:
        return "Такой профессии нет."

    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "UPDATE users SET job = ?, job_level = 0, job_exp = 0, "
            "job_last_work = NULL, salary = 0 WHERE user_id = ?",
            (profession_key, user_id),
        )
    return f"устроился на работу {PROFESSIONS[profession_key]['name']}."


def fire(user_id: int) -> str:
    user = db.get_user(user_id)
    if not user:
        return "Профиль не найден."

    job = user["job"] or "Отсутствует"
    if job == "Отсутствует" or job not in PROFESSIONS:
        return "Ты и так безработный."

    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "UPDATE users SET job = 'Отсутствует', job_level = 0, job_exp = 0, "
            "job_last_work = NULL, salary = 0 WHERE user_id = ?",
            (user_id,),
        )
    return "Ты уволился. Профессия, ступень и прогресс сброшены."


def job_stats(target_id: int, viewer_id: int | None = None) -> Optional[str]:
    user = db.get_user(target_id)
    if not user:
        return None

    job = user["job"] or "Отсутствует"
    level = int(user["job_level"] or 0)
    exp = int(user["job_exp"] or 0)

    if job == "Отсутствует" or job not in PROFESSIONS:
        if viewer_id is not None and viewer_id == target_id:
            return "У вас нет работы."
        return None

    job_name = PROFESSIONS[job]["name"]
    level_name = get_level_name(job, level)
    base = get_salary(level)
    mult = _get_salary_multiplier(target_id)
    actual = int(base * mult)

    return (
        f"💼 {job_name}\n"
        f"📊 Ступень: {level_name} ({level + 1}/{MAX_LEVEL + 1})\n"
        f"💰 Зарплата: {actual:,} 🪙\n"
        f"📈 Прогресс до повышения: {exp}/{PROMOTION_DAYS}\n"
        f"⚡ За смену: +{POWER_PER_WORK} силы Гиаса"
    ).replace(",", " ")
