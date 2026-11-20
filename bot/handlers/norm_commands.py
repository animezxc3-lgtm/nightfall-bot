from datetime import datetime, timedelta, date
from bot.core.router import router, CommandContext
from bot.core import database as db
from bot.core.config import settings
from bot.utils.vk_helpers import send_message, user_mention, edit_message
from bot.keyboards import norm_review_keyboard

@router.command("отчет")
def cmd_report(ctx: CommandContext):
    if ctx.peer_id > 2000000000:
        return send_message(ctx.vk, ctx.peer_id, "Отчет сдается только в ЛС.")
    send_message(ctx.vk, ctx.peer_id, "Пришли фото проделанной работы (до 10) или напиши 'Пропустить'.", keyboard=norm_skip_photos_keyboard())

@router.button("norm_skip_photos")
def btn_norm_skip(ctx: CommandContext):
    user_id = ctx.user_id
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
    msg_stats = db.get_messages_stats(user_id)
    week_msgs = msg_stats.get("week", 0)
    
    with db.db_cursor() as (_, cur):
        cur.execute("SELECT COUNT(*) FROM chat_members WHERE invited_by=? AND substr(first_join_at,1,10)>=?", (user_id, week_start))
        week_invites = cur.fetchone()[0] or 0
    
    DIVIDER = '⋅⋆✦──── ⋆⋅☆⋅⋆ ────✦⋆⋅'
    lines = [
        f'Отчёт от {user_mention(user_id)}',
        f'Активность: {week_msgs} сообщений.',
        f'Добавления: {week_invites}',
        DIVIDER,
        'Проверяют: ...'
    ]
    text = '\n'.join(lines)
    
    report_id = db.create_norm_report(user_id, text)
    send_message(ctx.vk, settings.control_chat, text, keyboard=norm_review_keyboard(report_id))
    send_message(ctx.vk, ctx.peer_id, "✅ Отчет отправлен в Контроль.")

@router.button("norm_accept")
def btn_norm_accept(ctx: CommandContext):
    report_id = ctx.payload.get("report_id")
    if not report_id: return
    db.update_norm_status(int(report_id), "accepted", ctx.user_id)
    send_message(ctx.vk, ctx.peer_id, "✅ Отчет одобрен.")

@router.button("norm_decline")
def btn_norm_decline(ctx: CommandContext):
    report_id = ctx.payload.get("report_id")
    if not report_id: return
    db.update_norm_status(int(report_id), "declined", ctx.user_id)
    send_message(ctx.vk, ctx.peer_id, "❌ Отчет отклонен.")