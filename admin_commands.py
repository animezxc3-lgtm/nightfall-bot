import re
from config import CREATOR_ID, GROUP_ID, APPLICATIONS_PEER_ID
from response_context import get_user_id, get_exclude_actor
from database import (
    get_global_role, set_global_role, get_admin_level_for_chat, set_admin_level,
    get_user, create_user, get_first_inviter, is_banned, is_in_admin_blacklist,
    get_warning_stats, get_kick_stats, get_messages_stats, get_last_message_at,
    add_warning, add_kick_event, remove_warning, clear_warnings,
    ban_user, unban_user, get_all_chats, get_banned_users,
    set_welcome_message, get_welcome_data, get_feature, get_broadcast_chats,
    toggle_feature, get_chat_activity, db_cursor, get_all_global_roles, 
    find_chats_by_number, add_admin_stat, add_to_admin_blacklist, 
    remove_from_admin_blacklist, set_profile_image
)
from pin_manager import refresh_after_admin_change

ROLE_NAMES = {
    1: 'Стажёр', 2: 'Активист', 3: 'Рекрутер',
    4: 'Заместитель Куратора', 5: 'Куратор',
    6: 'Вершитель правосудия', 7: 'Лелуш ви Британия',
}

# Слова, которые бот будет искать в команде
ROLE_WORDS = {
    'стажёр': 1, 'стажер': 1, 'активист': 2, 'рекрутер': 3,
    'зк': 4, 'заместитель куратора': 4, 'куратор': 5,
    'вершитель': 6, 'вершитель правосудия': 6, 'лелуш': 7, 'создатель': 7,
}

COMMAND_MIN_LEVEL = {
    'пред': 2, 'анпред': 3, 'фулл анпред': 3, 'кик': 2, 'фулл кик': 2, 'бан': 3, 'разбан': 3, 'банстат': 3,
    'админы': 1, 'проверить': 2, 'снять': 5, 'изменить приветствие': 4, 'рассылка': 5, 'приветствие': 4,
    'переключить мут': 5, 'переключить чистку': 5, 'переключить казино': 5, 'переключить дуэль': 5,
    'переключить рассылку': 5, 'чс адм': 5, 'убрать чс адм': 5,
    'беседа': 1, 'беседы': 1, 'выдать права': 5, 'аватар': 4, 'норма': 4,
}


def get_admin_level(user_id, peer_id=None):
    if user_id == CREATOR_ID: return 7
    g = get_global_role(user_id)
    if g > 0: return g
    if peer_id and peer_id > 2000000000:
        l = get_admin_level_for_chat(peer_id, user_id)
        if l > 0: return l
    return 0


def _refresh_pin(vk, peer_id):
    try: refresh_after_admin_change(vk, peer_id=peer_id, global_change=False)
    except: pass

def _refresh_all_pins(vk):
    try: refresh_after_admin_change(vk, global_change=True)
    except: pass

def extract_user_id(text):
    if not text: return None
    m = re.search(r'\[id(\d+)\|', text)
    if m: return int(m.group(1))
    m = re.search(r'vk\.(?:com|ru)/id(\d+)', text)
    if m: return int(m.group(1))
    m = re.search(r'@id(\d+)', text)
    if m: return int(m.group(1))
    m = re.search(r'\b(\d{3,15})\b', text)
    if m: return int(m.group(1))
    return None

def _user_link(vk, user_id, fallback='Пользователь'):
    try:
        info = vk.users.get(user_ids=user_id)[0]
        from relationships import get_display_name
        label = get_display_name(user_id) or info.get('first_name', fallback)
    except: label = fallback
    return f'[id{user_id}|{label}]'

def _user_fullname(vk, user_id):
    try:
        info = vk.users.get(user_ids=user_id)[0]
        return f"{info.get('first_name','')} {info.get('last_name','')}".strip() or 'Пользователь'
    except: return 'Пользователь'

def _ensure_profile(vk, user_id):
    if get_user(user_id): return
    try: create_user(user_id, _user_fullname(vk, user_id))
    except: pass

def can_act(actor, target, peer):
    if actor == target: return False
    return get_admin_level(target, peer) < get_admin_level(actor, peer)

def _send(vk, p, msg, actor_inline=True):
    actor = get_user_id()
    if actor and actor_inline and not get_exclude_actor():
        try:
            info = vk.users.get(user_ids=actor)[0]
            from relationships import get_display_name
            label = get_display_name(actor) or info.get("first_name", "Пользователь")
        except: label = "Пользователь"
        msg = f"[id{actor}|{label}] {msg}"
    vk.messages.send(peer_id=p, random_id=0, message=msg, disable_mentions=True)

def _require(key, uid, peer, vk):
    if get_admin_level(uid, peer) < COMMAND_MIN_LEVEL[key]:
        _send(vk, peer, 'Недостаточно прав', actor_inline=False)
        return False
    return True


# ... (ТУТ ОСТАЛЬНЫЕ ФУНКЦИИ: _fmt_date, _has_number_in_title, _get_numbered_chats, _get_user_chats, _build_check) ...
# ОНИ НЕ МЕНЯЮТСЯ, ОСТАВЬ КАК БЫЛО В ПРЕДЫДУЩЕМ ФАЙЛЕ


def handle_admin_command(command, user_id, peer_id, vk, text):
    keys = sorted(COMMAND_MIN_LEVEL, key=len, reverse=True)
    key = next((k for k in keys if command == k or command.startswith(k + ' ')), None)
    if not key: return False
    if not _require(key, user_id, peer_id, vk): return True
    rest = command[len(key):].strip()

    # ==========================================
    # ВЫДАТЬ ПРАВА (ПОЛНОСТЬЮ ПЕРЕПИСАНО)
    # ==========================================
    if key == 'выдать права':
        # Ищем юзера
        target = extract_user_id(rest)
        if not target:
            _send(vk, peer_id, '❌ Не вижу пользователя. Формат: `лл выдать права @user [номер беседы] [должность]`', actor_inline=False)
            return True

        # Ищем должность
        level = 0
        for word, lvl in ROLE_WORDS.items():
            if word in rest:
                level = lvl
                break
                
        if level == 0:
            _send(vk, peer_id, '❌ Должность не найдена. Доступно: стажёр, активист, рекрутер, зк, куратор, вершитель, лелуш.', actor_inline=False)
            return True

        # Ищем номер беседы
        m = re.search(r'\b(\d+)\b', rest.replace(str(target), ''))
        chat_number = int(m.group(1)) if m else None

        _ensure_profile(vk, target)
        actor_level = get_admin_level(user_id, peer_id)

        # Выдача ГЛОБАЛЬНЫХ (6, 7)
        if level in (6, 7):
            if actor_level < 7:
                _send(vk, peer_id, '❌ Только Лелуш может выдавать глобальные роли.', actor_inline=False)
                return True
            set_global_role(target, level)
            _send(vk, peer_id, f'👑 Выдал глобальную роль {ROLE_NAMES[level]} для {_user_link(vk, target)}.')
            _refresh_all_pins(vk)
            return True

        # Выдача ЛОКАЛЬНЫХ (1-5)
        if chat_number is None:
            _send(vk, peer_id, '❌ Укажи номер беседы. Формат: `лл выдать права @user 1 куратор`', actor_inline=False)
            return True

        target_peer = chat_number if chat_number > 2000000000 else 2000000000 + chat_number
        
        if not can_act(user_id, target, target_peer):
            _send(vk, peer_id, '❌ Недостаточно прав (ты не можешь выдать роль выше своей).', actor_inline=False)
            return True

        set_admin_level(target_peer, target, level, ROLE_NAMES[level])
        _send(vk, peer_id, f'✅ Выдал {ROLE_NAMES[level]} для {_user_link(vk, target)} в беседе «{chat_number}».')
        _refresh_pin(vk, target_peer)
        return True

    # ==========================================
    # СНЯТЬ ПРАВА (ПОЛНОСТЬЮ ПЕРЕПИСАНО)
    # ==========================================
    if key == 'снять':
        target = extract_user_id(rest)
        if not target:
            _send(vk, peer_id, '❌ Не вижу пользователя. Формат: `лл снять @user`', actor_inline=False)
            return True

        actor_level = get_admin_level(user_id, peer_id)

        # Снимаем глобальную, если есть
        if get_global_role(target):
            if actor_level < 7:
                _send(vk, peer_id, '❌ Только Лелуш может снимать глобальные роли.', actor_inline=False)
                return True
            set_global_role(target, 0)
            _send(vk, peer_id, f'👑 Снял глобальную роль с {_user_link(vk, target)}.')
            _refresh_all_pins(vk)
            return True

        # Снимаем локальные
        with db_cursor() as (_, c):
            c.execute("SELECT peer_id FROM admin_chat_rights WHERE user_id=? AND level>0", (target,))
            rows = c.fetchall()

        if not rows:
            _send(vk, peer_id, f'❌ У {_user_link(vk, target)} нет прав.', actor_inline=False)
            return True

        # Проверка, что снимающий выше по званию
        for rp in rows:
            if not can_act(user_id, target, rp[0]):
                _send(vk, peer_id, '❌ Недостаточно прав для снятия.', actor_inline=False)
                return True

        removed = []
        for (rp,) in rows:
            set_admin_level(rp, target, 0, 'Участник')
            removed.append(rp)

        _send(vk, peer_id, f'✅ Снял права с {_user_link(vk, target)} в {len(removed)} беседах.')
        for rp in removed: _refresh_pin(vk, rp)
        return True

    # ... (ОСТАЛЬНЫЕ КОМАНДЫ: пред, кик, бан, норма, аватар, приветствие и т.д. оставь как было) ...
    
    return True