"""
Испытательный срок стажёра: лл сдать исп (только ЛС).

Проверяют: куратор беседы стажёра + вершители + создатель.
Нельзя одобрить свой отчёт.
При одобрении: стажёр (1) -> активист (2) в своей беседе.
"""
from __future__ import annotations

import json
import logging

from bot.core.router import router, CommandContext
from bot.core import database as db
from bot.core.config import settings
from bot.utils.vk_helpers import send_message, user_mention, get_user_name, edit_message
from bot.keyboards.main import _btn
from bot.handlers.norm_commands import (
    _display_level,
    _user_link,
    _chat_title,
    _week_start,
    _extract_photos_from_message,
)

logger = logging.getLogger(__name__)

DIVIDER = "⋅⋆✦──── ⋆⋅☆⋅⋆ ────✦⋆⋅"
_pending_isp: dict[int, list[str]] = {}


def isp_review_keyboard(report_id: int) -> dict:
    return {
        "inline": True,
        "buttons": [[
            _btn("✅ Зачёт", "isp_accept", report_id=report_id),
            _btn("❌ Незачёт", "isp_decline", report_id=report_id),
        ]],
    }


def isp_skip_keyboard() -> dict:
    return {"inline": True, "buttons": [[_btn("Пропустить / готово", "isp_skip_photos")]]}


def _intern_chat(user_id: int):
    for peer_id, level in db.get_user_admin_chats(user_id):
        if level == 1:
            return peer_id
    return None


def get_isp_reviewers(author_id: int, peer_id) -> set:
    reviewers = {settings.creator_id}
    for row in db.get_all_global_roles():
        if int(row["level"]) >= 6:
            reviewers.add(int(row["user_id"]))
    if peer_id:
        for row in db.get_admins_for_chat(peer_id):
            if int(row["level"]) >= 5:
                reviewers.add(int(row["user_id"]))
    reviewers.discard(author_id)
    return reviewers


def can_review_isp(reviewer_id: int, author_id: int, peer_id) -> bool:
    if reviewer_id == author_id:
        return False
    if reviewer_id == settings.creator_id:
        return True
    if db.get_global_role(reviewer_id) >= 6:
        return True
    if peer_id and db.get_admin_level_for_chat(peer_id, reviewer_id) >= 5:
        return True
    return False


def build_isp_text(vk, user_id: int, peer_id) -> str:
    week_start = _week_start()
    msg_stats = db.get_messages_stats(user_id)
    week_msgs = msg_stats.get("week", 0)
    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT COUNT(*) FROM chat_members WHERE invited_by=? AND substr(first_join_at,1,10)>=?",
            (user_id, week_start),
        )
        row = cur.fetchone()
        invites = int(row[0] or 0) if row else 0

    chat_name = _chat_title(vk, peer_id) if peer_id else "—"
    reviewers = get_isp_reviewers(user_id, peer_id)
    rev_links = ", ".join(_user_link(vk, r) for r in sorted(reviewers)) or "—"
    join = "—"
    role_since = "—"
    if peer_id:
        jd = db.get_chat_join_date(peer_id, user_id)
        if jd:
            join = str(jd)[:10]
        ap = db.get_admin_appointed_at(peer_id, user_id)
        if ap:
            role_since = str(ap)[:10]
            try:
                from datetime import datetime, date
                d0 = datetime.fromisoformat(str(ap)[:19]).date()
                days = (date.today() - d0).days
                role_since = f"{role_since} ({days} дн. на должности)"
            except Exception:
                pass

    lines = [
        "📋 ИСПЫТАТЕЛЬНЫЙ ОТЧЁТ (стажёр)",
        f"От: {_user_link(vk, user_id)}",
        f"Беседа: {chat_name}",
        f"В беседе с: {join}",
        f"Стажёр с: {role_since}",
        DIVIDER,
        f"Сообщений за неделю: {week_msgs}",
        f"Добавлений за неделю: {invites}",
        DIVIDER,
        "Стажёр претендует на повышение до «Активист».",
        "",
        f"Проверяют: {rev_links}",
    ]
    return "\n".join(lines)


def submit_isp(vk, user_id: int, photos=None) -> str:
    photos = photos or []
    peer_id = _intern_chat(user_id)
    text = build_isp_text(vk, user_id, peer_id)
    report_id = db.create_internship_report(user_id, peer_id or 0, text)
    args = {
        "peer_id": settings.control_chat,
        "random_id": 0,
        "message": text,
        "keyboard": json.dumps(isp_review_keyboard(report_id), ensure_ascii=False),
        "disable_mentions": True,
    }
    if photos:
        args["attachment"] = ",".join(photos[:10])
    try:
        vk.messages.send(**args)
    except Exception as e:
        logger.exception("isp send: %s", e)
        return f"Ошибка отправки: {e}"
    return "✅ Испытательный отчёт отправлен в Контроль. Ожидай решения куратора / вершителя / создателя."


@router.command("сдать исп")
def cmd_submit_isp(ctx: CommandContext):
    if ctx.peer_id > 2_000_000_000:
        return send_message(ctx.vk, ctx.peer_id, "Команда «лл сдать исп» доступна только в ЛС бота.")

    peer = _intern_chat(ctx.user_id)
    if not peer and ctx.user_id != settings.creator_id:
        return send_message(
            ctx.vk,
            ctx.peer_id,
            "Эта команда только для стажёров (роль «Стажёр» в одной из бесед).",
        )

    _pending_isp[ctx.user_id] = []
    send_message(
        ctx.vk,
        ctx.peer_id,
        "Испытательный отчёт.\n"
        "Пришли скрины / фото работы (до 10), затем нажми «Пропустить / готово» "
        "или напиши «готово исп».",
        keyboard=isp_skip_keyboard(),
    )


@router.button("isp_skip_photos")
def btn_isp_skip(ctx: CommandContext):
    photos = _pending_isp.pop(ctx.user_id, [])
    send_message(ctx.vk, ctx.peer_id, submit_isp(ctx.vk, ctx.user_id, photos))


@router.command("готово исп")
def cmd_isp_done(ctx: CommandContext):
    if ctx.peer_id > 2_000_000_000:
        return
    if ctx.user_id not in _pending_isp:
        return
    photos = _pending_isp.pop(ctx.user_id, [])
    send_message(ctx.vk, ctx.peer_id, submit_isp(ctx.vk, ctx.user_id, photos))


def try_collect_isp_photo(user_id: int, peer_id: int, msg, vk) -> bool:
    if peer_id > 2_000_000_000:
        return False
    if user_id not in _pending_isp:
        return False
    photos = _extract_photos_from_message(msg)
    if not photos:
        return False
    bucket = _pending_isp.setdefault(user_id, [])
    bucket.extend(photos)
    send_message(
        vk,
        peer_id,
        f"📷 Фото для исп.: {len(bucket)}. Ещё или «Пропустить / готово».",
        keyboard=isp_skip_keyboard(),
    )
    return True


def _finalize_isp(ctx: CommandContext, status: str):
    report_id = ctx.payload.get("report_id")
    if not report_id:
        return
    report_id = int(report_id)
    report = db.get_internship_report(report_id)
    if not report:
        return send_message(ctx.vk, ctx.peer_id, "Отчёт не найден.")
    if (report["status"] or "").lower() in ("accepted", "declined"):
        return send_message(ctx.vk, ctx.peer_id, "Этот отчёт уже проверен.")

    author_id = int(report["user_id"])
    peer_id = int(report["peer_id"] or 0) or None
    old_text = report["report_text"] or ""

    if not can_review_isp(ctx.user_id, author_id, peer_id):
        try:
            send_message(ctx.vk, ctx.user_id, "⛔ Нет прав проверять этот испытательный отчёт (или это ваш отчёт).")
        except Exception:
            pass
        return

    db.update_internship_status(report_id, status, ctx.user_id)
    admin_link = _user_link(ctx.vk, ctx.user_id)

    if status == "accepted":
        promote_peer = peer_id or _intern_chat(author_id)
        if promote_peer:
            db.set_admin_level(promote_peer, author_id, 2)
            try:
                from bot.services.pin_service import refresh_after_admin_change
                refresh_after_admin_change(ctx.vk, peer_id=promote_peer, global_change=False)
            except Exception as e:
                logger.warning("pin after isp: %s", e)
        status_line = f"─── ✅ ЗАЧЁТ (проверил: {admin_link}) ───"
        footer = "⋅⋆✦──── ⋆⋅Испытательный срок пройден → Активист⋅⋆ ────✦⋆⋅"
        user_msg = "🎉 Испытательный отчёт принят!\nТебе присвоена роль «Активист». Поздравляем."
    else:
        status_line = f"─── ❌ НЕЗАЧЁТ (проверил: {admin_link}) ───"
        footer = "⋅⋆✦──── ⋆⋅Нужно доработать и сдать снова⋅⋆ ────✦⋆⋅"
        user_msg = (
            "Испытательный отчёт отклонён.\n"
            "Продолжай работу и снова используй «лл сдать исп» в ЛС, когда будешь готов."
        )

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


@router.button("isp_accept")
def btn_isp_accept(ctx: CommandContext):
    _finalize_isp(ctx, "accepted")


@router.button("isp_decline")
def btn_isp_decline(ctx: CommandContext):
    _finalize_isp(ctx, "declined")
