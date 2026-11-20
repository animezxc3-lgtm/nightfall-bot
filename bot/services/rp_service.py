"""
RP-команды с фото из альбомов.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Optional

from bot.core.config import settings
from bot.core import database as db
from bot.utils.vk_helpers import parse_target_id, user_mention

logger = logging.getLogger(__name__)

RP_RESPONSES: dict[str, list[str]] = {
    "обнять": ["обнял(а) {target} 🤗", "крепко обнял(а) {target} ❤️"],
    "поцеловать": ["поцеловал(а) {target} 😘", "поцеловал(а) {target} ❤️"],
    "пожать руку": ["пожал(а) руку {target} 🤝", "обменялся(ась) рукопожатием с {target} 🤝"],
    "погладить": ["погладил(а) {target} по голове 🥰", "нежно погладил(а) {target} 🤗"],
    "ущипнуть": ["ущипнул(а) {target} 😈", "ущипнул(а) {target} за щёку 🤭"],
    "укусить": ["укусил(а) {target} 🦷", "легонько укусил(а) {target} 😈"],
    "дать пять": ["дал(а) пять {target} ✋", "и {target} дали пять 🖐️"],
    "пнуть": ["пнул(а) {target} 🦵"],
    "положить в дурку": ["положил(а) {target} в дурку 🏥"],
    "посадить на бутылку": ["посадил(а) {target} на бутылку 😈"],
    "застрелить": ["застрелил(а) {target} 🔫", "пристрелил(а) {target} 💥"],
    "курить": ["закурил(а) вместе с {target} 🚬", "и {target} дымят в сторонке 🚬"],
    "пиво": ["выпил(а) пиво с {target} 🍺", "и {target} распили бутылочку 🍺"],
    "уснуть": ["уснул(а) рядом с {target} 😴"],
    "разбудить": ["разбудил(а) {target} ⏰"],
    "накормить": ["накормил(а) {target} 🍲"],
    "подарить": ["подарил(а) {target} подарок 🎁"],
    "подрочить": ["помог(ла) {target} расслабиться рукой 😏", "ласково подрочил(а) {target} 🍆"],
    "секс": ["страстно занялся(ась) сексом с {target} 🔥", "провёл(а) незабываемую ночь с {target} 🥵"],
    "футджоб": ["сделал(а) {target} приятно ножками 🦶", "подарил(а) {target} наслаждение ступнями 👣"],
    "принять душ": ["принял(а) душ вместе с {target} 🚿", "хорошенько намылил(а) спинку {target} 🧼"],
    "минет": ["сделал(а) {target} приятно ртом 👄", "опустился(ась) перед {target} 🤤"],
    "куни": ["сделал(а) {target} приятно языком 👅", "подарил(а) {target} оральное наслаждение 💦"],
    "69": ["занял(ась) взаимной лаской с {target} 🔄", "попробовал(а) позу 69 с {target} 🛏️"],
}

SELF_RESPONSES: dict[str, str] = {
    "обнять": "обнял(а) себя. Всё так плохо?",
    "поцеловать": "поцеловал(а) себя. Ох уж эти самовлюблённые...",
    "пожать руку": "пожал(а) руку самому себе. Отличный приятель.",
    "погладить": "погладил(а) себя. Хороший мальчик.",
    "ущипнуть": "ущипнул(а) себя. Ну как? Думаешь, спишь?",
    "укусить": "укусил(а) себя. Но с какой целью..?",
    "дать пять": "дал(а) себе пять. Отличная работа!",
    "пнуть": "пнул(а) себя. Приятно?",
    "положить в дурку": "лёг в дурку. Осознание проблемы — первый шаг к её решению.",
    "посадить на бутылку": "сел на бутылку. Похоже, он доволен новым местом.",
    "застрелить": "застрелился. Ну ты и псих.",
    "курить": "закурил(а) в одиночестве. Дым развеется — и ладно.",
    "пиво": "выпил(а) пиво в одиночестве. Похоже, компания — это не его.",
    "уснуть": "уснул(а). Завтра его ждут великие дела.",
    "разбудить": "каким-то чудом разбудил(а) себя. Каковы ощущения?",
    "накормить": "накормил(а) себя. Пожелаем ему приятного аппетита!",
    "подарить": "сделал(а) себе подарок. Интересно, что же он выбрал?",
    "подрочить": "решил(а) заняться самоудовлетворением.",
    "секс": "занялся(ась) самоудовлетворением.",
    "футджоб": "попытался(ась) сделать это сам(а). Гибкость — это талант.",
    "принять душ": "пошёл(пошла) в душ. Хотя бы гигиена соблюдена.",
    "минет": "попытался(ась) сделать это сам(а). Гибкость — это талант.",
    "куни": "попытался(ась) сделать это сам(а). Гибкость — это талант.",
    "69": "попытался(ась) сделать это сам(а). Гибкость — это талант.",
}

ADULT_COMMANDS = frozenset({
    "подрочить", "секс", "футджоб", "принять душ", "минет", "куни", "69",
})

ALL_RP_COMMANDS = frozenset(RP_RESPONSES.keys())


def get_random_rp_photo(command: str) -> Optional[str]:
    """Возвращает attachment случайного фото из кэша для команды."""
    with db.db_cursor() as (_, cur):
        cur.execute(
            "SELECT attachment FROM rp_photos WHERE command = ? ORDER BY RANDOM() LIMIT 1",
            (command,),
        )
        row = cur.fetchone()
        return row["attachment"] if row else None


def handle_rp(
    command: str,
    user_id: int,
    text: str,
    get_partner_id,
    get_display_name,
) -> tuple[Optional[str], Optional[str]]:
    """
    Обрабатывает RP-команду.
    Возвращает (текст_ответа, attachment) или (None, None) если команда неизвестна.
    """
    command = command.lower().strip()
    if command not in ALL_RP_COMMANDS:
        return None, None

    target = parse_target_id(text)

    # Adult-команды только с партнёром
    if command in ADULT_COMMANDS:
        partner = get_partner_id(user_id)
        if target != partner:
            return "❌ Это действие доступно только для твоей второй половинки.", None

    # На себя
    if target is None or target == user_id:
        if target == user_id:
            return "❌ Нельзя использовать это действие на самого себя.", None
        template = SELF_RESPONSES.get(command)
        if not template:
            return None, None
        return template, None

    if not db.user_exists(target):
        return "❌ У пользователя нет профиля.", None

    name = get_display_name(target) or "пользователь"
    target_mention = user_mention(target, name)
    templates = RP_RESPONSES.get(command)
    if not templates:
        return None, None

    body = random.choice(templates).format(target=target_mention)
    photo = None
    if command in settings.rp_albums:
        photo = get_random_rp_photo(command)

    return body, photo
