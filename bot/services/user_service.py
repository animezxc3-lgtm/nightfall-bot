"""
Сервис работы с пользователями и экономикой.
Тексты профиля/баланса/активности — как в старом боте.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from bot.core import database as db
from bot.services.admin_service import AdminService
from bot.services.relationship_service import get_partner_id, get_display_name
from bot.utils.vk_helpers import get_user_name, user_mention

logger = logging.getLogger(__name__)

POWER_RANKS = [
    (0, "Наблюдатель"),
    (100, "Новичок"),
    (300, "Стратег"),
    (700, "Тактик"),
    (1500, "Командир"),
    (3000, "Лидер"),
    (6000, "Властитель"),
    (10000, "Претендент на Трон"),
    (20000, "Королевская Особа"),
    (50000, "Император"),
]

ROLE_NAMES = {
    1: "Стажёр",
    2: "Активист",
    3: "Рекрутер",
    4: "Администратор",
    5: "Куратор",
    6: "Вершитель правосудия",
    7: "Лелуш ви Британия",
}


def get_power_rank(power: int) -> str:
    name = POWER_RANKS[0][1]
    for threshold, rank in POWER_RANKS:
        if power >= threshold:
            name = rank
        else:
            break
    return name


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    s = str(iso)[:10]
    try:
        y, m, d = s.split("-")
        return f"{d}.{m}.{y}"
    except ValueError:
        return s


class UserService:
    def __init__(self, vk: Any):
        self.vk = vk

    def ensure(self, user_id: int, name: str | None = None) -> None:
        if not db.user_exists(user_id):
            display = name or get_user_name(self.vk, user_id)
            db.create_user(user_id, display)
            logger.info("Создан пользователь %s (%s)", user_id, display)

    def get_profile_text(self, user_id: int, peer_id: int | None = None) -> tuple[str, str | None]:
        """Возвращает (текст, attachment|None) — как в старом боте."""
        row = db.get_user(user_id)
        if not row:
            return "Пользователь не найден в базе.", None

        nick = (row["nickname"] or "").strip()
        name = (row["name"] or "").strip()
        display = nick or (name.split()[0] if name else "Пользователь")
        power = int(row["power"] or 0)
        coins = int(row["coins"] or 0)
        soul_gems = int(row["soul_gems"] or 0)
        status = (row["status"] or "").strip()
        housing = row["housing"] or "Отсутствует"
        car = row["car"] or "Отсутствует"
        phone = row["phone"] or "Отсутствует"
        job = row["job"] or "Отсутствует"
        job_level = int(row["job_level"] or 0)
        gif_link = (row["gif_link"] or "").strip()
        profile_image = (row["profile_image"] or "").strip()

        # Работа с уровнем
        job_display = job
        if job and job != "Отсутствует":
            from bot.services.work_service import get_level_name, PROFESSIONS
            if job in PROFESSIONS:
                job_display = f"{PROFESSIONS[job]['name']} ({get_level_name(job, job_level)})"

        partner = get_partner_id(user_id)
        days_line = "—"
        if partner:
            try:
                from bot.services.relationship_service import relationship_status
                # days extracted if available in relationships table
                with db.db_cursor() as (_, cur):
                    cur.execute(
                        "SELECT relationship_since FROM relationships WHERE user_id=?",
                        (user_id,),
                    )
                    r = cur.fetchone()
                    if r and r["relationship_since"]:
                        from datetime import datetime, date
                        try:
                            since = datetime.fromisoformat(str(r["relationship_since"])[:19]).date()
                            days_line = str((date.today() - since).days)
                        except Exception:
                            days_line = "—"
            except Exception:
                pass

        admin = AdminService()
        level = admin.get_level(user_id, peer_id)
        global_level = db.get_global_role(user_id)
        display_level = max(level, global_level)
        from bot.core.config import settings
        if user_id == settings.creator_id:
            display_level = 7
        rights_display = ROLE_NAMES.get(display_level, "Участник")

        # Предупреждения
        warning_count = 0
        try:
            with db.db_cursor() as (_, cur):
                if peer_id and peer_id > 2_000_000_000:
                    cur.execute(
                        "SELECT COUNT(*) as c FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=1",
                        (user_id, peer_id),
                    )
                else:
                    cur.execute(
                        "SELECT warnings FROM users WHERE user_id=?",
                        (user_id,),
                    )
                r = cur.fetchone()
                if r:
                    warning_count = int(r["c"] if "c" in r.keys() else r["warnings"] or 0)
        except Exception:
            warning_count = int(row["warnings"] or 0)

        join_date = "—"
        if peer_id and peer_id > 2_000_000_000:
            jd = db.get_chat_join_date(peer_id, user_id)
            join_date = _fmt_date(jd)
        if join_date == "—":
            join_date = _fmt_date(row["join_date"] if "join_date" in row.keys() else None)

        lines = [f"👤 {user_mention(user_id, display)}"]
        if status:
            lines.append(f"📝 Статус: {status}")
        lines.append(f"⚡ Сила Гиаса: {power} // {get_power_rank(power)}")
        if display_level >= 1:
            lines.append(f"💎 Камни души: {soul_gems}")
        lines.extend([
            f"🪙 Монеты: {coins}",
            f"💼 Работа: {job_display}",
            f"❤️ Партнёр: {user_mention(partner, get_display_name(partner) or 'Партнёр') if partner else 'Нет'}",
            f"❤️ Дней в отношениях: {days_line}",
            f"🏠 Жильё: {housing}",
            f"🚗 Машина: {car}",
            f"📱 Телефон: {phone}",
            f"⚠️ Предупреждения: {warning_count}/3",
            f"🔒 Права: {rights_display}",
            f"📆 Дата появления: {join_date}",
        ])

        attachment = None
        if gif_link.startswith("https://vk.com/doc") or gif_link.startswith("https://vk.ru/doc"):
            attachment = gif_link
        elif profile_image.startswith("photo"):
            attachment = profile_image

        return "\n".join(lines), attachment

    def get_balance_text(self, user_id: int) -> str:
        row = db.get_user(user_id)
        if not row:
            return "Пользователь не найден."
        nick = (row["nickname"] or "").strip()
        name = (row["name"] or "").strip()
        display = nick or (name.split()[0] if name else "Пользователь")
        power = int(row["power"] or 0)
        coins = int(row["coins"] or 0)
        soul_gems = int(row["soul_gems"] or 0)

        admin = AdminService()
        level = admin.get_level(user_id)
        from bot.core.config import settings
        if user_id == settings.creator_id:
            level = 7

        lines = [
            f"👤 {user_mention(user_id, display)}",
            f"⚡ Сила Гиаса: {power} // {get_power_rank(power)}",
        ]
        if level >= 1:
            lines.append(f"💎 Камни души: {soul_gems}")
        lines.append(f"🪙 Монеты: {coins}")
        return "\n".join(lines)

    def get_activity_text(self, user_id: int) -> str:
        stats = db.get_messages_stats(user_id)
        if not stats:
            return (
                "📊 Активность\n"
                "📅 Сегодня: 0\n"
                "📆 За неделю: 0\n"
                "📆 За месяц: 0\n"
                "📈 За всё время: 0"
            )
        return (
            "📊 Активность\n"
            f"📅 Сегодня: {stats.get('today', 0)}\n"
            f"📆 За неделю: {stats.get('week', 0)}\n"
            f"📆 За месяц: {stats.get('month', 0)}\n"
            f"📈 За всё время: {stats.get('total', 0)}"
        )

    def set_nickname(self, user_id: int, nickname: str) -> bool:
        nickname = nickname.strip()
        if not 1 <= len(nickname) <= 30:
            return False
        db.update_user_field(user_id, "nickname", nickname)
        return True
