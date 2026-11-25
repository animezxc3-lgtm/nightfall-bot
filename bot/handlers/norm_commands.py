"""
Система норм / еженедельных отчётов.

Иерархия проверки:
- Нельзя одобрить свой отчёт.
- Отчёт куратора (ур. 5): проверяют вершители (ур. ≥6) и создатель.
- Отчёт стажёра / активиста / рекрутера / админа (ур. 1–4):
  проверяют кураторы его бесед (ур. ≥5) + вершители + создатель.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from bot.core.router import router, CommandContext
from bot.core import database as db
from bot.core.config import settings
from bot.services.admin_service import AdminService
from bot.services.user_service import ROLE_NAMES
from bot.utils.vk_helpers import send_message, user_mention, get_user_name, edit_message
from bot.keyboards import norm_review_keyboard, norm_skip_photos_keyboard

logger = logging.getLogger(__name__)

DIVIDER = "⋅⋆✦──── ⋆⋅☆⋅⋆ ────✦⋆⋅"

# Временное хранение фото при сдаче отчёта в ЛС: user_id -> list[attachment]
_pending_photos: dict[int, list[str]] = {}


def _week_start() -> str:
    now = datetime.now()
    return (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%d")


def _display_level(user_id: int) -> int:
    """Максимальный уровень прав пользователя (глобальный / локальный / создатель)."""
    if user_id == settings.creator_id:
        return 7
    g = db.get_global_role(user_id)
    chats = db.get_user_admin_chats(user_id)
    local_max = max((lvl for _, lvl in chats), default=0)
    return max(g, local_max)


def _chat_title(vk, peer_id: int) -> str:
    try:
        data = vk.messages.getConversationsById(peer_ids=peer_id).get("items", [])
        if data:
            return data[0].get("chat_settings", {}).get("title") or str(peer_id)
    except Exception:
        pass
    return str(peer_id)


def _user_link(vk, user_id: int) -> str:
    name = get_user_name(vk, user_id)
    try:
        from bot.services.relationship_service import get_display_name
        name = get_display_name(user_id) or name
    except Exception:
        pass
    return user_mention(user_id, name)


def get_reviewers_for_report(author_id: int) -> set[int]:
    """
    Кого тегать / кто имеет право проверять отчёт автора.
    """
    author_level = _display_level(author_id)
    reviewers: set[int] = set()

    # Всегда: создатель
    reviewers.add(settings.creator_id)

    # Всегда: глобальные вершители и выше (ур. ≥ 6)
    try:
        for row in db.get_all_global_roles():
            uid, lvl = int(row["user_id"]), int(row["level"])
            if lvl >= 6:
                reviewers.add(uid)
    except Exception:
        pass

    # Для кураторов (ур. ≥ 5) — только вершители + создатель (уже добавлены)
    # Для 1–4 — ещё кураторы бесед, где у автора есть права
    if author_level < 5:
        for peer_id, _ in db.get_user_admin_chats(author_id):
            try:
                for row in db.get_admins_for_chat(peer_id):
                    auid, alvl = int(row["user_id"]), int(row["level"])
                    if alvl >= 5:
                        reviewers.add(auid)
            except Exception:
                pass

    # Автор сам себе не ревьюер
    reviewers.discard(author_id)
    return reviewers


def can_review_norm(reviewer_id: int, author_id: int) -> bool:
    """Может ли reviewer одобрять/отклонять отчёт author."""
    if reviewer_id == author_id:
        return False
    if reviewer_id == settings.creator_id:
        return True

    author_level = _display_level(author_id)
    reviewer_global = db.get_global_role(reviewer_id)
    if reviewer_id == settings.creator_id or reviewer_global >= 6:
        return True

    # Отчёт куратора — только вершитель+ / создатель
    if author_level >= 5:
        return False

    # Отчёт 1–4: куратор той же беседы (локально ≥ 5)
    author_chats = {pid for pid, _ in db.get_user_admin_chats(author_id)}
    for peer_id in author_chats:
        if db.get_admin_level_for_chat(peer_id, reviewer_id) >= 5:
            return True
    return False


def build_report_text(vk, user_id: int) -> str:
    level = _display_level(user_id)
    role_name = ROLE_NAMES.get(level, "Участник")
    if user_id == settings.creator_id:
        role_name = ROLE_NAMES.get(7, "Создатель")

    chats = []
    for peer_id, _ in db.get_user_admin_chats(user_id):
        chats.append(_chat_title(vk, peer_id))
    chats_str = ", ".join(chats) if chats else "Нет"

    week_start = _week_start()
    msg_stats = db.get_messages_stats(user_id)
    week_msgs = msg_stats.get("week", 0)

    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT COUNT(*) FROM chat_members WHERE invited_by=? AND substr(first_join_at,1,10)>=?",
            (user_id, week_start),
        )
        row = cur.fetchone()
        week_invites = int(row[0] or 0) if row else 0

    tags = db.get_admin_tags_stats(user_id, week_start)
    tags_line = ", ".join(f"{k}: {v}" for k, v in tags.items()) if tags else "—"

    lines = [
        f"Отчёт от {_user_link(vk, user_id)}",
        f"Права: {role_name}",
        f"Беседы: {chats_str}",
        DIVIDER,
        f"Активность администратора\nЗа неделю: {week_msgs}",
        DIVIDER,
        f"Количество добавлений за неделю: {week_invites}",
        DIVIDER,
        f"Теги / действия: {tags_line}",
    ]

    reviewers = get_reviewers_for_report(user_id)
    links = [_user_link(vk, rid) for rid in sorted(reviewers)]
    reviewers_text = ", ".join(links) if links else "Нет назначенных проверяющих"
    lines.append("")
    lines.append(f"Проверяют: {reviewers_text}")
    return "\n".join(lines)


def submit_report(vk, user_id: int, photos: list[str] | None = None) -> str:
    photos = photos or []
    text = build_report_text(vk, user_id)
    report_id = db.create_norm_report(user_id, text)
    for ph in photos:
        db.add_norm_photo(report_id, ph)

    kb = norm_review_keyboard(report_id)
    args = {
        "peer_id": settings.control_chat,
        "random_id": 0,
        "message": text,
        "keyboard": json.dumps(kb, ensure_ascii=False),
        "disable_mentions": True,
    }
    if photos:
        args["attachment"] = ",".join(photos[:10])
    try:
        vk.messages.send(**args)
        if len(photos) > 10:
            vk.messages.send(
                peer_id=settings.control_chat,
                random_id=0,
                message="Остальные фото:",
                attachment=",".join(photos[10:]),
                disable_mentions=True,
            )
    except Exception as e:
        logger.exception("Ошибка отправки отчёта: %s", e)
        return f"Ошибка отправки в Контроль: {e}"
    return "✅ Отчёт сформирован и отправлен в Контроль."


def _extract_photos_from_message(msg) -> list[str]:
    """Достаёт photo-вложения из сообщения VK."""
    attachments = []
    raw = []
    if isinstance(msg, dict):
        raw = msg.get("attachments") or []
    else:
        raw = getattr(msg, "attachments", None) or []
    for att in raw:
        if isinstance(att, dict):
            if att.get("type") != "photo":
                continue
            photo = att.get("photo") or {}
            owner = photo.get("owner_id")
            pid = photo.get("id")
            access = photo.get("access_key")
            if owner is not None and pid is not None:
                s = f"photo{owner}_{pid}"
                if access:
                    s += f"_{access}"
                attachments.append(s)
    return attachments


# ─── Команды ─────────────────────────────────────────────

@router.command("отчет", aliases=["отчёт", "норма"])
def cmd_report(ctx: CommandContext):
    if ctx.peer_id > 2_000_000_000:
        return send_message(ctx.vk, ctx.peer_id, "Отчёт сдаётся только в ЛС бота.")

    level = _display_level(ctx.user_id)
    if level < 1 and ctx.user_id != settings.creator_id:
        return send_message(ctx.vk, ctx.peer_id, "Отчёт могут сдавать только сотрудники администрации.")

    _pending_photos[ctx.user_id] = []
    send_message(
        ctx.vk,
        ctx.peer_id,
        "Пришли фото проделанной работы (до 10 шт.) одним или несколькими сообщениями.\n"
        "Когда закончишь — нажми «Пропустить» / напиши «готово» или «пропустить».",
        keyboard=norm_skip_photos_keyboard(),
    )


@router.button("norm_skip_photos")
def btn_norm_skip(ctx: CommandContext):
    photos = _pending_photos.pop(ctx.user_id, [])
    msg = submit_report(ctx.vk, ctx.user_id, photos)
    send_message(ctx.vk, ctx.peer_id, msg)


@router.command("готово", aliases=["пропустить"])
def cmd_report_done(ctx: CommandContext):
    """Завершение сдачи отчёта текстом (если кнопкой не пользуются)."""
    if ctx.peer_id > 2_000_000_000:
        return
    if ctx.user_id not in _pending_photos:
        return
    photos = _pending_photos.pop(ctx.user_id, [])
    msg = submit_report(ctx.vk, ctx.user_id, photos)
    send_message(ctx.vk, ctx.peer_id, msg)


def try_collect_norm_photo(user_id: int, peer_id: int, msg, vk) -> bool:
    """
    Вызывать из main при MESSAGE_NEW в ЛС.
    Если пользователь в процессе сдачи отчёта — копит фото.
    """
    if peer_id > 2_000_000_000:
        return False
    if user_id not in _pending_photos:
        return False
    photos = _extract_photos_from_message(msg)
    if not photos:
        return False
    bucket = _pending_photos.setdefault(user_id, [])
    bucket.extend(photos)
    send_message(
        vk,
        peer_id,
        f"📷 Получено фото: {len(bucket)}. Можно прислать ещё или нажать «Пропустить» / написать «готово».",
        keyboard=norm_skip_photos_keyboard(),
    )
    return True


def _finalize_review(ctx: CommandContext, status: str):
    report_id = ctx.payload.get("report_id")
    if not report_id:
        return
    report_id = int(report_id)
    report = db.get_norm_report(report_id)
    if not report:
        return send_message(ctx.vk, ctx.peer_id, "Этот отчёт больше не существует.")

    author_id = int(report["user_id"])
    old_text = report["report_text"] or ""
    current_status = (report["status"] or "pending").lower()
    if current_status in ("accepted", "declined"):
        return send_message(ctx.vk, ctx.peer_id, "Этот отчёт уже проверен.")

    if not can_review_norm(ctx.user_id, author_id):
        # В ЛС ревьюеру — если жмёт без прав
        try:
            send_message(ctx.vk, ctx.user_id, "⛔ Недостаточно прав для проверки этого отчёта (или нельзя проверять свой).")
        except Exception:
            pass
        return

    db.update_norm_status(report_id, status, ctx.user_id)
    admin_link = _user_link(ctx.vk, ctx.user_id)

    if status == "accepted":
        status_line = f"─── Статус: ✅ ОДОБРЕНО (проверил: {admin_link}) ───"
        footer = "⋅⋆✦──── ⋆⋅Норма сдана⋅⋆ ────✦⋆⋅"
        user_msg = "Твой отчёт был одобрен!"
    else:
        status_line = f"─── Статус: ❌ ОТКЛОНЕНО (проверил: {admin_link}) ───"
        footer = "⋅⋆✦──── ⋆⋅Требует исправлений⋅⋆ ────✦⋆⋅"
        user_msg = "Твой отчёт был отклонён. Проверь цифры и попробуй снова."

    if "\n\nПроверяют:" in old_text:
        new_text = old_text.replace("\n\nПроверяют:", f"\n\n{status_line}\n{footer}\n\nПроверяют:")
    else:
        new_text = old_text + f"\n\n{status_line}\n{footer}"

    cmid = ctx.payload.get("_conversation_message_id")
    empty_kb = {"inline": True, "buttons": []}
    if cmid:
        edit_message(ctx.vk, ctx.peer_id, int(cmid), new_text, keyboard=empty_kb)
    else:
        send_message(ctx.vk, ctx.peer_id, new_text)

    try:
        send_message(ctx.vk, author_id, user_msg)
    except Exception:
        pass


@router.button("norm_accept")
def btn_norm_accept(ctx: CommandContext):
    _finalize_review(ctx, "accepted")


@router.button("norm_decline")
def btn_norm_decline(ctx: CommandContext):
    _finalize_review(ctx, "declined")
