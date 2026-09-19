import re
from config import CREATOR_ID, GROUP_ID, PROFILE_WELCOME_ALBUM_ID
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
        return get_admin_level_for_chat(peer_id, user_id)
    return 0


def _refresh_pin(vk, peer_id):
    try:
        from pin_manager import update_pin_in_chat
        update_pin_in_chat(vk, peer_id)
    except Exception as e:
        print(f'⚠️ Не удалось обновить закреп {peer_id}: {e}')


def _refresh_all_pins(vk):
    try:
        from pin_manager import update_all_pins
        update_all_pins(vk)
    except Exception as e:
        print(f'⚠️ Не удалось обновить все закрепы: {e}')


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


def can_act(actor, target, peer):
    if actor == target:
        return False
    return get_admin_level(target, peer) < get_admin_level(actor, peer)


def _send(vk, p, msg):
    actor = get_user_id()
    if actor and not get_exclude_actor():
        try:
            info = vk.users.get(user_ids=actor)[0]
            from relationships import get_display_name
            label = get_display_name(actor) or info.get("first_name", "Пользователь")
        except Exception:
            label = "Пользователь"
        msg = f"[id{actor}|{label}]\n{msg}"
    vk.messages.send(peer_id=p, random_id=0, message=msg, disable_mentions=True)


def _require(key, uid, peer, vk):
    if get_admin_level(uid, peer) < COMMAND_MIN_LEVEL[key]:
        _send(vk, peer, f'❌ Недостаточно прав. Требуется уровень {COMMAND_MIN_LEVEL[key]} — {ROLE_NAMES[COMMAND_MIN_LEVEL[key]]}.')
        return False
    return True


def _fmt_date(s):
    if not s:
        return '—'
    s = str(s)[:10]
    try:
        y,m,d = s.split('-')
        return f'{d}.{m}.{y}'
    except Exception:
        return s


def _build_check(vk, target, peer_id):
    from relationships import get_display_name
    u = get_user(target)
    if not u:
        return None

    name = u[1] or 'Пользователь'
    display = u[2] or name.split()[0]
    link = f'[id{target}|{name}]'

    # Пригласивший
    inviter_id = get_first_inviter(target)
    if inviter_id:
        inviter_name = get_display_name(inviter_id) or ''
        if not inviter_name:
            try:
                info = vk.users.get(user_ids=inviter_id)[0]
                inviter_name = f"{info.get('first_name','')} {info.get('last_name','')}".strip()
            except Exception:
                inviter_name = 'Пользователь'
        inviter_line = f'[id{inviter_id}|{inviter_name}]'
    else:
        inviter_line = '—'

    join_date = _fmt_date(u[14])

    # Права
    level = get_admin_level(target, peer_id)
    rights = ROLE_NAMES.get(level, 'Участник')

    # Бан и ЧС
    banned_line = 'Да' if is_banned(target) else 'Нет'
    bl_line = 'Да' if is_in_admin_blacklist(target) else 'Нет'

    # Предупреждения
    adm_w = get_warning_stats(target, True)
    w = get_warning_stats(target, False)
    kicks = get_kick_stats(target)

    # Беседы
    peers = get_all_chat_memberships(target)
    chat_titles = []
    if peers:
        try:
            ids = ','.join(str(p) for p in peers)
            data = vk.messages.getConversationsById(peer_ids=ids).get('items', [])
            for item in data:
                t = item.get('chat_settings', {}).get('title') or f"Беседа {item.get('peer',{}).get('local_id','')}"
                chat_titles.append(t)
        except Exception as e:
            print(f'⚠️ Не удалось получить беседы: {e}')

    # Активность
    msgs = get_messages_stats(target)
    last = get_last_message_at(target)
    last_fmt = '—'
    if last:
        try:
            dt = __import__('datetime').datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
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
            _send(vk, peer_id, f'❌ Формат: `лл {key} @user`')
            return True
        if key == 'проверить':
            text_out = _build_check(vk, target, peer_id)
            if not text_out:
                _send(vk, peer_id, '❌ Пользователь не найден.')
                return True
            _send(vk, peer_id, text_out)
            return True

        if not can_act(user_id, target, peer_id):
            _send(vk, peer_id, '❌ Нельзя управлять равным или более высоким уровнем.')
            return True

        if key == 'пред':
            n = add_warning(target, peer_id, True)
            _send(vk, peer_id, f'⚠️ Предупреждение выдано пользователю {_user_link(vk, target)}: {n}/3.')
            return True
        if key == 'анпред':
            left = remove_warning(target, peer_id, True)
            _send(vk, peer_id, f'✅ У пользователя {_user_link(vk, target)} снято одно предупреждение. Осталось: {left}/3')
            return True
        if key == 'фулл анпред':
            clear_warnings(target, peer_id, True)
            _send(vk, peer_id, '✅ Все предупреждения в этой беседе сняты.')
            return True
        if key == 'бан':
            ban_user(target)
            add_kick_event(target, peer_id, user_id)
            try:
                vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target)
            except Exception:
                pass
            _send(vk, peer_id, '🔨 Пользователь забанен и удалён из беседы.')
            return True
        if key == 'разбан':
            unban_user(target)
            _send(vk, peer_id, '✅ Пользователь разбанен.')
            return True
        if key in {'кик', 'фулл кик'}:
            add_kick_event(target, peer_id, user_id)
            try:
                vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target)
                _send(vk, peer_id, '✅ Пользователь исключён из беседы.')
            except Exception as e:
                _send(vk, peer_id, f'❌ Не удалось исключить: {e}')
            return True
        if key == 'снять':
            if get_global_role(target):
                if get_admin_level(user_id, peer_id) < 6:
                    _send(vk, peer_id, '❌ Глобальную роль может снять только Лелуш ви Британия.')
                    return True
                set_global_role(target, 0)
                _send(vk, peer_id, f'✅ Глобальная роль снята: {_user_link(vk, target)}.')
                _refresh_all_pins(vk)
                return True
            set_admin_level(peer_id, target, 0, 'Участник')
            _send(vk, peer_id, f'✅ Права в этой беседе сняты: {_user_link(vk, target)}.')
            _refresh_pin(vk, peer_id)
            return True

    if key == 'банстат':
        rows = get_banned_users()
        _send(vk, peer_id, '🔒 В бане никого нет.' if not rows else '\n'.join(
            ['🔒 Пользователи в бане:'] + [f'{i}. {n or "Пользователь"} — https://vk.com/id{u}' for i, (u, n) in enumerate(rows, 1)]))
        return True

    if key == 'админы':
        with db_cursor() as (_, c):
            c.execute('SELECT peer_id,user_id,level FROM admin_chat_rights WHERE level>0 ORDER BY level DESC,peer_id')
            rows = c.fetchall()
        if not rows:
            _send(vk, peer_id, '📋 Администраторов нет.')
            return True
        _send(vk, peer_id, '👑 Администрация по беседам:\n' + '\n'.join(
            f'Беседа {p}: {ROLE_NAMES.get(l, str(l))} — https://vk.com/id{u}' for p, u, l in rows))
        return True

    if key == 'выдать права':
        parts = rest.split()
        if len(parts) not in (2, 3):
            _send(vk, peer_id, '❌ Формат: `лл выдать права @user <уровень> [номер_беседы]`')
            return True
        target = extract_user_id(parts[0])
        try:
            level = int(parts[1])
        except Exception:
            level = -1
        if not target or level < 1 or level > 6:
            _send(vk, peer_id, '❌ Уровень должен быть от 1 до 6.')
            return True

        if is_in_admin_blacklist(target):
            _send(vk, peer_id, f'❌ {_user_link(vk, target)} находится в чёрном списке администрации. Сначала убери его оттуда.')
            return True

        actor_level = get_admin_level(user_id, peer_id)
        if target == user_id:
            _send(vk, peer_id, '❌ Нельзя назначить права самому себе.')
            return True

        if level in (5, 6) and len(parts) == 2:
            if actor_level < 6:
                _send(vk, peer_id, '❌ Только Лелуш ви Британия может назначать глобальные роли.')
                return True
            if level == 6 and target == CREATOR_ID:
                _send(vk, peer_id, '❌ Этот пользователь уже является создателем.')
                return True
            set_global_role(target, level)
            role = ROLE_NAMES[level]
            _send(vk, peer_id, f'✅ {role} назначен: {_user_link(vk, target)}')
            _refresh_all_pins(vk)
            return True

        if level == 6:
            if actor_level < 6:
                _send(vk, peer_id, '❌ Только создатель может назначать Лелуша ви Британия.')
                return True
            set_global_role(target, 6)
            _send(vk, peer_id, f'✅ Лелуш ви Британия назначен: {_user_link(vk, target)}')
            _refresh_all_pins(vk)
            return True

        if len(parts) != 3:
            _send(vk, peer_id, '❌ Для уровней 1–4 укажи номер беседы.')
            return True
        try:
            chat_number = int(parts[2])
        except Exception:
            chat_number = -1
        target_peer = chat_number if chat_number > 2000000000 else 2000000000 + chat_number
        if chat_number <= 0:
            _send(vk, peer_id, '❌ Некорректный номер беседы.')
            return True
        if not can_act(user_id, target, target_peer):
            _send(vk, peer_id, '❌ Нельзя управлять равным или более высоким уровнем.')
            return True
        set_admin_level(target_peer, target, level, ROLE_NAMES[level])
        _send(vk, peer_id, f'✅ Выдан уровень {level} — {ROLE_NAMES[level]} в беседе {chat_number}.')
        _refresh_pin(vk, target_peer)
        return True

    if key == 'чс адм':
        target = extract_user_id(rest)
        if not target:
            _send(vk, peer_id, '❌ Формат: `лл чс адм @user`')
            return True
        if not get_user(target):
            _send(vk, peer_id, '❌ У пользователя нет профиля.')
            return True
        add_to_admin_blacklist(target, user_id)
        _send(vk, peer_id, f'🚫 {_user_link(vk, target)} занесён в чёрный список администрации.')
        return True

    if key == 'убрать чс адм':
        target = extract_user_id(rest)
        if not target:
            _send(vk, peer_id, '❌ Формат: `лл убрать чс адм @user`')
            return True
        if not is_in_admin_blacklist(target):
            _send(vk, peer_id, f'❌ {_user_link(vk, target)} не в чёрном списке администрации.')
            return True
        remove_from_admin_blacklist(target)
        _send(vk, peer_id, f'✅ {_user_link(vk, target)} убран из чёрного списка администрации.')
        return True

    if key == 'аватар':
        parts = rest.split()
        if len(parts) != 2:
            _send(vk, peer_id, '❌ Формат: `лл аватар @user <ID фотографии>`')
            return True
        target = extract_user_id(parts[0])
        photo_id = parts[1]
        if not target or not photo_id.isdigit():
            _send(vk, peer_id, '❌ Укажи пользователя и числовой ID фотографии.')
            return True
        album_id = PROFILE_WELCOME_ALBUM_ID
        try:
            photos = vk.photos.get(owner_id=-GROUP_ID, album_id=album_id, count=1000)['items']
            photo = next((x for x in photos if str(x['id']) == photo_id), None)
        except Exception as e:
            _send(vk, peer_id, f'❌ Не удалось проверить фотографию в альбоме: {e}')
            return True
        if not photo:
            _send(vk, peer_id, '❌ Фотография с таким ID не найдена в указанном альбоме.')
            return True
        set_profile_image(target, f'photo-{GROUP_ID}_{photo_id}')
        _send(vk, peer_id, f'🖼 Аватар для {_user_link(vk, target)} установлен.')
        return True

    if key == 'изменить приветствие':
        photo = ''
        m = re.match(r'^(\d+)\s+(.+)$', rest)
        if m:
            photo_id, text = m.group(1), m.group(2).strip()
            try:
                photos = vk.photos.get(owner_id=-GROUP_ID, album_id=PROFILE_WELCOME_ALBUM_ID, count=1000)['items']
                if any(str(x['id']) == photo_id for x in photos):
                    photo = f'photo-{GROUP_ID}_{photo_id}'
                    rest = text
                else:
                    _send(vk, peer_id, '❌ Фотография с таким ID не найдена в альбоме.')
                    return True
            except Exception as e:
                _send(vk, peer_id, f'❌ Не удалось проверить фотографию: {e}')
                return True
        if not rest:
            _send(vk, peer_id, '❌ Формат: `лл изменить приветствие <ID фото> <текст>`')
            return True
        set_welcome_message(peer_id, rest, photo)
        _send(vk, peer_id, '✅ Приветствие изменено.')
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
        if not rest:
            _send(vk, peer_id, '❌ Укажи сообщение.')
            return True
        chats = get_broadcast_chats()
        if not chats:
            _send(vk, peer_id, '❌ Ни в одной беседе рассылка не включена.')
            return True
        ok = bad = 0
        for cp in chats:
            try:
                vk.messages.send(peer_id=cp, random_id=0, message=rest)
                ok += 1
            except Exception:
                bad += 1
        _send(vk, peer_id, f'📢 Рассылка завершена. Доставлено: {ok}, ошибок: {bad}.')
        return True

    if key.startswith('переключить '):
        feature = key[len('переключить '):]
        state = toggle_feature(peer_id, feature)
        _send(vk, peer_id, f'⚙️ {feature}: {"включено" if state else "выключено"}.')
        return True

    if key == 'скрыть беседу':
        hide_chat(peer_id)
        _send(vk, peer_id, '🙈 Эта беседа скрыта из списка `лл беседы`.')
        return True

    if key == 'показать беседу':
        unhide_chat(peer_id)
        _send(vk, peer_id, '👁 Эта беседа снова видна в списке `лл беседы`.')
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
        ))
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
        _send(vk, peer_id, '\n'.join(lines))
        return True

    return True