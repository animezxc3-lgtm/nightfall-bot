import re
from config import CREATOR_ID, GROUP_ID, PROFILE_WELCOME_ALBUM_ID, APPLICATIONS_PEER_ID
from response_context import get_user_id, get_exclude_actor
from database import *

ROLE_NAMES = {
    1: 'Стажёр',
    2: 'Администратор',
    3: 'Заместитель главного администратора',
    4: 'Главный администратор',
    5: 'Вершитель правосудия',
    6: 'Лелуш ви Британия',
}
COMMAND_MIN_LEVEL = {
    'пред': 2, 'анпред': 3, 'фулл анпред': 3, 'кик': 2, 'фулл кик': 2, 'бан': 3, 'разбан': 3, 'банстат': 3,
    'админы': 1, 'проверить': 2, 'снять': 5, 'изменить приветствие': 4, 'рассылка': 5, 'приветствие': 4,
    'переключить мут': 5, 'переключить чистку': 5, 'переключить казино': 5, 'переключить дуэль': 5,
    'переключить рассылку': 5,
    'скрыть беседу': 5, 'показать беседу': 5,
    'чс адм': 5, 'убрать чс адм': 5,
    'беседа': 1, 'беседы': 1,
    'выдать права': 5, 'аватар': 4,
}


def get_admin_level(user_id, peer_id=None):
    if user_id == CREATOR_ID:
        return 6
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
            return 6
        owner_global = get_global_role(owner)
        if owner_global:
            return owner_global
        if peer_id and peer_id > 2000000000:
            owner_local = get_admin_level_for_chat(peer_id, owner)
            if owner_local:
                return owner_local
    return 0


def _refresh_pin(vk, peer_id):
    """
    Обновляет закреп конкретной беседы после изменения
    локальной администрации.
    """
    try:
        from pin_manager import refresh_after_admin_change
        refresh_after_admin_change(vk, peer_id=peer_id, global_change=False)
    except Exception as e:
        print(f'⚠️ Не удалось обновить закреп беседы {peer_id}: {e}')


def _refresh_all_pins(vk):
    """
    Обновляет закрепы всех бесед после изменения
    глобальной администрации.
    """
    try:
        from pin_manager import refresh_after_admin_change
        refresh_after_admin_change(vk, global_change=True)
    except Exception as e:
        print(f'⚠️ Не удалось обновить глобальные закрепы: {e}')


def extract_user_id(text):
    m = re.search(r'\[id(\d+)\|', text or '')
    if m:
        return int(m.group(1))
    m = re.search(r'\b(\d{3,15})\b', text or '')
    return int(m.group(1)) if m else None


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
        _send(vk, peer, f'❌ Недостаточно прав. Требуется уровень {COMMAND_MIN_LEVEL[key]} — {ROLE_NAMES[COMMAND_MIN_LEVEL[key]]}.', actor_inline=False)
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
    from database import get_all_chats, is_chat_hidden

    titles = []
    seen = set()

    if current_peer and current_peer > 2000000000:
        try:
            data = vk.messages.getConversationsById(peer_ids=current_peer).get('items', [])
            if data:
                t = data[0].get('chat_settings', {}).get('title') or f'Беседа {current_peer - 2000000000}'
                titles.append(t)
                seen.add(t)
        except Exception:
            pass

    for peer, _ in get_all_chats():
        if peer == current_peer:
            continue
        if peer == APPLICATIONS_PEER_ID:
            continue
        if is_chat_hidden(peer):
            continue
        try:
            members = vk.messages.getConversationMembers(peer_id=peer).get('items', [])
            if any(m.get('member_id') == target for m in members):
                data = vk.messages.getConversationsById(peer_ids=peer).get('items', [])
                title = f'Беседа {peer - 2000000000}'
                if data:
                    title = data[0].get('chat_settings', {}).get('title') or title
                if title not in seen:
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
        return None, '❌ Укажи номер беседы.'
    chats = find_chats_by_number(vk, num)
    if not chats:
        return None, f'❌ Беседа с номером «{num}» не найдена.'
    if len(chats) > 1:
        return None, f'❌ Найдено несколько бесед с номером «{num}». Уточните название.'
    return chats[0], None


def handle_admin_command(command, user_id, peer_id, vk, text):
    keys = sorted(COMMAND_MIN_LEVEL, key=len, reverse=True)
    key = next((k for k in keys if command == k or command.startswith(k + ' ')), None)
    if not key:
        return False
    if not _require(key, user_id, peer_id, vk):
        return True
    rest = command[len(key):].strip()

    if key in {'пред', 'анпред', 'фулл анпред', 'кик', 'фулл кик', 'бан', 'разбан', 'снять', 'проверить'}:
        target = extract_user_id(rest)
        if not target:
            _send(vk, peer_id, f'❌ Формат: `лл {key} @user`', actor_inline=False)
            return True
        if key == 'проверить':
            text_out = _build_check(vk, target, peer_id)
            if not text_out:
                _send(vk, peer_id, '❌ Пользователь не найден.', actor_inline=False)
                return True
            _send(vk, peer_id, text_out, actor_inline=False)
            return True

        if not can_act(user_id, target, peer_id):
            _send(vk, peer_id, '❌ Нельзя управлять равным или более высоким уровнем.', actor_inline=False)
            return True

        if key == 'пред':
            _ensure_profile(vk, target)
            n = add_warning(target, peer_id, True)
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
                _send(vk, peer_id, f'❌ Не удалось исключить: {e}', actor_inline=False)
            return True
        if key == 'фулл кик':
            _ensure_profile(vk, target)
            add_kick_event(target, peer_id, user_id)
            kicked = 0
            from database import get_all_chats, is_chat_hidden
            for cp, _ in get_all_chats():
                if cp == APPLICATIONS_PEER_ID:
                    continue
                if is_chat_hidden(cp):
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
                if get_admin_level(user_id, peer_id) < 6:
                    _send(vk, peer_id, '❌ Глобальную роль может снять только Лелуш ви Британия.', actor_inline=False)
                    return True
                set_global_role(target, 0)
                _send(vk, peer_id, f'снял глобальную роль с {_user_link(vk, target)}.')
                _refresh_all_pins(vk)
                return True
            with db_cursor() as (_, c):
                c.execute("SELECT peer_id FROM admin_chat_rights WHERE user_id=? AND level>0", (target,))
                rows = c.fetchall()
            if not rows:
                _send(vk, peer_id, f'❌ У {_user_link(vk, target)} нет локальных прав ни в одной беседе.', actor_inline=False)
                return True
            removed = []
            for (rp,) in rows:
                set_admin_level(rp, target, 0, 'Участник')
                removed.append(rp)
            _send(vk, peer_id, f'снял права с {_user_link(vk, target)} в {len(removed)} беседах.')
            for rp in removed:
                _refresh_pin(vk, rp)
            return True

    if key == 'банстат':
        rows = get_banned_users()
        _send(vk, peer_id, '🔒 В бане никого нет.' if not rows else '\n'.join(
            ['🔒 Пользователи в бане:'] + [f'{i}. {n or "Пользователь"} — https://vk.com/id{u}' for i, (u, n) in enumerate(rows, 1)]), actor_inline=False)
        return True

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

    if key == 'выдать права':
        parts = rest.split()
        if len(parts) not in (2, 3):
            _send(vk, peer_id, '❌ Формат: `лл выдать права @user <уровень> [номер_беседы]`', actor_inline=False)
            return True
        target = extract_user_id(parts[0])
        try:
            level = int(parts[1])
        except Exception:
            level = -1
        if not target or level < 1 or level > 6:
            _send(vk, peer_id, '❌ Уровень должен быть от 1 до 6.', actor_inline=False)
            return True

        if is_in_admin_blacklist(target):
            _send(vk, peer_id, f'❌ {_user_link(vk, target)} находится в чёрном списке администрации. Сначала убери его оттуда.', actor_inline=False)
            return True

        _ensure_profile(vk, target)

        actor_level = get_admin_level(user_id, peer_id)
        if target == user_id:
            _send(vk, peer_id, '❌ Нельзя назначить права самому себе.', actor_inline=False)
            return True

        if level in (5, 6) and len(parts) == 2:
            if actor_level < 6:
                _send(vk, peer_id, '❌ Только Лелуш ви Британия может назначать глобальные роли.', actor_inline=False)
                return True
            if level == 6 and target == CREATOR_ID:
                _send(vk, peer_id, '❌ Этот пользователь уже является создателем.', actor_inline=False)
                return True
            set_global_role(target, level)
            role = ROLE_NAMES[level]
            _send(vk, peer_id, f'назначил {_user_link(vk, target)} на роль {role}.')
            _refresh_all_pins(vk)
            return True

        if level == 6:
            if actor_level < 6:
                _send(vk, peer_id, '❌ Только создатель может назначать Лелуша ви Британия.', actor_inline=False)
                return True
            set_global_role(target, 6)
            _send(vk, peer_id, f'назначил {_user_link(vk, target)} на роль Лелуш ви Британия.')
            _refresh_all_pins(vk)
            return True

        if len(parts) != 3:
            _send(vk, peer_id, '❌ Для уровней 1–4 укажи номер беседы.', actor_inline=False)
            return True
        target_peer, err = _resolve_target_peer(vk, parts[2])
        if err:
            _send(vk, peer_id, err, actor_inline=False)
            return True
        if not can_act(user_id, target, target_peer):
            _send(vk, peer_id, '❌ Нельзя управлять равным или более высоким уровнем.', actor_inline=False)
            return True
        set_admin_level(target_peer, target, level, ROLE_NAMES[level])
        _send(vk, peer_id, f'выдал {_user_link(vk, target)} уровень {level} — {ROLE_NAMES[level]} в беседе «{parts[2]}».')
        _refresh_pin(vk, target_peer)
        return True

    if key == 'чс адм':
        target = extract_user_id(rest)
        if not target:
            _send(vk, peer_id, '❌ Формат: `лл чс адм @user`', actor_inline=False)
            return True
        _ensure_profile(vk, target)
        add_to_admin_blacklist(target, user_id)
        _send(vk, peer_id, f'занёс {_user_link(vk, target)} в ЧС Администрации.')
        return True

    if key == 'убрать чс адм':
        target = extract_user_id(rest)
        if not target:
            _send(vk, peer_id, '❌ Формат: `лл убрать чс адм @user`', actor_inline=False)
            return True
        if not is_in_admin_blacklist(target):
            _send(vk, peer_id, f'❌ {_user_link(vk, target)} не в чёрном списке администрации.', actor_inline=False)
            return True
        remove_from_admin_blacklist(target)
        _send(vk, peer_id, f'убрал {_user_link(vk, target)} из ЧС Администрации.')
        return True

    if key == 'аватар':
        parts = rest.split()
        if len(parts) != 2:
            _send(vk, peer_id, '❌ Формат: `лл аватар @user <ID фотографии>`', actor_inline=False)
            return True
        target = extract_user_id(parts[0])
        photo_id = parts[1]
        if not target or not photo_id.isdigit():
            _send(vk, peer_id, '❌ Укажи пользователя и числовой ID фотографии.', actor_inline=False)
            return True
        _ensure_profile(vk, target)
        set_profile_image(target, f'photo-{GROUP_ID}_{photo_id}')
        _send(vk, peer_id, f'установил аватар для {_user_link(vk, target)}.')
        return True

    if key == 'изменить приветствие':
        photo = ''
        m = re.match(r'^(\d+)\s+(.+)$', rest)
        if m:
            photo_id, text = m.group(1), m.group(2).strip()
            photo = f'photo-{GROUP_ID}_{photo_id}'
            rest = text
        if not rest:
            _send(vk, peer_id, '❌ Формат: `лл изменить приветствие <ID фото> <текст>`', actor_inline=False)
            return True
        set_welcome_message(peer_id, rest, photo)
        _send(vk, peer_id, '✅ Приветствие изменено.', actor_inline=False)
        return True

    if key == 'приветствие':
        w, p = get_welcome_data(peer_id)
        args = {
            'peer_id': peer_id,
            'random_id': 0,
            'message': w or '',
            'disable_mentions': True,
        }
        if p:
            args['attachment'] = p
        try:
            vk.messages.send(**args)
        except Exception as e:
            print(f'⚠️ Не удалось показать приветствие: {e}')
        return True

    if key == 'рассылка':
        if not get_feature(peer_id, 'рассылка'):
            _send(vk, peer_id, '❌ Рассылка отключена в этой беседе.', actor_inline=False)
            return True
        if not rest:
            _send(vk, peer_id, '❌ Укажи сообщение.', actor_inline=False)
            return True
        chats = get_broadcast_chats()
        if not chats:
            _send(vk, peer_id, '❌ Ни в одной беседе рассылка не включена.', actor_inline=False)
            return True
        ok = bad = 0
        for cp in chats:
            try:
                vk.messages.send(peer_id=cp, random_id=0, message=rest)
                ok += 1
            except Exception:
                bad += 1
        _send(vk, peer_id, f'📢 Рассылка завершена. Доставлено: {ok}, ошибок: {bad}.', actor_inline=False)
        return True

    if key.startswith('переключить '):
        feature = key[len('переключить '):]
        state = toggle_feature(peer_id, feature)
        _send(vk, peer_id, f'⚙️ {feature}: {"включено" if state else "выключено"}.', actor_inline=False)
        return True

    if key == 'скрыть беседу':
        hide_chat(peer_id)
        _send(vk, peer_id, '🙈 Эта беседа скрыта из списка `лл беседы`.', actor_inline=False)
        return True

    if key == 'показать беседу':
        unhide_chat(peer_id)
        _send(vk, peer_id, '👁 Эта беседа снова видна в списке `лл беседы`.', actor_inline=False)
        return True

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
            f'🧹 Чистка: {"включена" if get_feature(peer_id, "чистка") else "выключена"}\n'
            f'🙈 Скрыта: {"да" if is_chat_hidden(peer_id) else "нет"}'
        ), actor_inline=False)
        return True

    if key == 'беседы':
        chats = get_all_chats()
        names = {}
        if chats:
            try:
                ids = [p for p, _ in chats]
                data = vk.messages.getConversationsById(peer_ids=','.join(map(str, ids))).get('items', [])
                names = {
                    int(x.get('peer', {}).get('id')): (x.get('chat_settings', {}).get('title') or f'Беседа {x.get("peer", {}).get("local_id", "")}')
                    for x in data
                }
            except Exception:
                pass

        def sort_key(item):
            p, _ = item
            title = names.get(p, f'Беседа {p - 2000000000 if p > 2000000000 else p}')
            m = re.match(r'^(.*?)(\d+)\s*$', title.strip())
            if m:
                return (m.group(1).strip().lower(), int(m.group(2)))
            return (title.strip().lower(), 0)

        chats = sorted(chats, key=sort_key)

        lines = ['💬 Активность бесед']
        for i, (p, _) in enumerate(chats, 1):
            a = get_chat_activity(p)
            title = names.get(p, f'Беседа {p - 2000000000 if p > 2000000000 else p}')
            lines.extend([
                f'{i}. {title}',
                f'День: {a["today"]}',
                f'Неделя: {a["week"]}',
                f'Месяц: {a["month"]}',
                f'Всё время: {a["total"]}',
                '────────────────────'
            ])
        if chats:
            lines.pop()
        _send(vk, peer_id, '\n'.join(lines), actor_inline=False)
        return True

    return True