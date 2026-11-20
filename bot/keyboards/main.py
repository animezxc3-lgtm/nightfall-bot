"""
Все inline-клавиатуры бота.
"""

from __future__ import annotations
import json
from typing import Any

def _btn(label: str, cmd: str, **extra: Any) -> dict:
    payload = {"cmd": cmd, **extra}
    return {
        "action": {
            "type": "callback",
            "label": label,
            "payload": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        }
    }

def menu_keyboard(is_admin: bool = False, is_creator: bool = False) -> dict:
    rows = [
        [_btn("📋 Основные", "menu_basic")],
        [_btn("❤️ Отношения", "menu_relationships"), _btn("🎭 RP", "menu_rp")],
        [_btn("💼 Работа", "menu_work"), _btn("🎭 Развлечение", "menu_entertainment")],
    ]
    if is_admin: rows[2].append(_btn("👑 Администрирование", "menu_admin"))
    if is_creator: rows.append([_btn("♛ Создатель", "menu_creator")])
    return {"inline": True, "buttons": rows}

def back_to_menu_keyboard() -> dict:
    return {"inline": True, "buttons": [[_btn("⬅️ В меню", "menu_main")]]}

def duel_keyboard() -> dict:
    return {"inline": True, "buttons": [[_btn("✅ Принять", "duel_accept"), _btn("❌ Отказаться", "duel_decline")]]}

def application_review_keyboard(applicant_id: int) -> dict:
    return {"inline": True, "buttons": [[_btn("✅ Принять", "app_accept", applicant=applicant_id), _btn("❌ Отклонить", "app_decline", applicant=applicant_id)]]}

def marriage_proposal_keyboard() -> dict:
    return {"inline": True, "buttons": [[_btn("💍 Согласиться", "marriage_accept"), _btn("❌ Отказаться", "marriage_reject")]]}

def relationship_proposal_keyboard() -> dict:
    return {"inline": True, "buttons": [[_btn("❤️ Согласиться", "relationship_accept"), _btn("❌ Отказаться", "relationship_reject")]]}

def family_proposal_keyboard() -> dict:
    return {"inline": True, "buttons": [[_btn("👪 Принять", "family_accept"), _btn("❌ Отказаться", "family_reject")]]}

def norm_review_keyboard(report_id: int) -> dict:
    return {"inline": True, "buttons": [[_btn("✅ Одобрить", "norm_accept", report_id=report_id), _btn("❌ Отклонить", "norm_decline", report_id=report_id)]]}

def norm_skip_photos_keyboard() -> dict:
    return {"inline": True, "buttons": [[_btn("Пропустить", "norm_skip_photos")]]}

def application_chat_select_keyboard() -> dict:
    from bot.core.config import settings
    buttons = []
    for i, pid in enumerate(settings.main_chats, 1):
        buttons.append([_btn(f"NightFall {i}", "app_chat_select", peer_id=pid)])
    return {"inline": True, "buttons": buttons}

def application_role_select_keyboard(peer_id: int) -> dict:
    return {"inline": True, "buttons": [
        [_btn("⚡ Активист", "app_role_select", peer_id=peer_id, role=2)],
        [_btn("🎯 Рекрутер", "app_role_select", peer_id=peer_id, role=3)],
        [_btn("📱 Админ", "app_role_select", peer_id=peer_id, role=4)]
    ]}