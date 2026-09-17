"""Lightweight character reactions for ordinary chat messages."""

import random
import re
import time

# Trigger -> response.
# Matching is case-insensitive and uses word boundaries.
REACTIONS = {
    "британия": "Британия падёт.",
    "бублик": "Кольцо без начала и конца. Интересно.",
    "пингвин": "Почему именно пингвин?..",
    "кактус": "Наконец-то растение, способное постоять за себя.",
    "пельмени": "Даже величайшие планы иногда уступают пельменям.",
    "ход конём": "Иногда лучший ход — тот, которого противник не предусмотрел.",
}

# A per-chat cooldown keeps repeated triggers from flooding the conversation.
COOLDOWN_SECONDS = 30
REACTION_CHANCE = 1.0
_last_reaction = {}


def _matches(text, trigger):
    return re.search(r"(?<!\w)" + re.escape(trigger) + r"(?!\w)", text, re.IGNORECASE) is not None


def maybe_react(text, peer_id, vk):
    text = (text or "").strip()
    if not text or text.lower().startswith("лл"):
        return False

    now = time.monotonic()
    if now - _last_reaction.get(peer_id, 0) < COOLDOWN_SECONDS:
        return False

    for trigger, response in REACTIONS.items():
        if _matches(text, trigger):
            if random.random() > REACTION_CHANCE:
                return False
            try:
                vk.messages.send(peer_id=peer_id, random_id=0, message=response)
                _last_reaction[peer_id] = now
                return True
            except Exception:
                return False
    return False
