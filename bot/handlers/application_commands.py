"""
Заявки на администратора: полный опрос после выбора беседы и роли.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from bot.core.router import router, CommandContext
from bot.core import database as db
from bot.core.config import settings
from bot.utils.vk_helpers import send_message, user_mention, get_user_name
from bot.keyboards import (
    application_chat_select_keyboard,
    application_role_select_keyboard,
    application_review_keyboard,
)

logger = logging.getLogger(__name__)

QUESTIONS = [
    "Ваше имя и фамилия? (только буквы, 2–80 символов)",
    "Ваш возраст?",
    "Сколько времени в день вы готовы уделять администрированию и в какие часы вы обычно онлайн?",
    "Почему вы хотите стать администратором?",
    "Был ли у вас уже опыт администрирования? Если да — напишите, как долго были администратором и с какими трудностями сталкивались.",
    "Что означает наказание «Предупреждение 1/3»? Сколько предупреждений нужно для того, чтобы участника исключило из чата?",
    "Запрещено ли распространять 18+ контент? Если есть исключения — назовите их.",
    "В чём заключается различие между «флудом» и «спамом»? Способны ли вы различать эти две вещи?",
    "Разрешено ли правилами распространение персональных данных?",
]

ROLE_NAMES = {2: "Активист", 3: "Рекрутер", 4: "Администратор"}

_EMOJI_DIGITS = {
    "0": "0️⃣", "1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣",
    "5": "5️⃣", "6": "6️⃣", "7": "7️⃣", "8": "8️⃣", "9": "9️⃣",
}


def _num(n: int) -> str:
    if n == 11:
        return "1️⃣1️⃣"
    if n == 10:
        return "🔟"
    return "".join(_EMOJI_DIGITS[d] for d in str(n))


def _parse_answers(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _app_dict(row) -> dict | None:
    if not row:
        return None
    return {
        "user_id": int(row["user_id"]),
        "state": row["state"],
        "current_step": int(row["current_step"] or 0),
        "answers": _parse_answers(row["answers"]),
        "review_peer_id": row["review_peer_id"],
        "review_msg_id": row["review_msg_id"],
        "updated_at": row["updated_at"],
    }


def _validate_name(text: str):
    text = text.strip()
    if not (2 <= len(text) <= 80):
        return False, "Имя и фамилия должны быть от 2 до 80 символов."
    if not all(ch.isalpha() or ch in "- " for ch in text):
        return False, "Имя и фамилия должны содержать только буквы, пробел или дефис."
    return True, ""


def validate_answer(step: int, text: str):
    if step == 0:
        return _validate_name(text)
    if not text or not text.strip():
        return False, "Ответ не может быть пустым."
    return True, ""


def _chat_label(peer_id: int) -> str:
    try:
        idx = list(settings.main_chats).index(peer_id) + 1
        return f"NightFall {idx}"
    except ValueError:
        if peer_id == settings.anarchy_chat:
            return "Анархия"
        if peer_id == settings.casino_chat:
            return "Казино"
        return str(peer_id)


def send_to_review(vk, user_id: int, answers: list):
    applicant_name = get_user_name(vk, user_id)
    chat_id = int(answers[0]) if answers and str(answers[0]).isdigit() else 0
    role_id = int(answers[1]) if len(answers) > 1 and str(answers[1]).isdigit() else 0
    chat_name = _chat_label(chat_id)
    role_name = ROLE_NAMES.get(role_id, str(role_id))

    lines = [
        "📩 Новая заявка на администратора",
        f"👤 [id{user_id}|{applicant_name}]",
        f"🏠 Беседа: {chat_name}",
        f"⚙️ Роль: {role_name}",
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "━━━━━━━━━━━━━━━",
    ]
    for i, (q, a) in enumerate(zip(QUESTIONS, answers[2:]), 1):
        lines.append(f"{_num(i)} {q}")
        lines.append(f"▸ {a}")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━")
    lines.append("Принять или отклонить заявку:")
    text = "\n".join(lines)

    try:
        result = vk.messages.send(
            peer_id=settings.applications_peer_id,
            random_id=0,
            message=text,
            keyboard=json.dumps(application_review_keyboard(user_id), ensure_ascii=False),
            disable_mentions=True,
        )
        db.set_application(user_id, "sent", len(QUESTIONS), answers, settings.applications_peer_id, result if isinstance(result, int) else None)
    except Exception as e:
        logger.exception("send_to_review: %s", e)
        send_message(vk, user_id, f"Не удалось отправить заявку модераторам: {e}")


def process_application_text(vk, user_id: int, peer_id: int, text: str) -> bool:
    """
    Обработка текстовых ответов заявки в ЛС.
    Возвращает True, если сообщение поглощено системой заявок.
    """
    if peer_id > 2_000_000_000:
        return False

    app = _app_dict(db.get_application(user_id))
    if not app:
        return False

    state = app["state"]
    if state not in ("in_progress", "await_chat", "await_role"):
        return False

    text = (text or "").strip()
    low = text.lower()

    if low in ("отмена", "лл отмена", "отменить"):
        db.delete_application(user_id)
        send_message(vk, user_id, "Заявка отменена. Можно начать заново: `лл заявка`.")
        return True

    if state in ("await_chat", "await_role"):
        send_message(vk, user_id, "Пожалуйста, воспользуйся кнопками выше, чтобы выбрать беседу или роль.")
        return True

    if not text:
        return True

    # Команды с префиксом во время опроса не мешаем (кроме отмены)
    if low.startswith("лл ") or low == "лл":
        return False

    step = int(app["current_step"])
    answers = list(app["answers"])

    ok, err = validate_answer(step, text)
    if not ok:
        send_message(vk, user_id, f"{err}\n\n{_num(step + 1)} {QUESTIONS[step]}")
        return True

    answers.append(text)
    step += 1

    if step >= len(QUESTIONS):
        db.set_application(user_id, "sent", step, answers)
        send_to_review(vk, user_id, answers)
        send_message(
            vk,
            user_id,
            "Спасибо! Твоя заявка отправлена на рассмотрение.\n\n"
            "Ответ придёт в личные сообщения в течение 24 часов.",
        )
        return True

    db.set_application(user_id, "in_progress", step, answers)
    send_message(vk, user_id, f"Принято.\n\n{_num(step + 1)} {QUESTIONS[step]}")
    return True


@router.command("заявка")
def cmd_apply(ctx: CommandContext):
    if ctx.peer_id > 2_000_000_000:
        return send_message(ctx.vk, ctx.peer_id, "Заявки подаются в ЛС бота.")

    app = _app_dict(db.get_application(ctx.user_id))
    if app and app["state"] in ("in_progress", "await_chat", "await_role", "sent"):
        return send_message(
            ctx.vk,
            ctx.peer_id,
            "У тебя уже есть активная заявка. Напиши `отмена`, чтобы сбросить, или дождись решения.",
        )

    if db.is_in_admin_blacklist(ctx.user_id):
        return send_message(ctx.vk, ctx.peer_id, "Ты в ЧС администрации. Подача заявок недоступна.")

    db.set_application(ctx.user_id, "await_chat", 0, [])
    send_message(ctx.vk, ctx.peer_id, "Шаг 1: выбери беседу:", keyboard=application_chat_select_keyboard())


@router.command("отмена")
def cmd_cancel_app(ctx: CommandContext):
    app = _app_dict(db.get_application(ctx.user_id))
    if not app or app["state"] not in ("in_progress", "await_chat", "await_role", "await_gif", "await_status"):
        return send_message(ctx.vk, ctx.peer_id, "Нет активной заявки для отмены.")
    db.delete_application(ctx.user_id)
    send_message(ctx.vk, ctx.peer_id, "Отменено. Можно снова написать `лл заявка`.")


@router.button("app_chat_select")
def btn_app_chat(ctx: CommandContext):
    target_peer = ctx.payload.get("peer_id")
    if not target_peer:
        return
    db.set_application(ctx.user_id, "await_role", 0, [str(target_peer)])
    send_message(
        ctx.vk,
        ctx.peer_id,
        "Шаг 2: выбери желаемую роль:",
        keyboard=application_role_select_keyboard(int(target_peer)),
    )


@router.button("app_role_select")
def btn_app_role(ctx: CommandContext):
    target_peer = ctx.payload.get("peer_id")
    role = ctx.payload.get("role")
    app = _app_dict(db.get_application(ctx.user_id))
    answers = list(app["answers"]) if app else []
    # answers[0] = peer, answers[1] = role
    if not answers:
        answers = [str(target_peer)]
    elif len(answers) == 1:
        pass
    else:
        answers = answers[:1]
    answers.append(str(role))
    db.set_application(ctx.user_id, "in_progress", 0, answers)
    send_message(
        ctx.vk,
        ctx.peer_id,
        f"Отлично! Ответь на вопросы по порядку.\n\n{_num(1)} {QUESTIONS[0]}",
    )


@router.button("app_accept")
def btn_app_accept(ctx: CommandContext):
    applicant = ctx.payload.get("applicant")
    if not applicant:
        return
    applicant = int(applicant)
    app = _app_dict(db.get_application(applicant))
    answers = app["answers"] if app else []
    peer_id = int(answers[0]) if answers and str(answers[0]).isdigit() else 0
    role_id = int(answers[1]) if len(answers) > 1 and str(answers[1]).isdigit() else 0

    # Принятие: ставим СТАЖЁРА (ур. 1) в выбранной беседе — карьера начинается с испа
    if peer_id and role_id:
        db.set_admin_level(peer_id, applicant, 1)  # стажёр
        try:
            from bot.services.pin_service import refresh_after_admin_change
            refresh_after_admin_change(ctx.vk, peer_id=peer_id, global_change=False)
        except Exception as e:
            logger.warning("pin after app accept: %s", e)

    db.set_application(applicant, "accepted", 0, answers or [])
    name = get_user_name(ctx.vk, ctx.user_id)
    send_message(
        ctx.vk,
        applicant,
        "Поздравляем! Твоя заявка на администратора принята.\n"
        "Тебе выдана роль «Стажёр». Пройди испытательный срок командой `лл сдать исп` в ЛС бота.\n"
        "Ожидай дальнейших указаний от старшей администрации.",
    )
    cmid = ctx.payload.get("_conversation_message_id")
    final = (
        f"📩 Заявка от [id{applicant}|{get_user_name(ctx.vk, applicant)}]\n"
        f"Беседа: {_chat_label(peer_id)} | Цель: {ROLE_NAMES.get(role_id, role_id)}\n\n"
        f"✅ Принята администратором [id{ctx.user_id}|{name}].\n"
        f"Назначен стажёр (испытательный срок)."
    )
    if cmid:
        try:
            ctx.vk.messages.edit(
                peer_id=ctx.peer_id,
                conversation_message_id=int(cmid),
                message=final,
                keyboard=json.dumps({"inline": True, "buttons": []}, ensure_ascii=False),
                disable_mentions=True,
            )
        except Exception:
            send_message(ctx.vk, ctx.peer_id, final)
    else:
        send_message(ctx.vk, ctx.peer_id, final)


@router.button("app_decline")
def btn_app_decline(ctx: CommandContext):
    applicant = ctx.payload.get("applicant")
    if not applicant:
        return
    applicant = int(applicant)
    app = _app_dict(db.get_application(applicant))
    answers = app["answers"] if app else []
    peer_id = int(answers[0]) if answers and str(answers[0]).isdigit() else 0
    role_id = int(answers[1]) if len(answers) > 1 and str(answers[1]).isdigit() else 0
    db.set_application(applicant, "declined", 0, answers or [])
    name = get_user_name(ctx.vk, ctx.user_id)
    send_message(
        ctx.vk,
        applicant,
        "К сожалению, твоя заявка на администратора отклонена.\n"
        "Позже можно подать новую через `лл заявка`.",
    )
    cmid = ctx.payload.get("_conversation_message_id")
    final = (
        f"📩 Заявка от [id{applicant}|{get_user_name(ctx.vk, applicant)}]\n"
        f"Беседа: {_chat_label(peer_id)} | Цель: {ROLE_NAMES.get(role_id, role_id)}\n\n"
        f"❌ Отклонена администратором [id{ctx.user_id}|{name}]."
    )
    if cmid:
        try:
            ctx.vk.messages.edit(
                peer_id=ctx.peer_id,
                conversation_message_id=int(cmid),
                message=final,
                keyboard=json.dumps({"inline": True, "buttons": []}, ensure_ascii=False),
                disable_mentions=True,
            )
        except Exception:
            send_message(ctx.vk, ctx.peer_id, final)
    else:
        send_message(ctx.vk, ctx.peer_id, final)
