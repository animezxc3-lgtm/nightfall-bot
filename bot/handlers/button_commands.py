from __future__ import annotations
import logging
from bot.core.router import router, CommandContext
from bot.services.admin_service import AdminService
from bot.keyboards import menu_keyboard, back_to_menu_keyboard
from bot.utils.vk_helpers import send_message, edit_message, user_mention
from bot.services.relationship_service import get_display_name

logger = logging.getLogger(__name__)


def _edit_or_send(ctx: CommandContext, text: str, keyboard: dict | None = None):
    cmid = ctx.payload.get("_conversation_message_id")
    if cmid and edit_message(ctx.vk, ctx.peer_id, int(cmid), text, keyboard=keyboard):
        return
    send_message(ctx.vk, ctx.peer_id, text, keyboard=keyboard)


def _menu_kb(ctx: CommandContext) -> dict:
    admin = AdminService()
    return menu_keyboard(
        admin.is_admin(ctx.user_id, ctx.peer_id),
        admin.is_creator(ctx.user_id),
    )


@router.button("menu_main")
def btn_menu_main(ctx: CommandContext):
    _edit_or_send(
        ctx,
        "📖 Меню Lelouch Bot\n\nВыбери нужный раздел ниже.",
        _menu_kb(ctx),
    )


@router.button("menu_basic")
def btn_menu_basic(ctx: CommandContext):
    text = (
        "📋 ОСНОВНЫЕ КОМАНДЫ\n\n"
        "👤 Статистика\n"
        "▪ лл профиль\n"
        "▪ лл ник <новый ник>\n"
        "▪ лл баланс\n"
        "▪ лл активность\n"
        "▪ лл топ активность + <здесь|везде> <день|неделя|месяц|все время>\n"
        "▪ лл топ <монеты|сила гиаса|камни души>\n"
        "▪ лл <семья> + \"ID\"\n\n"
        "👥 Социальное\n"
        "▪ лл передать \"ID\" <сумма>\n\n"
        "🏠 Имущество\n"
        "▪ лл магазин\n"
        "▪ лл купить дом | машину | телефон <номер>\n"
        "▪ лл продать дом | машину | телефон"
    )
    _edit_or_send(ctx, text, back_to_menu_keyboard())


@router.button("menu_relationships")
def btn_menu_relationships(ctx: CommandContext):
    text = (
        "💛 Команды отношений\n"
        "▪ лл <семья> + \"ID\"\n"
        "▪ лл <встречаться> + \"ID\"\n\n"
        "👫 Команды для парочек\n"
        "▪ лл <свидание>\n"
        "▪ лл <цем|поцеловаться>\n"
        "▪ лл <брак> + \"Фамилия семьи\"\n"
        "▪ лл <расстаться>\n\n"
        "💍 Команды для обручённых\n"
        "▪ лл <усыновить|удочерить> + \"ID\"\n"
        "▪ лл <выгнать из семьи|отправить в детдом> + \"ID\"\n"
        "▪ лл <развод>\n\n"
        "👶 Команды для детей\n"
        "▪ лл <покинуть семью>\n\n"
        "🔥 Команды для второй половинки\n"
        "▪ лл <подрочить>\n"
        "▪ лл <секс>\n"
        "▪ лл <разбудить>\n"
        "▪ лл <уснуть>\n"
        "▪ лл <принять душ>\n"
        "▪ лл <футджоб>\n"
        "▪ лл <минет>\n"
        "▪ лл <куни>\n"
        "▪ лл <69>"
    )
    _edit_or_send(ctx, text, back_to_menu_keyboard())


@router.button("menu_rp")
def btn_menu_rp(ctx: CommandContext):
    text = (
        "🎭 RP-КОМАНДЫ\n\n"
        "лл обнять @user\n"
        "лл поцеловать @user\n"
        "лл пожать руку @user\n"
        "лл погладить @user\n"
        "лл ущипнуть @user\n"
        "лл укусить @user\n"
        "лл дать пять @user\n"
        "лл пнуть @user\n"
        "лл положить в дурку @user\n"
        "лл застрелить @user\n"
        "лл посадить на бутылку @user\n"
        "лл уснуть [@user]\n"
        "лл разбудить @user\n"
        "лл накормить @user\n"
        "лл подарить @user\n"
        "лл курить [@user]\n"
        "лл пиво [@user]"
    )
    _edit_or_send(ctx, text, back_to_menu_keyboard())


@router.button("menu_work")
def btn_menu_work(ctx: CommandContext):
    text = (
        "💼 КОМАНДЫ РАБОТЫ\n\n"
        "лл устроиться\n"
        "лл работать\n"
        "лл уволиться\n"
        "лл работа [@user]\n\n"
        "💡 Множитель зарплаты можно повысить в VIP-магазине."
    )
    _edit_or_send(ctx, text, back_to_menu_keyboard())


@router.button("menu_entertainment")
def btn_menu_entertainment(ctx: CommandContext):
    text = (
        "🎭 РАЗВЛЕЧЕНИЯ\n\n"
        "⚔️ Дуэли:\n"
        "лл дуэль @user\n\n"
        "🎰 Казино:\n"
        "лл деп <сумма>\n"
        "лл рулетка <сумма>\n\n"
        "💡 Минимальная ставка: 1 000 🪙"
    )
    _edit_or_send(ctx, text, back_to_menu_keyboard())


@router.button("menu_admin")
def btn_menu_admin(ctx: CommandContext):
    admin = AdminService()
    if not admin.is_admin(ctx.user_id, ctx.peer_id):
        return _edit_or_send(
            ctx,
            "Этот раздел доступен только администраторам.",
            back_to_menu_keyboard(),
        )
    text = (
        "👑 АДМИНИСТРАТИВНЫЕ КОМАНДЫ\n\n"
        "🛡 МОДЕРАЦИЯ:\n"
        "лл пред @user\n"
        "лл анпред @user\n"
        "лл фулл анпред @user\n"
        "лл кик @user\n"
        "лл фулл кик @user\n"
        "лл бан @user\n"
        "лл разбан @user\n"
        "лл чистка [30-80] (в воскресенье)\n\n"
        "👥 УПРАВЛЕНИЕ:\n"
        "лл админы\n"
        "лл админ стат\n"
        "лл проверить @user\n"
        "лл снять @user\n"
        "лл выдать права @user <номер_беседы или Анархия/Казино> <должность>\n"
        "лл чс адм @user\n"
        "лл убрать чс адм @user\n\n"
        "📊 НОРМЫ И ОТЧЁТЫ:\n"
        "лл отчет (в ЛС бота)\n\n"
        "👥 ТВИНКИ:\n"
        "лл твинк @user\n"
        "лл твинк убрать @user\n"
        "лл твинки [@user]\n\n"
        "🖼 ОФОРМЛЕНИЕ:\n"
        "лл аватар @user <ID фото>\n"
        "лл обновить рп\n"
        "лл изменить приветствие <ID фото из альбома> <текст>\n"
        "лл приветствие\n\n"
        "📊 СТАТИСТИКА:\n"
        "лл беседа\n"
        "лл беседы\n"
        "лл админ стат"
    )
    _edit_or_send(ctx, text, back_to_menu_keyboard())


@router.button("menu_creator")
def btn_menu_creator(ctx: CommandContext):
    if not AdminService().is_creator(ctx.user_id):
        return _edit_or_send(
            ctx,
            "Этот раздел доступен только создателю.",
            back_to_menu_keyboard(),
        )
    text = (
        "♛ КОМАНДЫ СОЗДАТЕЛЯ\n\n"
        "💰 ВЫДАЧА РЕСУРСОВ:\n"
        "лл выдать монеты @user <количество>\n"
        "лл выдать гиас @user <количество>\n"
        "лл выдать камни @user <количество>\n\n"
        "➖ ИЗЪЯТИЕ РЕСУРСОВ:\n"
        "лл отобрать монеты @user <количество>\n"
        "лл отобрать гиас @user <количество>\n"
        "лл отобрать камни @user <количество>\n\n"
        "⚙️ УПРАВЛЕНИЕ:\n"
        "лл настроить набор (в ЛС)"
    )
    _edit_or_send(ctx, text, back_to_menu_keyboard())


@router.button("relationship_accept")
def btn_rel_accept(ctx: CommandContext):
    from bot.services.relationship_service import accept_relationship
    _edit_or_send(ctx, accept_relationship(ctx.user_id))


@router.button("relationship_reject")
def btn_rel_reject(ctx: CommandContext):
    from bot.services.relationship_service import reject_relationship
    _edit_or_send(ctx, reject_relationship(ctx.user_id))


@router.button("marriage_accept")
def btn_mar_accept(ctx: CommandContext):
    from bot.services.relationship_service import accept_marriage
    _edit_or_send(ctx, accept_marriage(ctx.user_id))


@router.button("marriage_reject")
def btn_mar_reject(ctx: CommandContext):
    from bot.services.relationship_service import reject_marriage
    _edit_or_send(ctx, reject_marriage(ctx.user_id))


@router.button("hire")
def btn_hire(ctx: CommandContext):
    from bot.services import work_service
    profession = ctx.payload.get("profession")
    if not profession:
        return
    result = work_service.hire(ctx.user_id, profession)
    name = get_display_name(ctx.user_id) or "Пользователь"
    _edit_or_send(ctx, f"{user_mention(ctx.user_id, name)} {result}")
