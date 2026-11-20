import datetime as dt
from bot.core.router import router, CommandContext
from bot.core import database as db
from bot.core.config import settings
from bot.services.user_service import UserService
from bot.services.admin_service import AdminService
from bot.utils.vk_helpers import send_message, parse_target_id, user_mention
from bot.keyboards import menu_keyboard


@router.command("меню")
def cmd_menu(ctx: CommandContext):
    admin = AdminService()
    send_message(
        ctx.vk,
        ctx.peer_id,
        "📖 Меню Lelouch Bot\n\nВыбери нужный раздел ниже.",
        keyboard=menu_keyboard(
            admin.is_admin(ctx.user_id, ctx.peer_id),
            admin.is_creator(ctx.user_id),
        ),
    )


@router.command("помощь", aliases=["команды", "help"])
def cmd_help(ctx: CommandContext):
    cmd_menu(ctx)


@router.command("профиль")
def cmd_profile(ctx: CommandContext):
    target = parse_target_id(ctx.args) if ctx.args else ctx.user_id
    if not target:
        return
    service = UserService(ctx.vk)
    service.ensure(target)
    text, attachment = service.get_profile_text(target, ctx.peer_id)
    send_message(ctx.vk, ctx.peer_id, text, attachment=attachment)


@router.command("баланс")
def cmd_balance(ctx: CommandContext):
    target = parse_target_id(ctx.args) if ctx.args else ctx.user_id
    if not target:
        return
    service = UserService(ctx.vk)
    service.ensure(target)
    send_message(ctx.vk, ctx.peer_id, service.get_balance_text(target))


@router.command("активность")
def cmd_activity(ctx: CommandContext):
    target = parse_target_id(ctx.args) if ctx.args else ctx.user_id
    if not target:
        return
    service = UserService(ctx.vk)
    service.ensure(target)
    name = service.get_balance_text  # just ensure
    from bot.services.relationship_service import get_display_name
    display = get_display_name(target) or "пользователь"
    header = f"Статистика сообщений {user_mention(target, display)}:\n"
    body = service.get_activity_text(target)
    # body starts with 📊 — strip first line if present for cleaner join
    lines = body.split("\n")
    if lines and lines[0].startswith("📊"):
        body = "\n".join(lines[1:])
    send_message(ctx.vk, ctx.peer_id, header + body)


@router.command("ник")
def cmd_nickname(ctx: CommandContext):
    if not ctx.args:
        return send_message(ctx.vk, ctx.peer_id, "Использование: лл ник <новый ник>")
    service = UserService(ctx.vk)
    service.ensure(ctx.user_id)
    if service.set_nickname(ctx.user_id, ctx.args):
        send_message(
            ctx.vk,
            ctx.peer_id,
            f"Ваш новый никнейм: {user_mention(ctx.user_id, ctx.args.strip())}",
        )
    else:
        send_message(ctx.vk, ctx.peer_id, "Ник должен быть от 1 до 30 символов.")


@router.command("топ")
def cmd_top(ctx: CommandContext):
    parts = (ctx.args or "").replace("+", " ").split()
    if not parts:
        return send_message(
            ctx.vk,
            ctx.peer_id,
            "Пример: лл топ монеты\nлл топ активность здесь день",
        )
    cat = parts[0].lower()

    if cat == "активность":
        scope = parts[1] if len(parts) > 1 else "здесь"
        period = parts[2] if len(parts) > 2 else "все время"
        with db.db_cursor() as (_, cur):
            if period == "день":
                cond, p = "date=?", (dt.date.today().isoformat(),)
            elif period == "неделя":
                cond, p = (
                    "date>=?",
                    (
                        (
                            dt.date.today()
                            - dt.timedelta(days=dt.date.today().weekday())
                        ).isoformat(),
                    ),
                )
            elif period == "месяц":
                cond, p = "date>=?", (dt.date.today().replace(day=1).isoformat(),)
            else:
                cond, p = "1=1", ()

            if scope == "здесь":
                cur.execute(
                    f"SELECT user_id, SUM(count) as c FROM chat_message_stats "
                    f"WHERE peer_id=? AND {cond} GROUP BY user_id ORDER BY c DESC LIMIT 10",
                    (ctx.peer_id, *p),
                )
            else:
                cur.execute(
                    f"SELECT user_id, SUM(count) as c FROM messages_stats "
                    f"WHERE {cond} GROUP BY user_id ORDER BY c DESC LIMIT 10",
                    p,
                )
            rows = cur.fetchall()

        lines = [f"🏆 Топ активности ({scope}, {period})", ""]
        for i, r in enumerate(rows, 1):
            lines.append(f"{i}. {user_mention(r['user_id'])} — {r['c']}")
        if not rows:
            lines.append("Пусто.")
        send_message(ctx.vk, ctx.peer_id, "\n".join(lines))
        return

    if cat in ("монеты", "сила", "камни"):
        fld = {"монеты": "coins", "сила": "power", "камни": "soul_gems"}[cat]
        with db.db_cursor() as (_, cur):
            cur.execute(
                f"SELECT user_id, {fld} FROM users WHERE {fld}>0 ORDER BY {fld} DESC LIMIT 10"
            )
            rows = cur.fetchall()
        lines = [f"🏆 Топ {cat}", ""]
        for i, r in enumerate(rows, 1):
            lines.append(f"{i}. {user_mention(r['user_id'])} — {r[fld]}")
        if not rows:
            lines.append("Пусто.")
        send_message(ctx.vk, ctx.peer_id, "\n".join(lines))
        return

    send_message(ctx.vk, ctx.peer_id, "Доступные топы: монеты, сила, камни, активность")


# ─── Создатель: выдать / отобрать ─────────────────────────
RESOURCE_MAP = {
    "монеты": ("coins", "монет"),
    "гиас": ("power", "силы Гиаса"),
    "камни": ("soul_gems", "камней души"),
}


@router.command("выдать", creator_only=True)
def cmd_give(ctx: CommandContext):
    parts = ctx.args_list
    if len(parts) < 3:
        return send_message(
            ctx.vk,
            ctx.peer_id,
            "Использование: лл выдать <монеты|гиас|камни> @user <кол-во>",
        )
    resource = parts[0].lower()
    if resource not in RESOURCE_MAP:
        return
    target = parse_target_id(parts[1])
    try:
        amount = int(parts[2].replace(" ", "").replace(",", ""))
    except ValueError:
        amount = 0
    if not target or amount <= 0:
        return
    if not db.user_exists(target):
        db.create_user(target)
    field, label = RESOURCE_MAP[resource]
    if field == "coins":
        db.update_coins(target, amount)
    elif field == "power":
        db.update_power(target, amount)
    else:
        db.update_gems(target, amount)
    send_message(
        ctx.vk,
        ctx.peer_id,
        f"Создатель выдал у {user_mention(target)} {amount} {label}.",
    )


@router.command("отобрать", creator_only=True)
def cmd_take(ctx: CommandContext):
    parts = ctx.args_list
    if len(parts) < 3:
        return send_message(
            ctx.vk,
            ctx.peer_id,
            "Использование: лл отобрать <монеты|гиас|камни> @user <кол-во>",
        )
    resource = parts[0].lower()
    if resource not in RESOURCE_MAP:
        return
    target = parse_target_id(parts[1])
    try:
        amount = int(parts[2].replace(" ", "").replace(",", ""))
    except ValueError:
        amount = 0
    if not target or amount <= 0:
        return
    field, label = RESOURCE_MAP[resource]
    with db.db_cursor(commit=True) as (_, cur):
        cur.execute(
            f"UPDATE users SET {field}=COALESCE({field},0)-? "
            f"WHERE user_id=? AND COALESCE({field},0)>=?",
            (amount, target, amount),
        )
        if cur.rowcount != 1:
            return send_message(ctx.vk, ctx.peer_id, "Недостаточно ресурсов у цели.")
    send_message(
        ctx.vk,
        ctx.peer_id,
        f"Создатель отобрал у {user_mention(target)} {amount} {label}.",
    )
