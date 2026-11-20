from bot.core.router import router, CommandContext
from bot.services import relationship_service as rs
from bot.utils.vk_helpers import send_message, parse_target_id, user_mention
from bot.keyboards import relationship_proposal_keyboard, marriage_proposal_keyboard

@router.command("отношения", aliases=["семья"])
def cmd_status(ctx: CommandContext):
    target = parse_target_id(ctx.args) if ctx.args else ctx.user_id
    if target: send_message(ctx.vk, ctx.peer_id, rs.relationship_status(target))

@router.command("встречаться", aliases=["познакомиться"])
def cmd_start_rel(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target: return send_message(ctx.vk, ctx.peer_id, "Использование: `лл встречаться @user`")
    target_id = int(target)
    ok, err = rs.start_relationship(ctx.user_id, target_id)
    if not ok: return send_message(ctx.vk, ctx.peer_id, err)
    send_message(ctx.vk, ctx.peer_id, f"{user_mention(ctx.user_id)} предлагает отношения {user_mention(target_id)}.", keyboard=relationship_proposal_keyboard())

@router.command("расстаться")
def cmd_breakup(ctx: CommandContext):
    send_message(ctx.vk, ctx.peer_id, rs.end_relationship(ctx.user_id))

@router.command("развод")
def cmd_divorce(ctx: CommandContext):
    send_message(ctx.vk, ctx.peer_id, rs.divorce(ctx.user_id))

@router.command("создать брак", aliases=["брак"])
def cmd_propose_marriage(ctx: CommandContext):
    if len(ctx.args_list) < 2: return send_message(ctx.vk, ctx.peer_id, "Использование: `лл создать брак @user Фамилия`")
    target = parse_target_id(ctx.args_list[0])
    if not target: return
    target_id = int(target)
    surname = " ".join(ctx.args_list[1:]).strip()
    ok, err = rs.propose_marriage(ctx.user_id, target_id, surname)
    if not ok: return send_message(ctx.vk, ctx.peer_id, err)
    send_message(ctx.vk, ctx.peer_id, f"💍 Предложение брака {user_mention(target_id)} с фамилией «{surname}».", keyboard=marriage_proposal_keyboard())

@router.command("уйти из семьи", aliases=["покинуть семью"])
def cmd_leave_family(ctx: CommandContext):
    send_message(ctx.vk, ctx.peer_id, rs.leave_family(ctx.user_id))

@router.command("усыновить", aliases=["удочерить"])
def cmd_adopt(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target: return send_message(ctx.vk, ctx.peer_id, "Использование: `лл усыновить @user`")
    target_id = int(target)
    ok, err = rs.adopt_child(ctx.user_id, target_id)
    send_message(ctx.vk, ctx.peer_id, err)

@router.command("выгнать из семьи", aliases=["отправить в детдом"])
def cmd_kick_family(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target: return send_message(ctx.vk, ctx.peer_id, "Использование: `лл выгнать из семьи @user`")
    target_id = int(target)
    rs.remove_child(ctx.user_id, target_id)
    send_message(ctx.vk, ctx.peer_id, "Ребёнок больше не в семье.")

@router.command("цем", aliases=["поцеловаться"])
def cmd_kiss_partner(ctx: CommandContext):
    partner = rs.get_partner_id(ctx.user_id)
    if not partner:
        return send_message(ctx.vk, ctx.peer_id, "У тебя нет партнёра.")
    send_message(
        ctx.vk, ctx.peer_id,
        f"{user_mention(ctx.user_id)} поцеловал(а) {user_mention(partner)} 😘",
    )


@router.command("свидание")
def cmd_date(ctx: CommandContext):
    partner = rs.get_partner_id(ctx.user_id)
    if not partner:
        return send_message(ctx.vk, ctx.peer_id, "У тебя нет партнёра.")
    send_message(
        ctx.vk, ctx.peer_id,
        f"{user_mention(ctx.user_id)} пригласил(а) {user_mention(partner)} на свидание 🌹",
    )
