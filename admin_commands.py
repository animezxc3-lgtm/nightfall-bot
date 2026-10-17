import re
from config import CREATOR_ID, GROUP_ID, APPLICATIONS_PEER_ID
from response_context import get_user_id, get_exclude_actor
# Явные импорты вместо "from database import *"
from database import (
    get_global_role, set_global_role, get_admin_level_for_chat, set_admin_level,
    get_user, create_user, get_first_inviter, is_banned, is_in_admin_blacklist,
    get_warning_stats, get_kick_stats, get_messages_stats, get_last_message_at,
    add_warning, add_kick_event, remove_warning, clear_warnings,
    ban_user, unban_user, get_all_chats, get_banned_users,
    set_welcome_message, get_welcome_data, get_feature, get_broadcast_chats,
    toggle_feature, get_chat_activity, get_owner, get_application,
    db_cursor, get_all_global_roles,
    # Новые добавления:
    find_chats_by_number, add_admin_stat, add_to_admin_blacklist, 
    remove_from_admin_blacklist, set_profile_image
)
from pin_manager import refresh_after_admin_change


# Иерархия по уровням (1-7)
ROLE_NAMES = {
    1: 'Стажёр',
    2: 'Активист',
    3: 'Рекрутер',
    4: 'Заместитель Куратора',
    5: 'Куратор',
    6: 'Вершитель правосудия',
    7: 'Лелуш ви Британия',
}

# Словесные должности для лл выдать права
ROLE_WORDS = {
    'стажёр': 1,
    'стажер': 1,
    'активист': 2,
    'рекрутер': 3,
    'зк': 4,
    'заместитель куратора': 4,
    'куратор': 5,
    'вершитель': 6,
    'вершитель правосудия': 6,
    'лелуш': 7,
    'создатель': 7,
}

COMMAND_MIN_LEVEL = {
    'пред': 2, 'анпред': 3, 'фулл анпред': 3, 'кик': 2, 'фулл кик': 2, 'бан': 3, 'разбан': 3, 'банстат': 3,
    'админы': 1, 'проверить': 2, 'снять': 5, 'изменить приветствие': 4, 'рассылка': 5, 'приветствие': 4,
    'переключить мут': 5, 'переключить чистку': 5, 'переключить казино': 5, 'переключить дуэль': 5,
    'переключить рассылку': 5,
    'чс адм': 5, 'убрать чс адм': 5,
    'беседа': 1, 'беседы': 1,
    'выдать права': 5, 'аватар': 4,
    'норма': 4,
}


def _has_number_in_title(title):
    if not title:
        return False
    return bool(re.search(r'\d+\s*$', str(title).strip()))


def _get_numbered_chats(vk):
    chats = get_all_chats()
    if not chats:
        return []

    ids = [p for p, _ in chats]
    names = {}
    try:
        data = vk.messages.getConversationsById(peer_ids=','.join(map(str, ids))).get('items', [])
        for x in data:
            pid = int(x.get('peer', {}).get('id'))
            title = (x.get('chat_settings', {}).get('title') or '').strip()
            names[pid] = title
    except Exception as e:
        print(f'⚠️ _get_numbered_chats: {e}')
        return []

    result = []
    for pid, _ in chats:
        title = names.get(pid, '')
        if _has_number_in_title(title):
            result.append((pid, title))

    def sort_key(item):
        _, title = item
        m = re.search(r'^(.*?)(\d+)\s*$', title)
        if m:
            return (m.group(1).strip().lower(), int(m.group(2)))
        return (title.lower(), 0)

    result.sort(key=sort_key)
    return result


def get_admin_level(user_id, peer_id=None):
    if user_id == CREATOR_ID:
        return 7

    global_level = get_global_role(user_id)
    if global_level:
        return global_level

    if peer_id and peer_id > 2000000000:
        local = get_admin_level_for_chat(peer_id, user_id)
        if local:
            return local

    owner = get_owner(user_id)
    if owner:
        if owner == CREATOR_ID:
            return 7
        owner_global = get_global_role(owner)
        if owner_global:
            return owner_global
        if peer_id and peer_id > 2000000000:
            owner_local = get_admin_level_for_chat(peer_id, owner)
            if owner_local:
                return owner_local

    return 0


def _refresh_pin(vk, peer_id):
    try:
        result = refresh_after_admin_change(vk, peer_id=peer_id, global_change=False)
    except Exception as e:
        print(f'⚠️ Ошибка обновления закрепа {peer_id}: {e}')


def _refresh_all_pins(vk):
    try:
        results = refresh_after_admin_change(vk, global_change=True)
    except Exception as e:
        print(f'⚠️ Ошибка массового обновления закрепов: {e}')


def extract_user_id(text):
    if not text:
        return None
    text = str(text).strip()

    m = re.search(r'\[id(\d+)\|', text)
    if m:
        return int(m.group(1))

    m = re.search(r'vk\.(?:com|ru)/id(\d+)', text)
    if m:
        return int(m.group(1))

    m = re.search(r'@id(\d+)', text)
    if m:
        return int(m.group(1))

    m = re.search(r'\b(\d{3,15})\b', text)
    if m:
        return int(m.group(1))

    return None


def _user_link(vk, user_id, fallback='Пользователь'):
    try:
        info = vk.users.get(user_ids=user_id)[0]
        from relationships import get_display_name
        label = get_display_name(user_id) or info.get('first_name', fallback)
    except Exception:
        label = fallback
    return f'[id{user_id}|{label}]'


def _user_fullname(vk, user_id):
    try:
        info = vk.users.get(user_ids=user_id)[0]
        return f"{info.get('first_name','')} {info.get('last_name','')}".strip() or 'Пользователь'
    except Exception:
        return 'Пользователь'


def _ensure_profile(vk, user_id):
    if get_user(user_id):
        return
    name = _user_fullname(vk, user_id)
    try:
        create_user(user_id, name)
    except Exception as e:
        print(f'⚠️ Не удалось создать профиль {user_id}: {e}')


def can_act(actor, target, peer):
    if actor == target:
        return False
    return get_admin_level(target, peer) < get_admin_level(actor, peer)


def _send(vk, p, msg, actor_inline=True):
    actor = get_user_id()
    if actor and actor_inline and not get_exclude_actor():
        try:
            info = vk.users.get(user_ids=actor)[0]
            from relationships import get_display_name
            label = get_display_name(actor) or info.get("first_name", "Пользователь")
        except Exception:
            label = "Пользователь"
        msg = f"[id{actor}|{label}] {msg}"
    vk.messages.send(peer_id=p, random_id=0, message=msg, disable_mentions=True)


def _require(key, uid, peer, vk):
    if get_admin_level(uid, peer) < COMMAND_MIN_LEVEL[key]:
        _send(vk, peer, 'Недостаточно прав', actor_inline=False)
        return False
    return True


def _fmt_date(s):
    if not s:
        return '—'
    s = str(s)[:10]
    try:
        y, m, d = s.split('-')
        return f'{d}.{m}.{y}'
    except Exception:
        return s


def _get_user_chats(vk, target, current_peer=None):
    chats = _get_numbered_chats(vk)
    titles = []
    seen = set()

    if current_peer and current_peer > 2000000000:
        try:
            data = vk.messages.getConversationsById(peer_ids=current_peer).get('items', [])
            if data:
                title = data[0].get('chat_settings', {}).get('title') or ''
                if _has_number_in_title(title):
                    titles.append(title)
                    seen.add(title)
        except Exception:
            pass

    for peer, title in chats:
        if peer == current_peer:
            continue
        if peer == APPLICATIONS_PEER_ID:
            continue
        if title in seen:
            continue
        try:
            members = vk.messages.getConversationMembers(peer_id=peer).get('items', [])
            if any(m.get('member_id') == target for m in members):
                titles.append(title)
                seen.add(title)
        except Exception:
            continue

    return titles


def _build_check(vk, target, peer_id):
    u = get_user(target)
    if not u:
        return None

    name = u[1] or 'Пользователь'
    link = f'[id{target}|{name}]'

    inviter_id = get_first_inviter(target)
    if inviter_id:
        inviter_name = _user_fullname(vk, inviter_id)
        inviter_line = f'[id{inviter_id}|{inviter_name}]'
    else:
        inviter_line = '—'

    join_date = _fmt_date(u[14])

    level = get_admin_level(target, peer_id)
    rights = ROLE_NAMES.get(level, 'Участник')

    banned_line = 'Да' if is_banned(target) else 'Нет'
    bl_line = 'Да' if is_in_admin_blacklist(target) else 'Нет'

    adm_w = get_warning_stats(target, True)
    w = get_warning_stats(target, False)
    kicks = get_kick_stats(target)

    chat_titles = _get_user_chats(vk, target, peer_id)

    msgs = get_messages_stats(target)
    last = get_last_message_at(target)
    last_fmt = '—'
    if last:
        try:
            from datetime import datetime as _dt
            dt = _dt.strptime(last, "%Y-%m-%d %H:%M:%S")
            last_fmt = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            last_fmt = last

    lines = [
        f'👤 {link}',
        f'Пригласивший в первый раз: {inviter_line}',
        f'Дата создания профиля: {join_date}',
        f'⚙️ Права: {rights}',
        '',
        '─────────✦─────────',
        f'Находится ли в бане: {banned_line}',
        f'Находится ли в ЧС Администрации: {bl_line}',
        '',
        'Адм. предупреждений: ',
        f'▪За неделю - {adm_w["week"]}',
        f'▪За месяц - {adm_w["month"]}',
        f'▪За все время - {adm_w["total"]}',
        'Предупреждений: ',
        f'▪За неделю - {w["week"]}',
        f'▪За месяц - {w["month"]}',
        f'▪За все время - {w["total"]}',
        'Был исключен: ',
        f'▪За неделю - {kicks["week"]}',
        f'▪За месяц - {kicks["month"]}',
        f'▪За все время - {kicks["total"]}',
        '',
        '─────────✦─────────',
        'Беседы в которых состоит пользователь:',
    ]

    if chat_titles:
        for t in chat_titles:
            lines.append(f'-{t}')
    else:
        lines.append('-—')

    lines.extend([
        '─────────✦─────────',
        'Активность по сообщениям:',
        f'▪За все время: {msgs["total"]}',
        f'▪За месяц: {msgs["month"]}',
        f'▪За неделю: {msgs["week"]}',
        f'▪За день: {msgs["today"]}',
        f'▪Последнее сообщение: {last_fmt}',
    ])

    return '\n'.join(lines)


def _resolve_target_peer(vk, rest_part):
    num = rest_part.strip()
    if not num:
        return None, 'Укажи номер беседы.'
    chats = find_chats_by_number(vk, num)
    if not chats:
        return None, f'Беседа с номером «{num}» не найдена.'
    if len(chats) > 1:
        return None, f'Найдено несколько бесед с номером «{num}».'
    return chats[0], None


def handle_admin_command(command, user_id, peer_id, vk, text):
    keys = sorted(COMMAND_MIN_LEVEL, key=len, reverse=True)
    key = next((k for k in keys if command == k or command.startswith(k + ' ')), None)
    if not key:
        return False
    if not _require(key, user_id, peer_id, vk):
        return True
    rest = command[len(key):].strip()

    # ========================================================
    # НОРМА
    # ========================================================
    if key == 'норма':
        parts = rest.split()
        if not parts:
            return True

        sign = parts[0]
        if sign not in ('+', '-'):
            return True

        if len(parts) >= 2:
            target = extract_user_id(parts[1])
        else:
            target = user_id

        if not target:
            return True

        if not get_user(target):
            _ensure_profile(vk, target)

        if sign == '+':
            add_admin_stat(target, 'reports', 1)
            _send(vk, peer_id, f'норма сдана для {_user_link(vk, target)}.')
        else:
            _send(vk, peer_id, f'норма НЕ сдана для {_user_link(vk, target)}.')
        return True

    # ========================================================
    # МОДЕРАЦИЯ
    # ========================================================
    if key in {'пред', 'анпред', 'фулл анпред', 'кик', 'фулл кик', 'бан', 'разбан', 'снять', 'проверить'}:
        target = extract_user_id(rest)
        if not target:
            return True

        if key == 'проверить':
            text_out = _build_check(vk, target, peer_id)
            if not text_out:
                _send(vk, peer_id, 'Пользователь не найден.', actor_inline=False)
                return True
            _send(vk, peer_id, text_out, actor_inline=False)
            return True

        if not can_act(user_id, target, peer_id):
            _send(vk, peer_id, 'Недостаточно прав', actor_inline=False)
            return True

        if key == 'пред':
            _ensure_profile(vk, target)
            n = add_warning(target, peer_id, True)

            if n >= 3:
                add_kick_event(target, peer_id, user_id)
                try:
                    vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target)
                except Exception:
                    pass
                _send(vk, peer_id, f'выдал предупреждение {_user_link(vk, target)}. Теперь у него 3/3. {_user_link(vk, target)} исключён из беседы.')
            else:
                _send(vk, peer_id, f'выдал предупреждение {_user_link(vk, target)}. Теперь у него {n}/3.')
            return True

        if key == 'анпред':
            _ensure_profile(vk, target)
            left = remove_warning(target, peer_id, True)
            _send(vk, peer_id, f'снял пред у {_user_link(vk, target)}. У {_user_link(vk, target)} стало {left}/3 предупреждений')
            return True

        if key == 'фулл анпред':
            _ensure_profile(vk, target)
            clear_warnings(target, peer_id, True)
            _send(vk, peer_id, f'снял все предупреждения у {_user_link(vk, target)}.')
            return True

        if key == 'бан':
            _ensure_profile(vk, target)
            ban_user(target)
            add_kick_event(target, peer_id, user_id)
            try:
                vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target)
            except Exception:
                pass
            _send(vk, peer_id, 'Пользователь забанен.')
            return True

        if key == 'разбан':
            _ensure_profile(vk, target)
            unban_user(target)
            _send(vk, peer_id, f'разбанил {_user_link(vk, target)}.')
            return True

        if key == 'кик':
            _ensure_profile(vk, target)
            add_kick_event(target, peer_id, user_id)
            try:
                vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target)
                _send(vk, peer_id, f'исключил {_user_link(vk, target)} из беседы.')
            except Exception as e:
                print(f'⚠️ Не удалось исключить: {e}')
            return True

        if key == 'фулл кик':
            _ensure_profile(vk, target)
            add_kick_event(target, peer_id, user_id)
            kicked = 0
            for cp, _ in get_all_chats():
                if cp == APPLICATIONS_PEER_ID:
                    continue
                if cp == peer_id:
                    continue
                try:
                    members = vk.messages.getConversationMembers(peer_id=cp).get('items', [])
                    if any(m.get('member_id') == target for m in members):
                        vk.messages.removeChatUser(chat_id=cp - 2000000000, user_id=target)
                        kicked += 1
                except Exception as e:
                    print(f'⚠️ Не удалось кикнуть из {cp}: {e}')
            try:
                vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target)
                kicked += 1
            except Exception:
                pass
            _send(vk, peer_id, f'исключил {_user_link(vk, target)} из {kicked} бесед.')
            return True

        if key == 'снять':
            if get_global_role(target):
                if get_admin_level(user_id, peer_id) < 7:
                    _send(vk, peer_id, 'Недостаточно прав', actor_inline=False)
                    return True
                set_global_role(target, 0)
                _send(vk, peer_id, f'снял глобальную роль с {_user_link(vk, target)}.')
                _refresh_all_pins(vk)
                return True

            with db_cursor() as (_, c):
                c.execute("SELECT peer_id FROM admin_chat_rights WHERE user_id=? AND level>0", (target,))
                rows = c.fetchall()

            if not rows:
                _send(vk, peer_id, f'У {_user_link(vk, target)} нет прав.', actor_inline=False)
                return True

            removed = []
            for (rp,) in rows:
                set_admin_level(rp, target, 0, 'Участник')
                removed.append(rp)

            _send(vk, peer_id, f'снял права с {_user_link(vk, target)} в {len(removed)} беседах.')

            for rp in removed:
                _refresh_pin(vk, rp)
            return True

    # ========================================================
    # БАНСТАТ
    # ========================================================
    if key == 'банстат':
        rows = get_banned_users()
        _send(vk, peer_id, '🔒 В бане никого нет.' if not rows else '\n'.join(
            ['🔒 Пользователи в бане:'] + [f'{i}. {n or "Пользователь"} — https://vk.com/id{u}' for i, (u, n) in enumerate(rows, 1)]), actor_inline=False)
        return True

    # ========================================================
    # АДМИНЫ
    # ========================================================
    if key == 'админы':
        with db_cursor() as (_, c):
            c.execute('SELECT peer_id,user_id,level FROM admin_chat_rights WHERE level>0 ORDER BY level DESC,peer_id')
            rows = c.fetchall()
        if not rows:
            _send(vk, peer_id, '📋 Администраторов нет.', actor_inline=False)
            return True
        _send(vk, peer_id, '👑 Администрация по беседам:\n' + '\n'.join(
            f'Беседа {p}: {ROLE_NAMES.get(l, str(l))} — https://vk.com/id{u}' for p, u, l in rows), actor_inline=False)
        return True

    # ========================================================
    # ВЫДАТЬ ПРАВА
    # ========================================================
    if key == 'выдать права':
        # Формат: @user [номер беседы] [должность]
        parts = rest.split(maxsplit=2)
        if len(parts) < 2:
            return True

        target = extract_user_id(parts[0])
        if not target:
            return True

        # Если 3 части: @user [номер] [должность]
        # Если 2 части: @user [должность] (для глобальных 5-7)
        chat_number = None
        role_word = None

        if len(parts) == 3:
            try:
                chat_number = int(parts[1])
            except Exception:
                chat_number = None
            role_word = parts[2].strip().lower()
        else:
            role_word = parts[1].strip().lower()

        level = ROLE_WORDS.get(role_word)
        if not level:
            _send(vk, peer_id, 'Такой должности нет.', actor_inline=False)
            return True

        if is_in_admin_blacklist(target):
            _send(vk, peer_id, f'{_user_link(vk, target)} в чёрном списке администрации.', actor_inline=False)
            return True

        _ensure_profile(vk, target)

        actor_level = get_admin_level(user_id, peer_id)

                # Глобальные роли (ТОЛЬКО Вершитель 6 и Лелуш 7)
        if level in (6, 7):
            if actor_level < 7:
                _send(vk, peer_id, 'Недостаточно прав (глобальные роли выдает только Лелуш).', actor_inline=False)
                return True
            if level == 7 and target == CREATOR_ID:
                _send(vk, peer_id, 'Этот пользователь уже является создателем.', actor_inline=False)
                return True
            set_global_role(target, level)
            role = ROLE_NAMES[level]
            _send(vk, peer_id, f'назначил {_user_link(vk, target)} на глобальную роль {role}.')
            _refresh_all_pins(vk)
            return True

        # Локальные роли (1-5)
        if chat_number is None:
            _send(vk, peer_id, 'Укажи номер беседы для локальной роли.', actor_inline=False)
            return True

        target_peer = chat_number if chat_number > 2000000000 else 2000000000 + chat_number
        if chat_number <= 0:
            _send(vk, peer_id, 'Некорректный номер беседы.', actor_inline=False)
            return True

        if not can_act(user_id, target, target_peer):
            _send(vk, peer_id, 'Недостаточно прав', actor_inline=False)
            return True

        set_admin_level(target_peer, target, level, ROLE_NAMES[level])
        _send(vk, peer_id, f'выдал {_user_link(vk, target)} уровень {level} — {ROLE_NAMES[level]} в беседе «{chat_number}».')
        _refresh_pin(vk, target_peer)
        return True

    # ========================================================
    # ЧС АДМ
    # ========================================================
    if key == 'чс адм':
        target = extract_user_id(rest)
        if not target:
            return True
        _ensure_profile(vk, target)
        add_to_admin_blacklist(target, user_id)
        _send(vk, peer_id, f'занёс {_user_link(vk, target)} в ЧС Администрации.')
        return True

    if key == 'убрать чс адм':
        target = extract_user_id(rest)
        if not target:
            return True
        if not is_in_admin_blacklist(target):
            _send(vk, peer_id, f'{_user_link(vk, target)} не в ЧС.', actor_inline=False)
            return True
        remove_from_admin_blacklist(target)
        _send(vk, peer_id, f'убрал {_user_link(vk, target)} из ЧС Администрации.')
        return True

    # ========================================================
    # АВАТАР
    # ========================================================
    if key == 'аватар':
        m_user = re.search(r'\[id(\d+)\|[^\]]+\]', rest)
        m_photo = re.search(r'(\d{5,})\s*$', rest)

        if not m_user or not m_photo:
            return True

        target = int(m_user.group(1))
        photo_id = m_photo.group(1)

        _ensure_profile(vk, target)
        set_profile_image(target, f'photo-{GROUP_ID}_{photo_id}')
        _send(vk, peer_id, f'установил аватар для {_user_link(vk, target)}.')
        return True

    # ========================================================
    # ПРИВЕТСТВИЕ
    # ========================================================
    if key == 'изменить приветствие':
        photo = ''
        m = re.match(r'^(\d+)\s+(.+)$', rest)
        if m:
            photo_id, text = m.group(1), m.group(2).strip()
            photo = f'photo-{GROUP_ID}_{photo_id}'
            rest = text
        if not rest:
            return True
        set_welcome_message(peer_id, rest, photo)
        _send(vk, peer_id, 'Приветствие изменено.', actor_inline=False)
        return True

    if key == 'приветствие':
        w, p = get_welcome_data(peer_id)
        args = {'peer_id': peer_id, 'random_id': 0, 'message': w or '', 'disable_mentions': True}
        if p:
            args['attachment'] = p
        try:
            vk.messages.send(**args)
        except Exception as e:
            print(f'⚠️ Не удалось показать приветствие: {e}')
        return True

    # ========================================================
    # РАССЫЛКА
    # ========================================================
    if key == 'рассылка':
        if not get_feature(peer_id, 'рассылка'):
            _send(vk, peer_id, 'Рассылка отключена.', actor_inline=False)
            return True
        if not rest:
            _send(vk, peer_id, 'Укажи сообщение.', actor_inline=False)
            return True
        chats = get_broadcast_chats()
        if not chats:
            _send(vk, peer_id, 'Рассылка не включена нигде.', actor_inline=False)
            return True
        ok = bad = 0
        for cp in chats:
            try:
                vk.messages.send(peer_id=cp, random_id=0, message=rest)
                ok += 1
            except Exception:
                bad += 1
        _send(vk, peer_id, f'📢 Доставлено: {ok}, ошибок: {bad}.', actor_inline=False)
        return True

    # ========================================================
    # ПЕРЕКЛЮЧАТЕЛИ
    # ========================================================
    if key.startswith('переключить '):
        feature = key[len('переключить '):]
        state = toggle_feature(peer_id, feature)
        _send(vk, peer_id, f'⚙️ {feature}: {"включено" if state else "выключено"}.', actor_inline=False)
        return True

    # ========================================================
    # БЕСЕДА / БЕСЕДЫ
    # ========================================================
    if key == 'беседа':
        a = get_chat_activity(peer_id)
        _send(vk, peer_id, (
            f'💬 Текущая беседа\n'
            f'📊 День: {a["today"]}\n'
            f'📆 Неделя: {a["week"]}\n'
            f'📆 Месяц: {a["month"]}\n'
            f'📈 Всё время: {a["total"]}\n'
            f'⚙️ Казино: {"включено" if get_feature(peer_id, "казино") else "выключено"}\n'
            f'⚔️ Дуэли: {"включены" if get_feature(peer_id, "дуэль") else "выключены"}\n'
            f'📢 Рассылка: {"включена" if get_feature(peer_id, "рассылка") else "выключена"}\n'
            f'🔇 Мут: {"включён" if get_feature(peer_id, "мут") else "выключен"}\n'
            f'🧹 Чистка: {"включена" if get_feature(peer_id, "чистка") else "выключена"}'
        ), actor_inline=False)
        return True

    if key == 'беседы':
        chats = _get_numbered_chats(vk)
        if not chats:
            _send(vk, peer_id, 'Беседы не найдены.', actor_inline=False)
            return True
        lines = ['💬 Активность бесед']
        for i, (p, title) in enumerate(chats, 1):
            a = get_chat_activity(p)
            lines.extend([
                f'{i}. {title}',
                f'День: {a["today"]}',
                f'Неделя: {a["week"]}',
                f'Месяц: {a["month"]}',
                f'Всё время: {a["total"]}',
                '────────────────────'
            ])
        lines.pop()
        _send(vk, peer_id, '\n'.join(lines), actor_inline=False)
        return True

    return True