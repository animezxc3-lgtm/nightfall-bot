from datetime import datetime
from bot.core.router import router, CommandContext
from bot.core.config import settings
from bot.services.rp_service import ALL_RP_COMMANDS, handle_rp
from bot.services.relationship_service import get_partner_id, get_display_name
from bot.utils.vk_helpers import send_message, user_mention

ADULT_CMDS = {'подрочить', 'секс', 'футджоб', 'принять душ', 'минет', 'куни', '69'}

def _register():
    for cmd in ALL_RP_COMMANDS:
        def make(c):
            def h(ctx: CommandContext):
                # Проверка 18+
                if c in ADULT_CMDS:
                    is_extra = ctx.peer_id in settings.extra_chats
                    is_citadel = ctx.peer_id == settings.citadel_chat
                    if not is_extra and not is_citadel:
                        if ctx.peer_id not in settings.main_chats: return
                        hour = datetime.now().hour
                        if not (hour >= 23 or hour < 8):
                            return send_message(ctx.vk, ctx.peer_id, "❌ 18+ только с 23:00 до 08:00.")
                
                body, photo = handle_rp(c, ctx.user_id, ctx.args or ctx.text, get_partner_id, get_display_name)
                if body:
                    send_message(ctx.vk, ctx.peer_id, f"{user_mention(ctx.user_id, get_display_name(ctx.user_id) or 'Пользователь')} {body}", attachment=photo)
            return h
        router.command(cmd)(make(cmd))

_register()