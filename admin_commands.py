import re
from config import CREATOR_ID, GROUP_ID, APPLICATIONS_PEER_ID, RP_ALBUMS, RP_PHOTO_TOKEN
from response_context import get_user_id, get_exclude_actor
# Явные импорты вместо "from database import *"
from database import (
    get_global_role, set_global_role, get_admin_level_for_chat, set_admin_level, get_admins_for_chat,
    get_user, create_user, get_first_inviter, is_banned, is_in_admin_blacklist,
    get_warning_stats, get_kick_stats, get_messages_stats, get_last_message_at,
    add_warning, add_kick_event, remove_warning, clear_warnings,
    ban_user, unban_user, get_all_chats, get_banned_users,
    set_welcome_message, get_welcome_data, get_feature, get_broadcast_chats,
    toggle_feature, get_chat_activity, get_owner, get_application,
    db_cursor, get_all_global_roles, get_user_admin_rights, get_rp_photo_count, replace_rp_photos,
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
    'выдать права': 5, 'аватар': 4, 'обновить рп': 5,
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


def get_display_admin_level(user_id):
    """Highest assigned role for profile display, independent of current conversation.

    This is display-only. Permission checks must continue to use get_admin_level(user_id, peer_id).
    """
    if int(user_id) == CREATOR_ID:
        return 7
    try:
        global_level, local_roles = get_user_admin_rights(int(user_id))
        if global_level in (6, 7):
            return int(global_level)
        return max((int(level) for _, level in local_roles if 1 <= int(level) <= 5), default=0)
    except Exception as exc:
        print(f'[RIGHTS][PROFILE] Не удалось получить назначенные роли user={user_id}: {exc}')
        return 0


def get_admin_level(user_id, peer_id=None):
    if user_id == CREATOR_ID:
        return 7

    global_level = int(get_global_role(user_id) or 0)
    # Only levels 6 and 7 are global in this project. A stale/invalid row
    # must not override a valid local appointment.
    if global_level in (6, 7):
        return global_level

    if peer_id and peer_id > 2000000000:
        local = int(get_admin_level_for_chat(peer_id, user_id) or 0)
        if 1 <= local <= 5:
            return local

    owner = get_owner(user_id)
    if owner:
        if owner == CREATOR_ID:
            return 7
        owner_global = int(get_global_role(owner) or 0)
        if owner_global in (6, 7):
            return owner_global
        if peer_id and peer_id > 2000000000:
            owner_local = int(get_admin_level_for_chat(peer_id, owner) or 0)
            if 1 <= owner_local <= 5:
                return owner_local

    return 0


def _refresh_pin(vk, peer_id):
    try:
        result = refresh_after_admin_change(vk, peer_id=peer_id, global_change=False)
    except Exception as e:
        # Если бот вышел из беседы или она удалена, мы просто пишем в консоль, а не роняем бота
        print(f'⚠️ Не удалось обновить закреп {peer_id}: {e}')


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



def _sync_rp_photos():
    """Fetch configured RP albums using RP_PHOTO_TOKEN and cache attachment IDs."""
    if not RP_PHOTO_TOKEN:
        return (
            '❌ Не настроен RP_PHOTO_TOKEN. Добавь его в .env. '
            'Нужен отдельный токен, которому VK разрешает photos.get.'
        )

    try:
        import vk_api
        photo_vk = vk_api.VkApi(token=RP_PHOTO_TOKEN).get_api()
    except Exception as e:
        return f'❌ Не удалось создать сессию чтения фотографий: {e}'

    lines = ['📷 Результат синхронизации RP-альбомов:']
    total = 0
    for command_name, album_id in RP_ALBUMS.items():
        collected = []
        offset = 0
        try:
            while True:
                response = photo_vk.photos.get(
                    owner_id=-abs(int(GROUP_ID)),
                    album_id=int(album_id),
                    count=1000,
                    offset=offset,
                )
                items = response.get('items') or []
                for photo in items:
                    photo_id = photo.get('id')
                    owner_id = photo.get('owner_id', -abs(int(GROUP_ID)))
                    if photo_id is None:
                        continue
                    collected.append((
                        f'photo{int(owner_id)}_{int(photo_id)}',
                        int(photo_id),
                        int(owner_id),
                    ))
                if len(items) < 1000:
                    break
                offset += len(items)

            replace_rp_photos(command_name, collected)
            count = get_rp_photo_count(command_name)
            total += count
            lines.append(f'• {command_name}: {count}')
        except Exception as e:
            old_count = get_rp_photo_count(command_name)
            total += old_count
            lines.append(f'• {command_name}: ошибка; сохранено прежних фото: {old_count}')
            print(f'❌ RP album sync [{command_name}, album {album_id}]: {e}')

    lines.append(f'\nВсего в кэше: {total} фотографий.')
    return '\n'.join(lines)


def repair_legacy_local_role_peer_ids(vk):
    """Move legacy roles saved under 2000000000 + title_number to real peer IDs.

    Only migrates rows whose old peer_id is not registered as an actual chat and
    whose trailing title number resolves to exactly one registered conversation.
    The migration preserves the highest level and deletes the old row only after
    the replacement row has been written in the same SQLite transaction.
    """
    from database import get_all_chats
    try:
        registered = {int(peer) for peer, _ in get_all_chats()}
        with db_cursor() as (_, cur):
            legacy_rows = cur.execute(
                'SELECT peer_id, user_id, level FROM admin_chat_rights WHERE level BETWEEN 1 AND 5 ORDER BY peer_id'
            ).fetchall()
        moved = 0
        for old_peer, target_uid, level in legacy_rows:
            old_peer, target_uid, level = int(old_peer), int(target_uid), int(level)
            if old_peer in registered or old_peer <= 2000000000:
                continue
            number = old_peer - 2000000000
            if number <= 0:
                continue
            matches = find_chats_by_number(vk, str(number))
            if len(matches) != 1:
                continue
            real_peer = int(matches[0])
            if real_peer == old_peer:
                continue
            with db_cursor(True) as (_, cur):
                current = cur.execute(
                    'SELECT level FROM admin_chat_rights WHERE peer_id=? AND user_id=?',
                    (real_peer, target_uid),
                ).fetchone()
                merged_level = max(level, int(current[0]) if current else 0)
                cur.execute(
                    'INSERT INTO admin_chat_rights(peer_id,user_id,level) VALUES(?,?,?) '
                    'ON CONFLICT(peer_id,user_id) DO UPDATE SET level=excluded.level',
                    (real_peer, target_uid, merged_level),
                )
                verify = cur.execute(
                    'SELECT level FROM admin_chat_rights WHERE peer_id=? AND user_id=?',
                    (real_peer, target_uid),
                ).fetchone()
                if not verify or int(verify[0]) != merged_level:
                    raise RuntimeError('проверка переноса локальной роли не пройдена')
                cur.execute(
                    'DELETE FROM admin_chat_rights WHERE peer_id=? AND user_id=?',
                    (old_peer, target_uid),
                )
            moved += 1
            print(f'[RIGHTS][MIGRATION] moved user={target_uid} old_peer={old_peer} new_peer={real_peer} level={merged_level}')
        print(f'[RIGHTS][MIGRATION] legacy roles moved: {moved}')
        return moved
    except Exception as exc:
        print(f'[RIGHTS][MIGRATION] Ошибка восстановления старых локальных ролей: {exc}')
        return 0


def handle_admin_command(command, user_id, peer_id, vk, text):
    keys = sorted(COMMAND_MIN_LEVEL, key=len, reverse=True)
    key = next((k for k in keys if command == k or command.startswith(k + ' ')), None)
    if not key:
        return False
    if not _require(key, user_id, peer_id, vk):
        return True
    rest = command[len(key):].strip()
    raw_command = text[3:].strip() if text and text.lower().startswith('лл ') else text.strip()
    raw_rest = raw_command[len(key):].strip() if raw_command.lower().startswith(key) else rest
    if key == 'обновить рп':
        _send(vk, peer_id, _sync_rp_photos(), actor_inline=False)
        return True

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
    if key in {'пред', 'анпред', 'фулл анпред', 'кик', 'фулл кик', 'бан', 'разбан', 'проверить'}:
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
        grouped = {level: [] for level in range(1, 8)}
        seen = set()

        try:
            for uid, level in get_all_global_roles():
                level, uid = int(level), int(uid)
                if level in (6, 7) and uid not in seen:
                    grouped[level].append(uid)
                    seen.add(uid)
        except Exception as e:
            print(f'⚠️ Не удалось прочитать глобальные роли: {e}')

        if CREATOR_ID not in seen:
            grouped[7].append(CREATOR_ID)
            seen.add(CREATOR_ID)

        try:
            for uid, level in get_admins_for_chat(peer_id):
                uid, level = int(uid), int(level)
                if level in (1, 2, 3, 4, 5) and uid not in seen:
                    grouped[level].append(uid)
                    seen.add(uid)
        except Exception as e:
            print(f'⚠️ Не удалось прочитать локальные роли беседы {peer_id}: {e}')

        lines = ['👑 Администрация беседы:', '']
        for level in (7, 6, 5, 4, 3, 2, 1):
            lines.append(f'{ROLE_NAMES[level]}:')
            if grouped[level]:
                lines.extend(f'• {_user_link(vk, uid)}' for uid in grouped[level])
            else:
                lines.append('• Нет')
            lines.append('')

        _send(vk, peer_id, '\n'.join(lines), actor_inline=False)
        return True

    if key == 'выдать права':
        target = extract_user_id(rest)
        if not target:
            _send(vk, peer_id, 'Формат: `лл выдать права @user [номер беседы] <должность>`', actor_inline=False)
            return True

        cleaned = re.sub(r'\[id\d+\|[^\]]+\]', ' ', rest)
        cleaned = re.sub(r'https?://vk\.(?:com|ru)/id\d+', ' ', cleaned, flags=re.I)
        cleaned = re.sub(r'@id\d+', ' ', cleaned, flags=re.I)
        cleaned = re.sub(rf'\b{target}\b', ' ', cleaned)

        level = None
        role_phrase = None
        for phrase in sorted(ROLE_WORDS, key=len, reverse=True):
            if re.search(rf'(?<!\w){re.escape(phrase)}(?!\w)', cleaned, flags=re.I):
                level = ROLE_WORDS[phrase]
                role_phrase = phrase
                break

        if level is None:
            _send(vk, peer_id, 'Должность не распознана. Доступно: стажёр, активист, рекрутер, ЗК, куратор, вершитель, Лелуш.', actor_inline=False)
            return True

        cleaned = re.sub(re.escape(role_phrase), ' ', cleaned, flags=re.I)
        nums = re.findall(r'(?<!\w)\d+(?!\w)', cleaned)
        chat_number = int(nums[0]) if nums else None

        if is_in_admin_blacklist(target):
            _send(vk, peer_id, f'{_user_link(vk, target)} находится в ЧС администрации.', actor_inline=False)
            return True

        _ensure_profile(vk, target)
        actor_level = get_admin_level(user_id, peer_id)

        if level in (6, 7):
            if actor_level < 7:
                _send(vk, peer_id, 'Глобальные роли может выдавать только Лелуш ви Британия.', actor_inline=False)
                return True
            if level == 7 and target == CREATOR_ID:
                _send(vk, peer_id, 'Этот пользователь уже является создателем.', actor_inline=False)
                return True
            try:
                set_global_role(target, level)
                saved_global = get_global_role(target)
            except Exception as exc:
                print(f'[RIGHTS][DB-WRITE] Ошибка сохранения глобальной роли target={target}, level={level}: {exc}')
                _send(vk, peer_id, 'Не удалось сохранить глобальные права в SQLite. Подробности записаны в журнал бота.', actor_inline=False)
                return True
            if saved_global != level:
                print(f'[RIGHTS][DB-WRITE] Глобальная роль не подтверждена target={target}, requested={level}, saved={saved_global}')
                _send(vk, peer_id, f'Ошибка проверки глобальной роли: запрошен уровень {level}, в базе найден {saved_global}.', actor_inline=False)
                return True
            print(f'[RIGHTS][DB-WRITE] GLOBAL OK target={target} level={saved_global} role={ROLE_NAMES[level]}')
            _send(vk, peer_id, f'Назначена глобальная роль «{ROLE_NAMES[level]}» для {_user_link(vk, target)}. Права сохранены.', actor_inline=False)
            _refresh_all_pins(vk)
            return True

        if level >= actor_level:
            _send(vk, peer_id, 'Нельзя выдавать роль равную или выше собственной.', actor_inline=False)
            return True

        if chat_number is None or chat_number <= 0:
            _send(vk, peer_id, 'Для локальной роли укажи номер беседы: `лл выдать права @user 1 стажёр`.', actor_inline=False)
            return True

        # A chat number is the trailing number in its title, not a VK peer_id.
        # The old arithmetic conversion wrote roles to IDs that did not belong
        # to the actual conversation, so profiles, lists and pins could not see them.
        if chat_number > 2000000000:
            target_peer = chat_number
        else:
            matches = find_chats_by_number(vk, str(chat_number))
            if not matches:
                _send(vk, peer_id, f'Беседа с номером «{chat_number}» не найдена среди зарегистрированных бесед. Проверь номер в названии и используй `лл беседы`.', actor_inline=False)
                return True
            if len(matches) > 1:
                _send(vk, peer_id, f'Найдено несколько бесед с номером «{chat_number}». Сделай номера в названиях уникальными.', actor_inline=False)
                return True
            target_peer = int(matches[0])

        if not can_act(user_id, target, target_peer):
            _send(vk, peer_id, 'Недостаточно прав: нельзя выдать роль равную или выше своей.', actor_inline=False)
            return True

        try:
            set_admin_level(target_peer, target, level, ROLE_NAMES[level])
            saved_level = get_admin_level_for_chat(target_peer, target)
        except Exception as exc:
            print(f'[RIGHTS][DB-WRITE] Ошибка сохранения target={target}, peer={target_peer}, level={level}: {exc}')
            _send(vk, peer_id, 'Не удалось сохранить права в SQLite. Подробности записаны в журнал бота.', actor_inline=False)
            return True

        if saved_level != level:
            print(f'[RIGHTS][DB-WRITE] Проверка не пройдена target={target}, peer={target_peer}, requested={level}, saved={saved_level}')
            _send(vk, peer_id, f'Ошибка проверки записи прав: запрошен уровень {level}, в базе найден {saved_level}.', actor_inline=False)
            return True

        print(f'[RIGHTS][DB-WRITE] OK target={target} peer={target_peer} level={saved_level} role={ROLE_NAMES[level]}')
        _send(vk, peer_id, f'Назначена локальная роль «{ROLE_NAMES[level]}» для {_user_link(vk, target)} в беседе №{chat_number}. Права сохранены.', actor_inline=False)
        _refresh_pin(vk, target_peer)
        return True

    if key == 'снять':
        target = extract_user_id(rest)
        if not target:
            _send(vk, peer_id, 'Формат: `лл снять @user`', actor_inline=False)
            return True

        if get_global_role(target):
            if get_admin_level(user_id, peer_id) < 7:
                _send(vk, peer_id, 'Снимать глобальные роли может только Лелуш ви Британия.', actor_inline=False)
                return True
            set_global_role(target, 0)
            _send(vk, peer_id, f'Глобальная роль снята с {_user_link(vk, target)}.', actor_inline=False)
            _refresh_all_pins(vk)
            return True

        with db_cursor() as (_, c):
            c.execute(
                'SELECT peer_id, level FROM admin_chat_rights WHERE user_id=? AND level>0',
                (target,),
            )
            rows = c.fetchall()

        if not rows:
            _send(vk, peer_id, f'У {_user_link(vk, target)} нет административных прав.', actor_inline=False)
            return True

        for target_peer, _level in rows:
            if not can_act(user_id, target, target_peer):
                _send(vk, peer_id, 'Недостаточно прав для снятия одной или нескольких ролей.', actor_inline=False)
                return True

        removed = []
        for target_peer, _level in rows:
            set_admin_level(target_peer, target, 0, 'Участник')
            removed.append(target_peer)

        _send(vk, peer_id, f'Сняты локальные права с {_user_link(vk, target)} в беседах: {len(removed)}.', actor_inline=False)
        for target_peer in removed:
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
        rest = raw_rest
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
        rest = raw_rest
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