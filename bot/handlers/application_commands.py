import json
from bot.core.router import router, CommandContext
from bot.core import database as db
from bot.core.config import settings
from bot.utils.vk_helpers import send_message, user_mention, parse_target_id
from bot.keyboards import (
    application_chat_select_keyboard,
    application_role_select_keyboard,
    application_review_keyboard,
)

QUESTIONS = [
    "Ваше имя и фамилия?", "Ваш возраст?", "Опыт администрирования?", 
    "Сколько часов в день уделяете?", "Почему хотите стать админом?",
    "Что такое предупреждение 1/3?", "Разрешено ли 18+?",
    "Различие флуда и спама?", "Можно ли распространять личные данные?"
]

@router.command("заявка")
def cmd_apply(ctx: CommandContext):
    if ctx.peer_id > 2000000000:
        return send_message(ctx.vk, ctx.peer_id, "Заявки подаются в ЛС бота.")
    
    app = db.get_application(ctx.user_id)
    if app and app["state"] != "closed":
        return send_message(ctx.vk, ctx.peer_id, "У вас уже есть активная заявка. Напишите 'отмена'.")
    
    db.set_application(ctx.user_id, "await_chat", 0, [])
    send_message(ctx.vk, ctx.peer_id, "Шаг 1: Выбери беседу:", keyboard=application_chat_select_keyboard())

@router.button("app_chat_select")
def btn_app_chat(ctx: CommandContext):
    target_peer = ctx.payload.get("peer_id")
    db.set_application(ctx.user_id, "await_role", 1, [str(target_peer)])
    send_message(ctx.vk, ctx.peer_id, "Шаг 2: Выбери роль:", keyboard=application_role_select_keyboard(target_peer))

@router.button("app_role_select")
def btn_app_role(ctx: CommandContext):
    target_peer = ctx.payload.get("peer_id")
    role = ctx.payload.get("role")
    app = db.get_application(ctx.user_id)
    answers = app["answers"] if app else []
    db.set_application(ctx.user_id, "in_progress", 0, answers + [str(role)])
    send_message(ctx.vk, ctx.peer_id, f"Отлично! Ответь на вопросы.\n\n1. {QUESTIONS[0]}")

@router.button("app_accept")
def btn_app_accept(ctx: CommandContext):
    applicant = ctx.payload.get("applicant")
    if not applicant: return
    db.set_application(int(applicant), "accepted", 0, [])
    send_message(ctx.vk, applicant, "✅ Ваша заявка одобрена!")
    # Редактируем сообщение в заявках
    cmid = ctx.payload.get("_conversation_message_id")
    if cmid: send_message(ctx.vk, ctx.peer_id, "✅ Заявка одобрена.", keyboard=None)

@router.button("app_decline")
def btn_app_decline(ctx: CommandContext):
    applicant = ctx.payload.get("applicant")
    if not applicant: return
    db.set_application(int(applicant), "declined", 0, [])
    send_message(ctx.vk, applicant, "❌ Ваша заявка отклонена.")