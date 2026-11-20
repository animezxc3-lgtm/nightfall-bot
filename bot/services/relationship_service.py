"""
Отношения, брак, семья.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from bot.core import database as db
from bot.utils.vk_helpers import user_mention

MAX_CHILDREN = 5


def _ensure_relationship_row(user_id: int) -> None:
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT OR IGNORE INTO relationships (user_id) VALUES (?)",
            (user_id,),
        )


def get_partner_id(user_id: int) -> Optional[int]:
    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT partner_id FROM relationships WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return int(row["partner_id"]) if row and row["partner_id"] else None


def get_family_surname(user_id: int) -> str:
    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT family_surname FROM relationships WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return (row["family_surname"] or "") if row else ""


def get_display_name(user_id: int) -> Optional[str]:
    u = db.get_user(user_id)
    if not u:
        return None
    base = u["nickname"] or (u["name"].split()[0] if u["name"] else f"id{user_id}")
    surname = get_family_surname(user_id)
    return f"{base} {surname}".strip() if surname else base


def get_children(user_id: int) -> list[int]:
    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT child_id FROM family_children WHERE parent_id = ? ORDER BY id",
            (user_id,),
        )
        return [int(r["child_id"]) for r in cur.fetchall()]


def get_parents(user_id: int) -> list[int]:
    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT parent_id FROM family_children WHERE child_id = ? ORDER BY id",
            (user_id,),
        )
        return [int(r["parent_id"]) for r in cur.fetchall()]


def start_relationship(uid: int, target: int) -> tuple[bool, str]:
    if not target or target == uid:
        return False, "Нельзя начать отношения с самим собой."
    if not db.user_exists(uid) or not db.user_exists(target):
        return False, "У одного из пользователей ещё нет профиля."
    if get_partner_id(uid) or get_partner_id(target):
        return False, "Один из пользователей уже состоит в отношениях."

    _ensure_relationship_row(uid)
    _ensure_relationship_row(target)

    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT OR REPLACE INTO relationship_proposals "
            "(target_id, proposer_id, created_at) VALUES (?, ?, ?)",
            (target, uid, datetime.now().isoformat(timespec="seconds")),
        )
    return True, ""


def accept_relationship(target: int) -> str:
    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT proposer_id FROM relationship_proposals WHERE target_id = ?",
            (target,),
        )
        row = cur.fetchone()
    if not row:
        return "Для тебя нет действующего предложения отношений."

    proposer = int(row["proposer_id"])
    if get_partner_id(target) or get_partner_id(proposer):
        with db.db_cursor(commit=True) as (_, cur):
            cur.execute("DELETE FROM relationship_proposals WHERE target_id = ?", (target,))
        return "Предложение больше недействительно."

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db.db_cursor(commit=True) as (_, cur):
        for a, b in ((proposer, target), (target, proposer)):
            _ensure_relationship_row(a)
            cur.execute(
                "UPDATE relationships SET partner_id = ?, relationship_since = ? WHERE user_id = ?",
                (b, now, a),
            )
        cur.execute("DELETE FROM relationship_proposals WHERE target_id = ?", (target,))
    return "❤️ Согласие принято! Теперь вы состоите в отношениях."


def reject_relationship(target: int) -> str:
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM relationship_proposals WHERE target_id = ?", (target,))
        if cur.rowcount == 0:
            return "Предложение больше недействительно."
    return "💔 Предложение отклонено."


def end_relationship(uid: int) -> str:
    partner = get_partner_id(uid)
    if not partner:
        return "У тебя нет партнёра."

    with db.db_cursor() as (_, cur):
        cur.execute("SELECT married FROM relationships WHERE user_id = ?", (uid,))
        row = cur.fetchone()
    if row and row["married"]:
        return "Вы состоите в браке. Используйте команду `лл развод`."

    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "UPDATE relationships SET partner_id = NULL, married = 0, "
            "family_surname = '', relationship_since = NULL WHERE user_id IN (?, ?)",
            (uid, partner),
        )
    return "💔 Вы больше не состоите в отношениях."


def divorce(uid: int) -> str:
    partner = get_partner_id(uid)
    if not partner:
        return "У тебя нет супруга/супруги."

    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "UPDATE relationships SET partner_id = NULL, married = 0, "
            "family_surname = '', relationship_since = NULL WHERE user_id IN (?, ?)",
            (uid, partner),
        )
    return "💔 Вы развелись. Брак и фамилия семьи расторгнуты."


def propose_marriage(uid: int, target: int, surname: str) -> tuple[bool, str]:
    if get_partner_id(uid) != target or get_partner_id(target) != uid:
        return False, "Сначала начните отношения друг с другом."
    if not 1 <= len(surname) <= 30:
        return False, "Фамилия должна быть от 1 до 30 символов."

    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT OR REPLACE INTO marriage_proposals "
            "(target_id, proposer_id, surname, created_at) VALUES (?, ?, ?, ?)",
            (target, uid, surname, datetime.now().isoformat(timespec="seconds")),
        )
    return True, ""


def accept_marriage(target: int) -> str:
    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT proposer_id, surname FROM marriage_proposals WHERE target_id = ?",
            (target,),
        )
        row = cur.fetchone()
    if not row:
        return "У тебя нет ожидающего предложения брака."

    proposer, surname = int(row["proposer_id"]), row["surname"]
    if get_partner_id(target) != proposer or get_partner_id(proposer) != target:
        with db.db_cursor(commit=True) as (_, cur):
            cur.execute("DELETE FROM marriage_proposals WHERE target_id = ?", (target,))
        return "Предложение больше недействительно."

    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "UPDATE relationships SET married = 1, family_surname = ? WHERE user_id IN (?, ?)",
            (surname, target, proposer),
        )
        cur.execute("DELETE FROM marriage_proposals WHERE target_id = ?", (target,))
    return f"💍 Согласие принято! Теперь вы семья с фамилией «{surname}»."


def reject_marriage(target: int) -> str:
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM marriage_proposals WHERE target_id = ?", (target,))
        if cur.rowcount == 0:
            return "У тебя нет ожидающего предложения брака."
    return "💔 Предложение брака отклонено."


def leave_family(uid: int) -> str:
    if not get_parents(uid):
        return "Ты не состоишь ни в одной семье."
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM family_children WHERE child_id = ?", (uid,))
    return "🚪 Ты ушёл/ушла из семьи."


def relationship_status(uid: int) -> str:
    partner = get_partner_id(uid)
    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT married, family_surname FROM relationships WHERE user_id = ?",
            (uid,),
        )
        row = cur.fetchone()
    married = bool(row and row["married"])
    surname = (row["family_surname"] if row else "") or "не установлена"
    children = get_children(uid)
    parents = get_parents(uid)

    partner_text = "Нет"
    if partner:
        name = get_display_name(partner) or f"id{partner}"
        partner_text = f"[id{partner}|{name}]"

    return (
        f"❤️ Партнёр: {partner_text}\n"
        f"💍 Брак: {'да' if married else 'нет'}\n"
        f"👤 Фамилия семьи: {surname}\n"
        f"👪 Родителей: {len(parents)}\n"
        f"🧒 Детей: {len(children)}/{MAX_CHILDREN}"
    )


def adopt_child(parent_id: int, child_id: int) -> tuple[bool, str]:
    if parent_id == child_id:
        return False, "Нельзя усыновить самого себя."
    if not get_partner_id(parent_id):
        return False, "Усыновление доступно только парам."
    with db.db_cursor() as (_, cur):
        cur.execute("SELECT married FROM relationships WHERE user_id=?", (parent_id,))
        row = cur.fetchone()
    if not row or not row["married"]:
        return False, "Усыновление доступно только в браке."
    if len(get_children(parent_id)) >= MAX_CHILDREN:
        return False, f"Максимум детей: {MAX_CHILDREN}."
    if get_parents(child_id):
        return False, "У этого пользователя уже есть семья."
    partner = get_partner_id(parent_id)
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT OR IGNORE INTO family_children (parent_id, child_id) VALUES (?, ?)",
            (parent_id, child_id),
        )
        if partner:
            cur.execute(
                "INSERT OR IGNORE INTO family_children (parent_id, child_id) VALUES (?, ?)",
                (partner, child_id),
            )
    return True, "👶 Ребёнок добавлен в семью."


def _name(uid: int) -> str:
    return get_display_name(uid) or f"id{uid}"


def remove_child(parent_id: int, child_id: int) -> str:
    children = get_children(parent_id)
    if child_id not in children:
        return "Этот пользователь не ваш ребёнок."
    partner = get_partner_id(parent_id)
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM family_children WHERE child_id=? AND parent_id=?", (child_id, parent_id))
        if partner:
            cur.execute("DELETE FROM family_children WHERE child_id=? AND parent_id=?", (child_id, partner))
    return "Ребёнок больше не в семье."
