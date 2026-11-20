"""
Команды магазина имущества.
"""

from __future__ import annotations

from bot.core.router import router, CommandContext
from bot.services import shop_service
from bot.utils.vk_helpers import send_message


@router.command("магазин", aliases=["shop"])
def cmd_shop(ctx: CommandContext) -> None:
    send_message(ctx.vk, ctx.peer_id, shop_service.shop_overview())


@router.command("дом")
def cmd_housing(ctx: CommandContext) -> None:
    if not ctx.args:
        send_message(ctx.vk, ctx.peer_id, shop_service.category_text("housing"))
        return
    try:
        idx = int(ctx.args_list[0])
    except (ValueError, IndexError):
        send_message(ctx.vk, ctx.peer_id, "Укажи номер: `лл дом <номер>`")
        return
    send_message(ctx.vk, ctx.peer_id, shop_service.buy_by_index(ctx.user_id, "housing", idx))


@router.command("машина", aliases=["авто"])
def cmd_car(ctx: CommandContext) -> None:
    if not ctx.args:
        send_message(ctx.vk, ctx.peer_id, shop_service.category_text("car"))
        return
    try:
        idx = int(ctx.args_list[0])
    except (ValueError, IndexError):
        send_message(ctx.vk, ctx.peer_id, "Укажи номер: `лл машина <номер>`")
        return
    send_message(ctx.vk, ctx.peer_id, shop_service.buy_by_index(ctx.user_id, "car", idx))


@router.command("телефон")
def cmd_phone(ctx: CommandContext) -> None:
    if not ctx.args:
        send_message(ctx.vk, ctx.peer_id, shop_service.category_text("phone"))
        return
    try:
        idx = int(ctx.args_list[0])
    except (ValueError, IndexError):
        send_message(ctx.vk, ctx.peer_id, "Укажи номер: `лл телефон <номер>`")
        return
    send_message(ctx.vk, ctx.peer_id, shop_service.buy_by_index(ctx.user_id, "phone", idx))


@router.command("продать")
def cmd_sell(ctx: CommandContext) -> None:
    if not ctx.args_list:
        send_message(ctx.vk, ctx.peer_id, "Использование: `лл продать дом|машину|телефон`")
        return
    what = ctx.args_list[0].lower()
    mapping = {
        "дом": "housing",
        "жильё": "housing",
        "жилье": "housing",
        "машину": "car",
        "машина": "car",
        "авто": "car",
        "телефон": "phone",
    }
    category = mapping.get(what)
    if not category:
        send_message(ctx.vk, ctx.peer_id, "Можно продать: дом, машину, телефон")
        return
    send_message(ctx.vk, ctx.peer_id, shop_service.sell(ctx.user_id, category))
