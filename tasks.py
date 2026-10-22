"""Daily task system for Lelouch Bot.

Ordinary tasks are tracked globally across chats. Administrative tasks are tracked
inside the conversation where they were assigned. Tasks expire at midnight Moscow
 time. The old weekly task tables are intentionally left in place for data safety,
 but are no longer used by this module.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import random

from database import db_cursor, get_user

MOSCOW = ZoneInfo("Europe/Moscow")

# 20,000 coins -> 10 Geass power; 25,000 coins -> 20 Geass power.
ORDINARY_TASKS = [
    {"id": "messages_50", "title": "Активность", "description": "Написать 50 сообщений", "kind": "messages", "goal": 50, "coins": 20000, "power": 10, "gems": 0},
    {"id": "messages_100", "title": "Общение", "description": "Написать 100 сообщений", "kind": "messages", "goal": 100, "coins": 20000, "power": 10, "gems": 0},
    {"id": "messages_150", "title": "Разговор", "description": "Написать 150 сообщений", "kind": "messages", "goal": 150, "coins": 25000, "power": 20, "gems": 0},
    {"id": "rp_3", "title": "Ролевая игра", "description": "Использовать RP-команды 3 раза", "kind": "rp", "goal": 3, "coins": 20000, "power": 10, "gems": 0},
    {"id": "rp_5", "title": "Отыгрыш", "description": "Использовать RP-команды 5 раз", "kind": "rp", "goal": 5, "coins": 20000, "power": 10, "gems": 0},
    {"id": "rp_8", "title": "Сцена", "description": "Использовать RP-команды 8 раз", "kind": "rp", "goal": 8, "coins": 25000, "power": 20, "gems": 0},
    {"id": "profile", "title": "Профиль", "description": "Открыть свой профиль", "kind": "profile", "goal": 1, "coins": 20000, "power": 10, "gems": 0},
    {"id": "balance", "title": "Баланс", "description": "Проверить баланс", "kind": "balance", "goal": 1, "coins": 20000, "power": 10, "gems": 0},
    {"id": "shop", "title": "Магазин", "description": "Открыть магазин", "kind": "shop", "goal": 1, "coins": 20000, "power": 10, "gems": 0},
    {"id": "activity", "title": "Активность", "description": "Проверить свою активность", "kind": "activity", "goal": 1, "coins": 20000, "power": 10, "gems": 0},
    {"id": "other_profile", "title": "Знакомство", "description": "Открыть профиль другого участника", "kind": "other_profile", "goal": 1, "coins": 20000, "power": 10, "gems": 0},
    {"id": "transfer_1000", "title": "Перевод", "description": "Передать другому участнику 1 000 монет или больше", "kind": "transfer", "goal": 1, "coins": 20000, "power": 10, "gems": 0},
    {"id": "partner_rp", "title": "Партнёр", "description": "Использовать RP-команду на своём партнёре", "kind": "partner_rp", "goal": 1, "coins": 20000, "power": 10, "gems": 0},
]

ADMIN_TASKS = [
    {"id": "admin_messages_30", "title": "Присутствие", "description": "Написать 30 сообщений в беседе", "kind": "admin_messages", "goal": 30, "coins": 20000, "power": 10, "gems": 1},
    {"id": "admin_messages_50", "title": "Общение", "description": "Написать 50 сообщений в беседе", "kind": "admin_messages", "goal": 50, "coins": 20000, "power": 10, "gems": 1},
    {"id": "admin_messages_100", "title": "Активность", "description": "Написать 100 сообщений в беседе", "kind": "admin_messages", "goal": 100, "coins": 25000, "power": 20, "gems": 2},
    {"id": "admin_invite_1", "title": "Новый участник", "description": "Добавить 1 участника в беседу", "kind": "admin_invite", "goal": 1, "coins": 20000, "power": 10, "gems": 1},
    {"id": "admin_invite_2", "title": "Пополнение беседы", "description": "Добавить 2 участников в беседу", "kind": "admin_invite", "goal": 2, "coins": 20000, "power": 10, "gems": 1},
    {"id": "admin_invite_3", "title": "Новые лица", "description": "Добавить 3 участников в беседу", "kind": "admin_invite", "goal": 3, "coins": 25000, "power": 20, "gems": 2},
]


def _today():
    return datetime.now(MOSCOW).date().isoformat()


def _expire_old_tasks(c):
    c.execute("UPDATE daily_task_instances SET status='expired' WHERE status='active' AND task_date < ?", (_today(),))


def get_extra_task_slots(user_id):
    with db_cursor() as (_, c):
        row = c.execute("SELECT extra_slots FROM daily_task_slots WHERE user_id=?", (int(user_id),)).fetchone()
    return int(row[0]) if row else 0


def buy_extra_task_slot(user_id, slot_number):
    """Permanently buy slot 2 or 3. Caller handles payment."""
    slot_number = int(slot_number)
    if slot_number not in (2, 3):
        return False, "Такого слота нет."
    with db_cursor(True) as (_, c):
        c.execute("INSERT INTO daily_task_slots(user_id, extra_slots) VALUES(?,0) ON CONFLICT(user_id) DO NOTHING", (int(user_id),))
        row = c.execute("SELECT extra_slots FROM daily_task_slots WHERE user_id=?", (int(user_id),)).fetchone()
        current = int(row[0] or 0)
        needed = slot_number - 1
        if current >= needed:
            return False, "Этот слот уже открыт."
        if needed != current + 1:
            return False, "Сначала открой предыдущий слот."
        c.execute("UPDATE daily_task_slots SET extra_slots=? WHERE user_id=?", (needed, int(user_id)))
    return True, f"Слот {slot_number} открыт навсегда."


def _scope_for_user(user_id, peer_id):
    try:
        from admin_commands import get_admin_level
        if peer_id and int(peer_id) > 2000000000 and get_admin_level(int(user_id), int(peer_id)) >= 1:
            return int(peer_id), ADMIN_TASKS
    except Exception as exc:
        print(f"[TASKS] Не удалось проверить админскую роль user={user_id}: {exc}")
    return 0, ORDINARY_TASKS


def assign_task(user_id, peer_id):
    if not get_user(user_id):
        return {"error": "Сначала создай профиль, чтобы получать задания."}
    scope_peer_id, pool = _scope_for_user(user_id, peer_id)
    with db_cursor(True) as (_, c):
        _expire_old_tasks(c)
        c.execute("INSERT INTO daily_task_slots(user_id, extra_slots) VALUES(?,0) ON CONFLICT(user_id) DO NOTHING", (int(user_id),))
        extra = c.execute("SELECT extra_slots FROM daily_task_slots WHERE user_id=?", (int(user_id),)).fetchone()
        max_active = 1 + int(extra[0] or 0)
        active = c.execute("SELECT COUNT(*) FROM daily_task_instances WHERE user_id=? AND status='active' AND task_date=?", (int(user_id), _today())).fetchone()[0]
        if active >= max_active:
            return {"error": f"У тебя заняты все слоты заданий ({active}/{max_active}). Выполни одно или дождись следующего дня."}
        used_rows = c.execute("SELECT task_id FROM daily_task_instances WHERE user_id=? AND task_date=? AND scope_peer_id=?", (int(user_id), _today(), scope_peer_id)).fetchall()
        used = {r[0] for r in used_rows}
        available = [dict(t) for t in pool if t["id"] not in used]
        if not available:
            return {"error": "На сегодня задания этого типа закончились. Попробуй завтра."}
        task = random.choice(available)
        c.execute("""INSERT INTO daily_task_instances
            (user_id, task_date, scope_peer_id, task_id, title, description, kind, goal, coins, power, gems, progress, status)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,0,'active')""",
            (int(user_id), _today(), scope_peer_id, task["id"], task["title"], task["description"], task["kind"], task["goal"], task["coins"], task["power"], task["gems"]))
        task["instance_id"] = c.lastrowid
        task["scope_peer_id"] = scope_peer_id
        task["progress"] = 0
        task["status"] = "active"
    return {"task": task, "scope_peer_id": scope_peer_id, "max_active": max_active}


def _format_reward(task):
    parts = [f"{int(task['coins']):,}".replace(",", " ") + " монет", f"{int(task['power'])} силы Гиасса"]
    if int(task.get("gems", 0)) > 0:
        parts.append(f"{int(task['gems'])} камень души" if int(task['gems']) == 1 else f"{int(task['gems'])} камня души")
    return " + ".join(parts)


def format_assigned_task(user_id, peer_id):
    result = assign_task(user_id, peer_id)
    if result.get("error"):
        return result["error"]
    task = result["task"]
    try:
        from relationships import get_display_name
        name = get_display_name(user_id) or "Участник"
    except Exception:
        name = "Участник"
    return (f"[id{user_id}|{name}], ваше задание на сегодня:\n"
            f"{task['title']}\n{task['description']}\n"
            f"Награда: {_format_reward(task)}\n"
            f"Прогресс: 0/{task['goal']}\n"
            f"Срок выполнения — до конца дня.")


def format_tasks(user_id, peer_id=None):
    with db_cursor(True) as (_, c):
        _expire_old_tasks(c)
        rows = c.execute("""SELECT task_date, scope_peer_id, title, description, goal, coins, power, gems, progress, status
            FROM daily_task_instances WHERE user_id=? AND task_date=? AND (scope_peer_id=0 OR scope_peer_id=?)
            ORDER BY id""", (int(user_id), _today(), int(peer_id or 0))).fetchall()
    if not rows:
        return "На сегодня заданий нет. Напиши `лл задание`, чтобы получить первое."
    lines = ["📋 Твои задания на сегодня:"]
    for i, row in enumerate(rows, 1):
        _, scope, title, description, goal, coins, power, gems, progress, status = row
        if status == "completed":
            state = "✅ Выполнено"
        elif status == "expired":
            state = "⌛ Истекло"
        else:
            state = f"Прогресс: {min(int(progress), int(goal))}/{goal}"
        task = {"coins": coins, "power": power, "gems": gems}
        lines.append(f"{i}. {title}\n{description}\n{state}\nНаграда: {_format_reward(task)}")
    slots = get_extra_task_slots(user_id) + 1
    with db_cursor() as (_, c):
        active = c.execute("SELECT COUNT(*) FROM daily_task_instances WHERE user_id=? AND task_date=? AND status='active'", (int(user_id), _today())).fetchone()[0]
    lines.append(f"\nАктивные слоты: {active}/{slots}. Дополнительные слоты навсегда открываются в `лл вип магазин`.")
    return "\n\n".join(lines)


def event(user_id, kind, amount=1, data=None, peer_id=None):
    """Record an event against today's active tasks and award completed tasks once."""
    data = data or {}
    today = _today()
    awarded = []
    with db_cursor(True) as (_, c):
        _expire_old_tasks(c)
        rows = c.execute("""SELECT id, scope_peer_id, task_id, title, description, kind, goal, coins, power, gems, progress
            FROM daily_task_instances WHERE user_id=? AND task_date=? AND status='active'""", (int(user_id), today)).fetchall()
        for row in rows:
            instance_id, scope, task_id, title, description, task_kind, goal, coins, power, gems, progress = row
            if task_kind == "messages":
                matches = kind == "messages" and int(scope) == 0
            elif task_kind == "admin_messages":
                matches = kind == "messages" and int(scope) == int(peer_id or 0)
            elif task_kind == "admin_invite":
                matches = kind == "invite" and int(scope) == int(peer_id or 0)
            else:
                matches = task_kind == kind and int(scope) == 0
            if not matches:
                continue
            if task_kind == "transfer" and int(data.get("transfer_amount", amount) or 0) < 1000:
                continue
            new_progress = int(progress) + max(1, int(amount or 1))
            if new_progress >= int(goal):
                updated = c.execute("UPDATE daily_task_instances SET progress=?, status='completed' WHERE id=? AND status='active'", (new_progress, instance_id)).rowcount
                if not updated:
                    continue
                c.execute("UPDATE users SET coins=COALESCE(coins,0)+?, power=COALESCE(power,0)+?, soul_gems=COALESCE(soul_gems,0)+? WHERE user_id=?", (int(coins), int(power), int(gems), int(user_id)))
                awarded.append({"id": task_id, "title": title, "description": description, "coins": int(coins), "power": int(power), "gems": int(gems)})
            else:
                c.execute("UPDATE daily_task_instances SET progress=? WHERE id=? AND status='active'", (new_progress, instance_id))
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
        reward = _format_reward(task)
        message = f"[id{user_id}|{name}], вы выполнили задание «{task['title']}». Ваша награда: {reward}."
        try:
            vk.messages.send(peer_id=peer_id, random_id=0, message=message, disable_mentions=True)
        except Exception as exc:
            print(f"⚠️ Не удалось отправить награду за задание: {exc}")
