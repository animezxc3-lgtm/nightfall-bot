import random
from database import get_user, update_coins

COINS_MULTIPLIERS = [
    (0,    45),
    (0.5,  18),
    (1,    15),
    (1.5,  10),
    (2,     7),
    (3,     3),
    (5,     1.5),
    (10,    0.5),
]


def get_random_multiplier(items=COINS_MULTIPLIERS):
    return random.choices([x[0] for x in items], weights=[x[1] for x in items], k=1)[0]


def casino(user_id, bet):
    """Возвращает (result, mult, error). error=None если игра прошла."""
    user = get_user(user_id)
    if not user:
        return None, None, '❌ Профиль не найден.'
    if bet < 1000:
        return None, None, '❌ Минимальная ставка: 1 000 монет.'
    if bet > user[4]:
        return None, None, f'❌ Недостаточно монет. Баланс: {user[4]:,}.'

    mult = get_random_multiplier()
    result = int(bet * mult)
    update_coins(user_id, result - bet)
    return result, mult, None