"""
Команды работы.
"""

from __future__ import annotations

from bot.core.router import router, CommandContext
from bot.services import work_service
from bot.services.relationship_service import get_display_name
from bot.utils.vk_helpers import send_message, parse_target_id, user_mention
from bot.keyboards.main import _btn


def _profession_keyboard() -> dict:
    buttons = []
    row = []
    for key, data in work_service.PROFESSIONS.items():
        row.append(_btn(data["name"], "hire", profession=key))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return {"inline": True, "buttons": buttons}


@router.command("устроиться")
def cmd_hire_menu(ctx: CommandContext) -> None:
    send_message(
        ctx.vk,
        ctx.peer_id,
        "Выбери профессию:",
        keyboard=_profession_keyboard(),
    )


@router.command("работать")
def cmd_work(ctx: CommandContext) -> None:
    text, promoted = work_service.work(ctx.user_id)
    name = get_display_name(ctx.user_id) or "пользователь"
    msg = f"{user_mention(ctx.user_id, name)} {text}"
    if promoted:
        msg += f"\n🎉 {user_mention(ctx.user_id, name)} {promoted}"
    send_message(ctx.vk, ctx.peer_id, msg)


@router.command("уволиться")
def cmd_fire(ctx: CommandContext) -> None:
    send_message(ctx.vk, ctx.peer_id, work_service.fire(ctx.user_id))


@router.command("работа")
def cmd_job_stats(ctx: CommandContext) -> None:
    target = parse_target_id(ctx.args) if ctx.args else ctx.user_id
    if not target:
        return
    result = work_service.job_stats(target, ctx.user_id)
    if result:
        send_message(ctx.vk, ctx.peer_id, result)
