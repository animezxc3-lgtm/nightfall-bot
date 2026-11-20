"""
Казино и дуэли (базовые).
"""

from __future__ import annotations

from bot.core.router import router, CommandContext
from bot.core import database as db
from bot.services import games_service
from bot.utils.vk_helpers import send_message, parse_target_id, user_mention
from bot.keyboards import duel_keyboard
from bot.services.relationship_service import get_display_name


@router.command("деп", aliases=["рулетка"])
def cmd_casino(ctx: CommandContext) -> None:
    if not ctx.args_list:
        send_message(ctx.vk, ctx.peer_id, "Использование: `лл деп <сумма>` (мин. 1000)")
        return
    try:
        bet = int(ctx.args_list[0].replace(" ", "").replace(",", ""))
    except ValueError:
        send_message(ctx.vk, ctx.peer_id, "Укажи сумму числом.")
        return

    result, mult, err = games_service.casino_bet(ctx.user_id, bet)
    if err:
        send_message(ctx.vk, ctx.peer_id, err)
        return
    assert result is not None and mult is not None
    send_message(
        ctx.vk,
        ctx.peer_id,
        games_service.format_casino_result(bet, result, mult),
    )


@router.command("передать")
def cmd_transfer(ctx: CommandContext) -> None:
    if len(ctx.args_list) < 2:
        send_message(ctx.vk, ctx.peer_id, "Использование: `лл передать @user <сумма>`")
        return
    target = parse_target_id(ctx.args_list[0])
    try:
        amount = int(ctx.args_list[1].replace(" ", ""))
    except ValueError:
        amount = 0
    if not target or amount <= 0:
        return
    if target == ctx.user_id:
        send_message(ctx.vk, ctx.peer_id, "Нельзя передать монеты самому себе.")
        return
    if not db.user_exists(target):
        send_message(ctx.vk, ctx.peer_id, "Пользователь не найден в базе.")
        return

    ok = db.update_coins(ctx.user_id, -amount)
    if not ok:
        send_message(ctx.vk, ctx.peer_id, "Недостаточно монет.")
        return
    db.update_coins(target, amount)
    from_name = get_display_name(ctx.user_id) or "пользователь"
    to_name = get_display_name(target) or "пользователь"
    send_message(
        ctx.vk,
        ctx.peer_id,
        f"{user_mention(ctx.user_id, from_name)} передал(а) "
        f"{user_mention(target, to_name)} {amount:,} 🪙".replace(",", " "),
    )


@router.command("дуэль")
def cmd_duel(ctx: CommandContext) -> None:
    target = parse_target_id(ctx.args)
    if not target:
        send_message(ctx.vk, ctx.peer_id, "Использование: `лл дуэль @user`")
        return
    if target == ctx.user_id:
        send_message(ctx.vk, ctx.peer_id, "Нельзя вызвать на дуэль самого себя.")
        return
    if not db.user_exists(target):
        send_message(ctx.vk, ctx.peer_id, "Пользователь не найден.")
        return

    # Простая запись дуэли
    from datetime import datetime
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM duels WHERE opponent_id = ? OR challenger_id = ?", (target, ctx.user_id))
        cur.execute(
            "INSERT INTO duels (opponent_id, challenger_id, peer_id, created_at) VALUES (?, ?, ?, ?)",
            (target, ctx.user_id, ctx.peer_id, datetime.now().isoformat(timespec="seconds")),
        )

    name = get_display_name(ctx.user_id) or "пользователь"
    send_message(
        ctx.vk,
        ctx.peer_id,
        f"⚔️ {user_mention(ctx.user_id, name)} вызывает на дуэль {user_mention(target)}!",
        keyboard=duel_keyboard(),
    )


@router.button("duel_accept")
def btn_duel_accept(ctx: CommandContext) -> None:
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "SELECT challenger_id, peer_id FROM duels WHERE opponent_id = ?",
            (ctx.user_id,),
        )
        row = cur.fetchone()
        if not row:
            send_message(ctx.vk, ctx.peer_id, "Активная дуэль не найдена.")
            return
        challenger_id = row["challenger_id"]
        peer_id = row["peer_id"]
        cur.execute("DELETE FROM duels WHERE opponent_id = ?", (ctx.user_id,))

    # Простой исход: 50/50
    import random
    winner = ctx.user_id if random.random() < 0.5 else challenger_id
    loser = challenger_id if winner == ctx.user_id else ctx.user_id
    w_name = get_display_name(winner) or "победитель"
    l_name = get_display_name(loser) or "проигравший"
    send_message(
        ctx.vk,
        peer_id,
        f"⚔️ Дуэль!\n{user_mention(winner, w_name)} побеждает {user_mention(loser, l_name)}!",
    )


@router.button("duel_decline")
def btn_duel_decline(ctx: CommandContext) -> None:
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            "SELECT challenger_id, peer_id FROM duels WHERE opponent_id = ?",
            (ctx.user_id,),
        )
        row = cur.fetchone()
        if not row:
            send_message(ctx.vk, ctx.peer_id, "Активная дуэль не найдена.")
            return
        peer_id = row["peer_id"]
        cur.execute("DELETE FROM duels WHERE opponent_id = ?", (ctx.user_id,))
    name = get_display_name(ctx.user_id) or "пользователь"
    send_message(
        ctx.vk,
        peer_id,
        f"❌ {user_mention(ctx.user_id, name)} отклонил(а) дуэль.",
    )
