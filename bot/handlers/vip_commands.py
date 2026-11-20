from bot.core.router import router, CommandContext
from bot.core import database as db
from bot.core.config import settings
from bot.utils.vk_helpers import send_message, user_mention

VIP_PRICES = {1: 100, 2: 100, 3: 65, 4: 100, 5: 100, 6: 100}

@router.command("вип")
def cmd_vip_shop(ctx: CommandContext):
    if ctx.peer_id > 2000000000:
        return send_message(ctx.vk, ctx.peer_id, "VIP-магазин доступен только в ЛС бота.")
    
    text = (
        "💎 VIP-магазин\n\n"
        "1. GIF в профиль — 100 💎\n"
        "2. Статус — 100 💎\n"
        "3. Снять пред — 65 💎\n"
        "4. Множитель зарплаты — 100 💎\n"
        "Покупка: `лл купить <номер>`"
    )
    send_message(ctx.vk, ctx.peer_id, text)

@router.command("купить")
def cmd_buy(ctx: CommandContext):
    if ctx.peer_id > 2000000000:
        return send_message(ctx.vk, ctx.peer_id, "Только в ЛС.")
    try:
        n = int(ctx.args)
    except ValueError:
        return
    
    price = VIP_PRICES.get(n)
    if not price: return
    
    user = db.get_user(ctx.user_id)
    if user["soul_gems"] < price:
        return send_message(ctx.vk, ctx.peer_id, "Недостаточно камней души.")
    
    db.update_gems(ctx.user_id, -price)
    
    if n == 1:
        send_message(ctx.vk, ctx.peer_id, "GIF куплено. Пришли ссылку на документ VK.")
    elif n == 2:
        send_message(ctx.vk, ctx.peer_id, "Статус куплен. Напиши текст статуса (до 30 символов).")
    elif n == 3:
        db.clear_warnings(ctx.user_id, ctx.peer_id, True)
        send_message(ctx.vk, ctx.peer_id, "Предупреждение снято.")
    elif n == 4:
        current = float(user["salary_multiplier"] or 1.0)
        if current >= 7.0: 
            db.update_gems(ctx.user_id, price) # Возврат
            return send_message(ctx.vk, ctx.peer_id, "Максимальный множитель уже достигнут.")
        db.update_user_field(ctx.user_id, "salary_multiplier", current + 0.5)
        send_message(ctx.vk, ctx.peer_id, "Множитель зарплаты повышен.")