"""Weekly task engine for Lelouch Bot.

Two tasks are assigned per user for each Monday-starting week (Moscow time).
RP milestones: 3/7/15/25 actions with rewards 3,000 / 7,000 / 12,000+2 gems / 20,000+4 gems.
"""
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database import (
    get_user,
    get_messages_stats,
    get_weekly_tasks,
    save_weekly_tasks,
    weekly_task_is_completed,
    complete_weekly_task,
    update_coins,
    update_gems,
    get_task_progress,
    set_task_progress,
)

MOSCOW = ZoneInfo("Europe/Moscow")

RP_THRESHOLDS = [
    {"id": "rp_3", "title": "Выполнить 3 RP-команды", "kind": "rp", "goal": 3, "coins": 3000, "gems": 0, "difficulty": 1},
    {"id": "rp_7", "title": "Выполнить 7 RP-команд", "kind": "rp", "goal": 7, "coins": 7000, "gems": 0, "difficulty": 2},
    {"id": "rp_15", "title": "Выполнить 15 RP-команд", "kind": "rp", "goal": 15, "coins": 12000, "gems": 2, "difficulty": 3},
    {"id": "rp_25", "title": "Выполнить 25 RP-команд", "kind": "rp", "goal": 25, "coins": 20000, "gems": 4, "difficulty": 4},
]

OTHER_TASKS = [
    {"id": "messages_20", "title": "Написать 20 сообщений за неделю", "kind": "messages", "goal": 20, "coins": 5000, "gems": 0, "difficulty": 1},
    {"id": "messages_50", "title": "Написать 50 сообщений за неделю", "kind": "messages", "goal": 50, "coins": 9000, "gems": 1, "difficulty": 2},
    {"id": "work_3", "title": "Отработать 3 дня", "kind": "work", "goal": 3, "coins": 7000, "gems": 0, "difficulty": 1},
    {"id": "work_7", "title": "Отработать 7 дней", "kind": "work", "goal": 7, "coins": 14000, "gems": 2, "difficulty": 3},
    {"id": "casino_3", "title": "Сыграть в казино 3 раза", "kind": "casino", "goal": 3, "coins": 4000, "gems": 0, "difficulty": 1},
    {"id": "casino_5", "title": "Сыграть в казино 5 раз", "kind": "casino", "goal": 5, "coins": 8000, "gems": 1, "difficulty": 2},
    {"id": "transfer_1", "title": "Передать монеты другому участнику", "kind": "transfer", "goal": 1, "coins": 5000, "gems": 0, "difficulty": 1},
    {"id": "property_1", "title": "Купить один предмет имущества", "kind": "property", "goal": 1, "coins": 6000, "gems": 0, "difficulty": 2},
]

TASK_POOL = RP_THRESHOLDS + OTHER_TASKS


def week_key(now=None):
    now = now or datetime.now(MOSCOW).date()
    if isinstance(now, datetime):
        now = now.date()
    return (now - timedelta(days=now.weekday())).isoformat()


def _applicable(user_id):
    user = get_user(user_id)
    if not user:
        return []
    stats = get_messages_stats(user_id)
    result = []
    for task in TASK_POOL:
        if task["kind"] == "work" and (not user[6] or user[6] == "Отсутствует"):
            continue
        if task["difficulty"] == 4 and stats.get("total", 0) < 50:
            continue
        result.append(dict(task))
    return result


def ensure_weekly_tasks(user_id):
    key = week_key()
    existing = get_weekly_tasks(user_id)
    if existing and existing["week_key"] == key:
        return existing

    pool = _applicable(user_id)
    if not pool:
        return None

    random.shuffle(pool)
    chosen = []
    for task in pool:
        if len(chosen) >= 2:
            break
        if chosen and task["kind"] == chosen[0]["kind"]:
            continue
        chosen.append(task)

    for task in pool:
        if len(chosen) >= 2:
            break
        if task not in chosen:
            chosen.append(task)

    if len(chosen) < 2:
        chosen = pool[:2]
    if len(chosen) < 2:
        return None

    save_weekly_tasks(user_id, key, chosen[0], chosen[1])
    return get_weekly_tasks(user_id)


def format_tasks(user_id):
    data = ensure_weekly_tasks(user_id)
    if not data:
        return "Сначала создай профиль, чтобы получать задания."

    lines = ["📋 Еженедельные задания", ""]
    for index, (task, done) in enumerate(zip(data["tasks"], data["completed"]), 1):
        status = "✅ Выполнено" if done else f"🎯 Цель: {task['goal']}"
        reward = f"{task['coins']:,} 🪙".replace(",", " ")
        if task.get("gems"):
            reward += f" + 💎 {task['gems']}"
        progress = task["goal"] if done else min(_progress(user_id, task), task["goal"])
        if not done:
            status += f" | Прогресс: {progress}/{task['goal']}"
        lines.append(f"{index}. {task['title']}\n{status} | Награда: {reward}")
    lines.append("")
    lines.append("Задания обновляются раз в неделю.")
    return "\n".join(lines)


def _progress(user_id, task):
    if task["kind"] == "messages":
        return int(get_messages_stats(user_id).get("week", 0))
    if task["kind"] == "work":
        return get_task_progress(user_id, week_key(), task["id"])
    if task["kind"] in ("rp", "casino", "transfer", "property"):
        return get_task_progress(user_id, week_key(), task["id"])
    return 0


def event(user_id, kind, amount=1, data=None):
    data = ensure_weekly_tasks(user_id)
    if not data:
        return []

    awarded = []
    for slot, task in enumerate(data["tasks"]):
        if data["completed"][slot] or task["kind"] != kind:
            continue

        if kind == "messages":
            progress = _progress(user_id, task)
        else:
            progress = get_task_progress(user_id, data["week_key"], task["id"]) + int(amount)
            set_task_progress(user_id, data["week_key"], task["id"], progress)

        if progress < task["goal"]:
            continue

        update_coins(user_id, int(task["coins"]))
        if task.get("gems"):
            update_gems(user_id, int(task["gems"]))
        complete_weekly_task(user_id, slot)
        awarded.append(task)
    return awarded


def notify_task_rewards(vk, peer_id, user_id, awarded):
    if not awarded:
        return
    try:
        from relationships import get_display_name
        name = get_display_name(user_id) or "Участник"
    except Exception:
        name = "Участник"
    for task in awarded:
        reward = f"{task['coins']:,} 🪙".replace(",", " ")
        if task.get("gems"):
            reward += f" + 💎 {task['gems']}"
        message = (
            f"🎯 [id{user_id}|{name}] выполнил задание «{task['title']}». "
            f"Награда: {reward}."
        )
        try:
            vk.messages.send(
                peer_id=peer_id,
                random_id=0,
                message=message,
                disable_mentions=True,
            )
        except Exception as e:
            print(f"⚠️ Не удалось отправить награду за задание: {e}")
