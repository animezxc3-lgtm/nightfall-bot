"""Полный набор админ-команд (логика и тексты из старого бота)."""
from __future__ import annotations
import logging
import re
from datetime import datetime

from bot.core.router import router, CommandContext
from bot.core import database as db
from bot.core.config import settings
from bot.services.admin_service import AdminService
from bot.utils.vk_helpers import send_message, parse_target_id, user_mention, get_user_name

logger = logging.getLogger(__name__)

ROLE_NAMES = {
    1: "Стажёр",
    2: "Активист",
    3: "Рекрутер",
    4: "Администратор",
    5: "Куратор",
    6: "Вершитель правосудия",
    7: "Лелуш ви Британия",
}

ROLE_WORDS = {
    "стажёр": 1, "стажер": 1,
    "активист": 2,
    "рекрутер": 3,
    "админ": 4, "администратор": 4,
    "куратор": 5,
    "вершитель": 6, "вершитель правосудия": 6,
    "лелуш": 7, "создатель": 7,
}


def log_to_control(vk, text: str):
    try:
        send_message(vk, settings.control_chat, text)
    except Exception as e:
        logger.warning("log_to_control: %s", e)


def _link(vk, uid: int) -> str:
    name = get_user_name(vk, uid)
    from bot.services.relationship_service import get_display_name
    label = get_display_name(uid) or name
    return user_mention(uid, label)


def _chat_title(vk, peer_id: int) -> str:
    try:
        data = vk.messages.getConversationsById(peer_ids=peer_id).get("items", [])
        if data:
            return data[0].get("chat_settings", {}).get("title") or f"Беседа {peer_id}"
    except Exception:
        pass
    return f"Беседа {peer_id}"


def _level(uid: int, peer: int | None = None) -> int:
    return AdminService().get_level(uid, peer)


def _can_act(actor: int, target: int, peer: int) -> bool:
    if actor == target:
        return False
    a, t = _level(actor, peer), _level(target, peer)
    if a in (2, 3, 4) and t in (2, 3, 4):
        return False
    return t < a


def _ensure(vk, uid: int):
    if not db.user_exists(uid):
        db.create_user(uid, get_user_name(vk, uid))


def _fmt_date(s) -> str:
    if not s:
        return "—"
    s = str(s)[:10]
    try:
        y, m, d = s.split("-")
        return f"{d}.{m}.{y}"
    except Exception:
        return s


# ─── Модерация ───────────────────────────────────────────

@router.command("пред", admin_level=2)
def cmd_warn(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return send_message(ctx.vk, ctx.peer_id, "Использование: лл пред @user")
    if not _can_act(ctx.user_id, target, ctx.peer_id):
        return send_message(ctx.vk, ctx.peer_id, "Недостаточно прав")
    _ensure(ctx.vk, target)
    n = db.add_warning(target, ctx.peer_id, True)
    t, a = _link(ctx.vk, target), _link(ctx.vk, ctx.user_id)
    title = _chat_title(ctx.vk, ctx.peer_id)
    if n >= 3:
        db.add_kick_event(target, ctx.peer_id, ctx.user_id)
        try:
            ctx.vk.messages.removeChatUser(chat_id=ctx.peer_id - 2000000000, user_id=target)
        except Exception:
            pass
        db.annul_warnings(target, ctx.peer_id)
        send_message(ctx.vk, ctx.peer_id, f"{a} выдал предупреждение {t}. Теперь у него 3/3. {t} исключён, предупреждения аннулированы.")
        log_to_control(ctx.vk, f"⚠️ Предупреждение 3/3 (Кик)\nБеседа: {title}\nАдмин: {a}\nНарушитель: {t}")
    else:
        send_message(ctx.vk, ctx.peer_id, f"{a} выдал предупреждение {t}. Теперь у него {n}/3.")
        log_to_control(ctx.vk, f"⚠️ Предупреждение {n}/3\nБеседа: {title}\nАдмин: {a}\nНарушитель: {t}")


@router.command("анпред", admin_level=5)
def cmd_unwarn(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return
    _ensure(ctx.vk, target)
    left = db.remove_warning(target, ctx.peer_id, True)
    t, a = _link(ctx.vk, target), _link(ctx.vk, ctx.user_id)
    send_message(ctx.vk, ctx.peer_id, f"{a} снял пред у {t}. У него стало {left}/3.")
    log_to_control(ctx.vk, f"✅ Снятие преда\nБеседа: {_chat_title(ctx.vk, ctx.peer_id)}\nАдмин: {a}\nПользователь: {t} (осталось {left}/3)")


@router.command("фулл анпред", admin_level=5)
def cmd_full_unwarn(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return
    _ensure(ctx.vk, target)
    db.clear_warnings(target, ctx.peer_id, True)
    t, a = _link(ctx.vk, target), _link(ctx.vk, ctx.user_id)
    send_message(ctx.vk, ctx.peer_id, f"{a} снял все предупреждения у {t}.")
    log_to_control(ctx.vk, f"✅ Снятие всех предов\nБеседа: {_chat_title(ctx.vk, ctx.peer_id)}\nАдмин: {a}\nПользователь: {t}")


@router.command("кик", admin_level=2)
def cmd_kick(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return
    if _level(target, ctx.peer_id) > 0 or db.get_global_role(target) > 0:
        return send_message(ctx.vk, ctx.peer_id, "Нельзя наказать администратора.")
    if not _can_act(ctx.user_id, target, ctx.peer_id):
        return send_message(ctx.vk, ctx.peer_id, "Недостаточно прав")
    _ensure(ctx.vk, target)
    db.add_kick_event(target, ctx.peer_id, ctx.user_id)
    t, a = _link(ctx.vk, target), _link(ctx.vk, ctx.user_id)
    try:
        ctx.vk.messages.removeChatUser(chat_id=ctx.peer_id - 2000000000, user_id=target)
        send_message(ctx.vk, ctx.peer_id, f"{a} исключил {t} из беседы.")
        log_to_control(ctx.vk, f"👢 Кик\nБеседа: {_chat_title(ctx.vk, ctx.peer_id)}\nАдмин: {a}\nПользователь: {t}")
    except Exception as e:
        send_message(ctx.vk, ctx.peer_id, f"Ошибка кика: {e}")


@router.command("фулл кик", admin_level=5)
def cmd_full_kick(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return
    if _level(target, ctx.peer_id) > 0 or db.get_global_role(target) > 0:
        return send_message(ctx.vk, ctx.peer_id, "Нельзя наказать администратора.")
    if not _can_act(ctx.user_id, target, ctx.peer_id):
        return send_message(ctx.vk, ctx.peer_id, "Недостаточно прав")
    _ensure(ctx.vk, target)
    db.add_kick_event(target, ctx.peer_id, ctx.user_id)
    kicked = 0
    for peer in db.get_all_chats():
        if peer in (settings.applications_peer_id, ctx.peer_id):
            continue
        try:
            members = ctx.vk.messages.getConversationMembers(peer_id=peer).get("items", [])
            if any(m.get("member_id") == target for m in members):
                ctx.vk.messages.removeChatUser(chat_id=peer - 2000000000, user_id=target)
                kicked += 1
        except Exception:
            pass
    try:
        ctx.vk.messages.removeChatUser(chat_id=ctx.peer_id - 2000000000, user_id=target)
        kicked += 1
    except Exception:
        pass
    t, a = _link(ctx.vk, target), _link(ctx.vk, ctx.user_id)
    send_message(ctx.vk, ctx.peer_id, f"{a} исключил {t} из {kicked} бесед.")
    log_to_control(ctx.vk, f"👢 Фулл кик\nБеседа: {_chat_title(ctx.vk, ctx.peer_id)}\nАдмин: {a}\nПользователь: {t}\nБесед: {kicked}")


@router.command("бан", admin_level=5)
def cmd_ban(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return
    if _level(target, ctx.peer_id) > 0 or db.get_global_role(target) > 0:
        return send_message(ctx.vk, ctx.peer_id, "Нельзя забанить администратора.")
    if not _can_act(ctx.user_id, target, ctx.peer_id):
        return send_message(ctx.vk, ctx.peer_id, "Недостаточно прав")
    _ensure(ctx.vk, target)
    db.ban_user(target)
    db.add_kick_event(target, ctx.peer_id, ctx.user_id)
    for peer in db.get_all_chats():
        try:
            ctx.vk.messages.removeChatUser(chat_id=peer - 2000000000, user_id=target)
        except Exception:
            pass
    t, a = _link(ctx.vk, target), _link(ctx.vk, ctx.user_id)
    send_message(ctx.vk, ctx.peer_id, "Пользователь забанен и исключён из всех бесед.")
    log_to_control(ctx.vk, f"⛔ Бан\nБеседа: {_chat_title(ctx.vk, ctx.peer_id)}\nАдмин: {a}\nПользователь: {t}")


@router.command("разбан", admin_level=5)
def cmd_unban(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return
    _ensure(ctx.vk, target)
    db.unban_user(target)
    t, a = _link(ctx.vk, target), _link(ctx.vk, ctx.user_id)
    send_message(ctx.vk, ctx.peer_id, f"{a} разбанил {t}.")
    log_to_control(ctx.vk, f"✅ Разбан\nАдмин: {a}\nПользователь: {t}")


# ─── Проверка / админы / стат ────────────────────────────

@router.command("проверить", admin_level=2)
def cmd_check(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return send_message(ctx.vk, ctx.peer_id, "Использование: лл проверить @user")
    _ensure(ctx.vk, target)
    u = db.get_user(target)
    if not u:
        return send_message(ctx.vk, ctx.peer_id, "Пользователь не найден.")
    inviter = db.get_first_inviter(target)
    inviter_line = _link(ctx.vk, inviter) if inviter else "—"
    level = _level(target, ctx.peer_id)
    rights = ROLE_NAMES.get(level, "Участник")
    adm_w = db.get_warning_stats(target, True)
    w = db.get_warning_stats(target, False)
    kicks = db.get_kick_stats(target)
    msgs = db.get_messages_stats(target)
    last = db.get_last_message_at(target) or "—"
    lines = [
        f"👤 {_link(ctx.vk, target)}",
        f"Пригласивший в первый раз: {inviter_line}",
        f"Дата создания профиля: {_fmt_date(u['join_date'] if 'join_date' in u.keys() else None)}",
        f"⚙️ Права: {rights}",
        "",
        "─────────✦─────────",
        f"Находится ли в бане: {'Да' if db.is_banned(target) else 'Нет'}",
        f"Находится ли в ЧС Администрации: {'Да' if db.is_in_admin_blacklist(target) else 'Нет'}",
        "",
        "Адм. предупреждений: ",
        f"▪За неделю - {adm_w['week']}",
        f"▪За месяц - {adm_w['month']}",
        f"▪За все время - {adm_w['total']}",
        "Предупреждений: ",
        f"▪За неделю - {w['week']}",
        f"▪За месяц - {w['month']}",
        f"▪За все время - {w['total']}",
        "Был исключен: ",
        f"▪За неделю - {kicks['week']}",
        f"▪За месяц - {kicks['month']}",
        f"▪За все время - {kicks['total']}",
        "",
        "─────────✦─────────",
        "Активность по сообщениям:",
        f"▪За все время: {msgs.get('total', 0)}",
        f"▪За месяц: {msgs.get('month', 0)}",
        f"▪За неделю: {msgs.get('week', 0)}",
        f"▪За день: {msgs.get('today', 0)}",
        f"▪Последнее сообщение: {last}",
    ]
    send_message(ctx.vk, ctx.peer_id, "\n".join(lines))


@router.command("админы", admin_level=1)
def cmd_admins(ctx: CommandContext):
    rows = db.get_admins_for_chat(ctx.peer_id)
    global_rows = db.get_all_global_roles()
    by_level: dict[int, list] = {}
    for r in rows:
        by_level.setdefault(int(r["level"]), []).append(int(r["user_id"]))
    for r in global_rows:
        lvl = int(r["level"])
        uid = int(r["user_id"])
        by_level.setdefault(lvl, [])
        if uid not in by_level[lvl]:
            by_level[lvl].append(uid)
    if not by_level:
        return send_message(ctx.vk, ctx.peer_id, "Администраторов нет.")
    lines = ["👑 Администрация беседы", ""]
    for lvl in sorted(by_level.keys(), reverse=True):
        emoji = "♛" if lvl >= 7 else "👑" if lvl >= 5 else "🛡"
        lines.append(f"{emoji} {ROLE_NAMES.get(lvl, str(lvl))}:")
        for uid in by_level[lvl]:
            lines.append(f"  • {_link(ctx.vk, uid)}")
        lines.append("")
    send_message(ctx.vk, ctx.peer_id, "\n".join(lines))


@router.command("админ стат")
def cmd_admin_stat(ctx: CommandContext):
    """Админ-стат: только админ смотрит свой или другого админа."""
    admin = AdminService()
    if not admin.is_admin(ctx.user_id, ctx.peer_id):
        return send_message(ctx.vk, ctx.peer_id, "⛔ Команда доступна только администрации.")

    target = parse_target_id(ctx.args) if ctx.args else ctx.user_id
    if not target:
        target = ctx.user_id

    # Чужую админ-стату — только если цель тоже админ (или создатель)
    if target != ctx.user_id:
        if not admin.is_admin(target, ctx.peer_id) and target != settings.creator_id:
            return send_message(
                ctx.vk,
                ctx.peer_id,
                "Можно смотреть админ-статистику только у администраторов.",
            )

    stats = db.get_admin_week_stats(target)
    text = (
        f"📊 Админ-стат {_link(ctx.vk, target)} (неделя):\n"
        f"▪ Сообщения: {stats['messages']}\n"
        f"▪ Приглашения: {stats['invites']}\n"
        f"▪ Отчёты: {stats['reports']}\n"
        f"▪ Камни выдано: {stats['gems_awarded']}"
    )
    send_message(ctx.vk, ctx.peer_id, text)


@router.command("снять", admin_level=6)
def cmd_unadmin(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return send_message(ctx.vk, ctx.peer_id, "Использование: лл снять @user")
    if target == settings.creator_id:
        return send_message(ctx.vk, ctx.peer_id, "Нельзя снять права с создателя.")
    ok, msg = AdminService().remove_rights(target)
    send_message(ctx.vk, ctx.peer_id, f"Снято с {_link(ctx.vk, target)}: {msg}")
    log_to_control(ctx.vk, f"📉 Снятие прав\nАдмин: {_link(ctx.vk, ctx.user_id)}\nПользователь: {_link(ctx.vk, target)}\nРезультат: {msg}")


@router.command("выдать права", admin_level=6)
def cmd_give_rights(ctx: CommandContext):
    parts = ctx.args_list
    if len(parts) < 2:
        return send_message(
            ctx.vk, ctx.peer_id,
            "Использование: лл выдать права @user <беседа|анархия|казино> <должность>",
        )
    target = parse_target_id(parts[0])
    if not target:
        return send_message(ctx.vk, ctx.peer_id, "Укажи пользователя.")
    rest = " ".join(parts[1:]).lower()
    level = None
    for word, lvl in ROLE_WORDS.items():
        if word in rest:
            level = lvl
            break
    if not level:
        return send_message(ctx.vk, ctx.peer_id, "Укажи должность (активист, рекрутер, админ, куратор...).")
    _ensure(ctx.vk, target)
    if db.is_in_admin_blacklist(target):
        return send_message(ctx.vk, ctx.peer_id, f"{_link(ctx.vk, target)} в ЧС администрации.")
    actor_level = _level(ctx.user_id, ctx.peer_id)
    if level in (6, 7):
        if actor_level < 7 and ctx.user_id != settings.creator_id:
            return send_message(ctx.vk, ctx.peer_id, "Глобальные роли выдает только Лелуш.")
        db.set_global_role(target, level)
        send_message(ctx.vk, ctx.peer_id, f"Назначена глобальная роль «{ROLE_NAMES[level]}» для {_link(ctx.vk, target)}.")
        log_to_control(ctx.vk, f"👑 Выдача глобальной роли\nАдмин: {_link(ctx.vk, ctx.user_id)}\nПользователь: {_link(ctx.vk, target)}\nРоль: {ROLE_NAMES[level]}")
        return
    if level >= actor_level and ctx.user_id != settings.creator_id:
        return send_message(ctx.vk, ctx.peer_id, "Нельзя выдавать роль равную или выше собственной.")
    target_peer = None
    if "анархия" in rest:
        target_peer = settings.anarchy_chat
    elif "казино" in rest:
        target_peer = settings.casino_chat
    else:
        nums = re.findall(r"(?<!\w)\d+(?!\w)", rest)
        if nums:
            n = int(nums[0])
            if n > 2000000000:
                target_peer = n
            elif 1 <= n <= len(settings.main_chats):
                target_peer = settings.main_chats[n - 1]
            else:
                # try match peer ending
                for pid in settings.main_chats:
                    if str(pid).endswith(str(n)):
                        target_peer = pid
                        break
    if not target_peer:
        target_peer = ctx.peer_id if ctx.peer_id > 2000000000 else None
    if not target_peer:
        return send_message(ctx.vk, ctx.peer_id, "Укажи беседу (номер или «Анархия»/«Казино»).")
    db.set_admin_level(target_peer, target, 0)
    db.set_admin_level(target_peer, target, level)
    send_message(
        ctx.vk, ctx.peer_id,
        f"Назначена роль «{ROLE_NAMES[level]}» для {_link(ctx.vk, target)} в беседе «{_chat_title(ctx.vk, target_peer)}».",
    )
    log_to_control(
        ctx.vk,
        f"📈 Выдача локальной роли\nАдмин: {_link(ctx.vk, ctx.user_id)}\nПользователь: {_link(ctx.vk, target)}\nРоль: {ROLE_NAMES[level]}\nБеседа: {_chat_title(ctx.vk, target_peer)}",
    )


@router.command("чс адм", admin_level=6)
def cmd_admin_bl_add(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return
    _ensure(ctx.vk, target)
    db.add_to_admin_blacklist(target, ctx.user_id)
    send_message(ctx.vk, ctx.peer_id, f"{_link(ctx.vk, ctx.user_id)} занёс {_link(ctx.vk, target)} в ЧС Администрации.")
    log_to_control(ctx.vk, f"🚫 Добавление в ЧС Адм\nАдмин: {_link(ctx.vk, ctx.user_id)}\nПользователь: {_link(ctx.vk, target)}")


@router.command("убрать чс адм", admin_level=6)
def cmd_admin_bl_remove(ctx: CommandContext):
    target = parse_target_id(ctx.args)
    if not target:
        return
    if not db.is_in_admin_blacklist(target):
        return send_message(ctx.vk, ctx.peer_id, f"{_link(ctx.vk, target)} не в ЧС.")
    db.remove_from_admin_blacklist(target)
    send_message(ctx.vk, ctx.peer_id, f"{_link(ctx.vk, ctx.user_id)} убрал {_link(ctx.vk, target)} из ЧС Администрации.")
    log_to_control(ctx.vk, f"✅ Удаление из ЧС Адм\nАдмин: {_link(ctx.vk, ctx.user_id)}\nПользователь: {_link(ctx.vk, target)}")


# ─── Твинки ──────────────────────────────────────────────

@router.command("твинк", admin_level=1)
def cmd_twink(ctx: CommandContext):
    parts = ctx.args_list
    if not parts:
        return send_message(ctx.vk, ctx.peer_id, "Использование: лл твинк @user  |  лл твинк убрать @user")
    if parts[0].lower() == "убрать":
        target = parse_target_id(" ".join(parts[1:]))
        if not target or not db.is_twink(target):
            return send_message(ctx.vk, ctx.peer_id, "Твинк не найден.")
        owner = db.get_owner(target)
        if ctx.user_id not in (owner, settings.creator_id) and _level(ctx.user_id, ctx.peer_id) < 5:
            return send_message(ctx.vk, ctx.peer_id, "Недостаточно прав.")
        db.remove_twink(target)
        return send_message(ctx.vk, ctx.peer_id, f"Твинк {_link(ctx.vk, target)} убран.")
    target = parse_target_id(ctx.args)
    if not target:
        return
    if target == ctx.user_id:
        return send_message(ctx.vk, ctx.peer_id, "Нельзя добавить себя.")
    db.add_twink(ctx.user_id, target)
    send_message(ctx.vk, ctx.peer_id, f"Твинк {_link(ctx.vk, target)} добавлен.")


@router.command("твинки", admin_level=1)
def cmd_twinks(ctx: CommandContext):
    target = parse_target_id(ctx.args) if ctx.args else ctx.user_id
    if not target:
        target = ctx.user_id
    rows = db.get_twinks(target)
    if not rows:
        return send_message(ctx.vk, ctx.peer_id, f"У {_link(ctx.vk, target)} нет твинков.")
    lines = [f"👥 Твинки {_link(ctx.vk, target)}:", ""]
    for tid in rows:
        lines.append(f"• {_link(ctx.vk, int(tid))}")
    send_message(ctx.vk, ctx.peer_id, "\n".join(lines))


@router.command("аватар", admin_level=2)
def cmd_avatar(ctx: CommandContext):
    m = re.search(r"\[id(\d+)\|[^\]]+\]", ctx.args or "")
    if not m:
        m = re.search(r"(?:@)?id(\d+)|\b(\d{3,15})\b", ctx.args or "")
    if not m:
        return send_message(ctx.vk, ctx.peer_id, "Укажи пользователя: `лл аватар @user <photo...>`")
    target = int(m.group(1) or m.group(2))
    rest = (ctx.args or "")[m.end():].strip()
    photo = None
    pm = re.search(r"photo(-?\d+)_(-?\d+)", rest, re.I)
    if pm:
        photo = f"photo{pm.group(1)}_{pm.group(2)}"
    if not photo:
        return send_message(ctx.vk, ctx.peer_id, "Не удалось распознать фото. Укажи ID или ссылку.")
    _ensure(ctx.vk, target)
    db.set_profile_image(target, photo)
    send_message(ctx.vk, ctx.peer_id, f"{_link(ctx.vk, ctx.user_id)} установил аватар для {_link(ctx.vk, target)}.")


@router.command("изменить приветствие", admin_level=5)
def cmd_set_welcome(ctx: CommandContext):
    raw = ctx.args or ""
    photo = ""
    pm = re.search(r"photo(-?\d+)_(-?\d+)", raw, re.I)
    if pm:
        photo = f"photo{pm.group(1)}_{pm.group(2)}"
        raw = (raw[: pm.start()] + raw[pm.end():]).strip()
    if not raw:
        return send_message(ctx.vk, ctx.peer_id, "Укажи текст приветствия (и опционально photo).")
    db.set_welcome_message(ctx.peer_id, raw, photo)
    send_message(ctx.vk, ctx.peer_id, "Приветствие изменено.")


@router.command("приветствие", admin_level=5)
def cmd_show_welcome(ctx: CommandContext):
    text, photo = db.get_welcome_data(ctx.peer_id)
    msg = f"Текущее приветствие:\n{text or '—'}"
    if photo:
        msg += f"\nФото: {photo}"
    send_message(ctx.vk, ctx.peer_id, msg)


@router.command("обновить рп", admin_level=6)
def cmd_refresh_rp(ctx: CommandContext):
    from bot.services.rp_service import sync_all_rp_photos
    try:
        n = sync_all_rp_photos(ctx.vk)
        send_message(ctx.vk, ctx.peer_id, f"RP-фото обновлены. Записей: {n}")
    except Exception as e:
        # fallback: just report count
        cnt = db.get_rp_photo_count()
        send_message(ctx.vk, ctx.peer_id, f"Кэш RP-фото: {cnt} записей. ({e})")


# ─── Чистка / беседы ─────────────────────────────────────

@router.command("чистка", admin_level=5)
def cmd_cleanup(ctx: CommandContext):
    try:
        amount = int((ctx.args or "50").strip().split()[0])
        if not (30 <= amount <= 80):
            raise ValueError
    except ValueError:
        return send_message(ctx.vk, ctx.peer_id, "Укажи число сообщений от 30 до 80. Пример: `лл чистка 50`")
    if ctx.peer_id not in settings.main_chats:
        return send_message(ctx.vk, ctx.peer_id, "Чистка доступна только в основных беседах.")
    # Manual cleanup: kick users with low weekly messages
    from datetime import date, timedelta
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    kicked = 0
    try:
        members = ctx.vk.messages.getConversationMembers(peer_id=ctx.peer_id).get("items", [])
    except Exception as e:
        return send_message(ctx.vk, ctx.peer_id, f"Не удалось получить участников: {e}")
    for item in members:
        uid = int(item.get("member_id", 0))
        if uid <= 0:
            continue
        if uid == settings.creator_id or _level(uid, ctx.peer_id) >= 1:
            continue
        msgs = db.get_chat_user_week_messages(ctx.peer_id, uid, week_start, today.isoformat())
        if msgs < amount:
            try:
                ctx.vk.messages.removeChatUser(chat_id=ctx.peer_id - 2000000000, user_id=uid)
                db.add_kick_event(uid, ctx.peer_id, ctx.user_id)
                kicked += 1
            except Exception:
                pass
    res = f"Чистка завершена. Исключено: {kicked} (порог {amount} сообщений за неделю)."
    send_message(ctx.vk, ctx.peer_id, res)
    log_to_control(ctx.vk, f"🧹 Чистка\nБеседа: {_chat_title(ctx.vk, ctx.peer_id)}\nАдмин: {_link(ctx.vk, ctx.user_id)}\nРезультат: {res}")


@router.command("беседа", admin_level=1)
def cmd_chat_info(ctx: CommandContext):
    title = _chat_title(ctx.vk, ctx.peer_id)
    try:
        members = ctx.vk.messages.getConversationMembers(peer_id=ctx.peer_id)
        count = len(members.get("items", []))
    except Exception:
        count = "?"
    send_message(
        ctx.vk, ctx.peer_id,
        f"📊 Беседа: {title}\nID: {ctx.peer_id}\nУчастников: {count}",
    )


@router.command("беседы", admin_level=1)
def cmd_chats_list(ctx: CommandContext):
    lines = ["📋 Беседы бота:", ""]
    for i, pid in enumerate(settings.main_chats, 1):
        lines.append(f"{i}. {_chat_title(ctx.vk, pid)} (`{pid}`)")
    lines.append(f"Анархия: {_chat_title(ctx.vk, settings.anarchy_chat)}")
    lines.append(f"Казино: {_chat_title(ctx.vk, settings.casino_chat)}")
    send_message(ctx.vk, ctx.peer_id, "\n".join(lines))


@router.command("настроить набор", admin_level=6)
def cmd_recruit_settings(ctx: CommandContext):
    if ctx.peer_id > 2000000000:
        return send_message(ctx.vk, ctx.peer_id, "Настройка набора — только в ЛС бота.")
    from bot.keyboards.main import _btn
    # Simple text for now
    lines = ["⚙️ Настройка открытых ролей по беседам:", ""]
    for i, pid in enumerate(settings.main_chats, 1):
        conf = db.get_recruit_settings(pid)
        lines.append(f"NightFall {i} (`{pid}`):")
        for role, name in ((2, "Активист"), (3, "Рекрутер"), (4, "Админ")):
            open_ = conf.get(role, True)
            lines.append(f"  {name}: {'✅ открыто' if open_ else '❌ закрыто'}")
        lines.append("")
    lines.append("Переключение: лл набор <номер_беседы> <роль>  (пока через БД / позже кнопки)")
    send_message(ctx.vk, ctx.peer_id, "\n".join(lines))
