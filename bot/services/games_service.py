"""
Казино и простые игры.
"""

from __future__ import annotations

import random
from typing import Optional

from bot.core import database as db

MIN_BET = 1_000

# (множитель, вес)
COINS_MULTIPLIERS = [
    (0, 45),
    (0.5, 18),
    (1, 15),
    (1.5, 10),
    (2, 7),
    (3, 3),
    (5, 1.5),
    (10, 0.5),
]


def _random_multiplier() -> float:
    values = [m for m, _ in COINS_MULTIPLIERS]
    weights = [w for _, w in COINS_MULTIPLIERS]
    return random.choices(values, weights=weights, k=1)[0]


def casino_bet(user_id: int, bet: int) -> tuple[Optional[int], Optional[float], Optional[str]]:
    """
    Возвращает (выигрыш_сумма, множитель, ошибка).
    выигрыш_сумма — сколько получил игрок (0 при проигрыше).
    """
    user = db.get_user(user_id)
    if not user:
        return None, None, "Профиль не найден."

    coins = int(user["coins"] or 0)
    if bet < MIN_BET:
        return None, None, f"Минимальная ставка: {_fmt(MIN_BET)} монет."
    if bet > coins:
        return None, None, "Недостаточно монет."

    mult = _random_multiplier()
    result = int(bet * mult)
    db.update_coins(user_id, result - bet)
    return result, mult, None


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def format_casino_result(bet: int, result: int, mult: float) -> str:
    if mult == 0:
        return (
            f"🎰 Ставка: {_fmt(bet)} 🪙\n"
            f"Множитель: ×{mult}\n"
            f"💔 Проигрыш. Баланс уменьшен на {_fmt(bet)} 🪙"
        )
    if mult < 1:
        return (
            f"🎰 Ставка: {_fmt(bet)} 🪙\n"
            f"Множитель: ×{mult}\n"
            f"📉 Частичный возврат: {_fmt(result)} 🪙"
        )
    if mult == 1:
        return (
            f"🎰 Ставка: {_fmt(bet)} 🪙\n"
            f"Множитель: ×{mult}\n"
            f"😐 Ставка возвращена."
        )
    return (
        f"🎰 Ставка: {_fmt(bet)} 🪙\n"
        f"Множитель: ×{mult}\n"
        f"🎉 Выигрыш: {_fmt(result)} 🪙"
    )
