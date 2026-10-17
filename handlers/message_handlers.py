import json, re
from config import CREATOR_ID, ALLOWED_IN_DM
from database import (
    get_user, create_user, user_exists, transfer_coins, debit_gems, 
    update_coins, clear_warnings, set_nickname, get_owner, 
    get_twinks, remove_twink, add_twink, is_twink, 
    get_feature, get_application, delete_application, 
    upsert_application, set_gif_link, set_status, 
    get_property_value, db_cursor, set_salary_multiplier, 
    increase_salary_multiplier, get_salary_multiplier, 
    add_admin_stat, has_active_duel, create_duel, get_duel_for_opponent, delete_duel
)
from admin_commands import handle_admin_command, get_admin_level
from games import casino
from wheel import spin_wheel, draw_wheel
from vk_upload import upload_photo
from jobs.work_handler import work, hire, fire, job_stats
from handlers.user_handlers import (
    get_profile,
    get_profile_data,
    get_balance,
    set_nickname_command,
    get_activity,
    is_admin,
)
from handlers.rp_handlers import handle_rp_command
from relationships import (
    parse_target_id, start_relationship, end_relationship, divorce,
    adopt, relinquish, leave_family, get_partner_id, get_display_name,
    get_family_stats,
)
from property_shop import buy_property, get_items
from response_context import set_user, get_user_id, get_exclude_actor
from jobs.professions import PROFESSIONS


def _user_link(vk, user_id, fallback='Пользователь'):
    try:
        info = vk.users.get(user_ids=user_id)[0]
        label = get_display_name_safe(user_id, info.get('first_name', 'Пользователь'))
    except Exception:
        label = get_display_name_safe(user_id, fallback)
    return f'[id{user_id}|{label}]'


def _send(vk, peer_id, msg, keyboard=None, attachment=None, exclude_actor=False):
    actor = get_user_id()
    if actor and not exclude_actor and not get_exclude_actor():
        msg = f'{_user_link(vk, actor)} {msg}'
    args = {'peer_id': peer_id, 'random_id': 0, 'message': msg}
    if keyboard is not None:
        args['keyboard'] = json.dumps(keyboard, ensure_ascii=False)
    if attachment:
        args['attachment'] = attachment
    args['disable_mentions'] = True
    vk.messages.send(**args)


def _target(s): return parse_target_id(s)


def get_display_name_safe(uid, fallback):
    from relationships import get_display_name
    return get_display_name(uid) or fallback


# ============ VIP МАГАЗИН ============

VIP_PRICES = {
    1: 100,  # GIF/видео в профиль
    2: 100,  # Статус
    3: 65,   # Снять предупреждение
    4: 100,  # Множитель зарплаты
}


def vip_shop_text():
    return (
        '💎 VIP-магазин\n\n'
        '1. GIF/видео в профиль — 100 💎\n'
        '2. Статус в профиле — 100 💎\n'
        '3. Снять предупреждение — 65 💎\n'
        '4. Повысить множитель зарплаты — 100 💎\n\n'
        'Покупка: `лл купить <номер>`'
    )


def _check_salary_mult_cap(user_id):
    """Максимум множителя — x7."""
    return get_salary_multiplier(user_id) >= 7.0


def handle_command(command, user_id, peer_id, vk, text):
    list_commands = {'меню', 'магазин', 'беседы', 'админы', 'банстат', 'твинки'}
    set_user(user_id, command.split()[0] in list_commands)
    is_chat = peer_id > 2000000000
    if not is_chat:
        return

    if handle_admin_command(command, user_id, peer_id, vk, text):
        return

    # ─── МЕНЮ ────────────────────────────────────────────
    if command == 'меню':
        from keyboards import menu_keyboard
        is_adm = get_admin_level(user_id, peer_id) >= 1
        _send(vk, peer_id,
              '📖 Меню Lelouch Bot\n\nВыбери нужный раздел ниже. '
              'При нажатии текст этого сообщения будет заменён на выбранный раздел.',
              menu_keyboard(is_adm), exclude_actor=True)
        return

    # ─── VIP-МАГАЗИН ─────────────────────────────────────
    if command == 'вип магазин':
        _send(vk, peer_id, vip_shop_text(), exclude_actor=True)
        return

    if command.startswith('купить '):
        parts = command.split()
        if len(parts) != 2:
            return
        try:
            n = int(parts[1])
        except ValueError:
            return
        price = VIP_PRICES.get(n)
        if not price:
            return

        # Проверка на кап множителя
        if n == 4 and _check_salary_mult_cap(user_id):
            _send(vk, peer_id, 'Множитель уже максимальный (×7).', exclude_actor=True)
            return

        if not debit_gems(user_id, price):
            _send(vk, peer_id, 'Недостаточно Камней души.', exclude_actor=True)
            return

        if n == 1:
            _send(vk, peer_id,
                  'GIF/видео в профиль куплено. Пришли ссылку на документ VK '
                  '(в формате https://vk.com/doc-XXXX_YYYY) следующим сообщением.',
                  exclude_actor=True)
            upsert_application(user_id, 'await_gif', 0, [])
            return
        if n == 2:
            _send(vk, peer_id,
                  'Статус куплен. Напиши текст статуса следующим сообщением (до 60 символов).',
                  exclude_actor=True)
            upsert_application(user_id, 'await_status', 0, [])
            return
        if n == 3:
            clear_warnings(user_id, peer_id)
            _send(vk, peer_id, 'Предупреждение снято.', exclude_actor=True)
            return
        if n == 4:
            new_mult = increase_salary_multiplier(user_id, 0.5, 7.0)
            _send(vk, peer_id, f'Множитель зарплаты повышен. Теперь ×{new_mult}.', exclude_actor=True)
            return
        return

    # ─── Ожидание GIF/статуса (в ЛС) ────────────────────
    # (обрабатывается в main.py через handle_dm_message)

    # ─── ПРОФИЛЬ ────────────────────────────────────────
    if command == 'профиль' or command.startswith('профиль '):
        rest = command[len('профиль'):].strip() if command != 'профиль' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target):
            _send(vk, peer_id, 'Пользователь не найден.', exclude_actor=True)
            return
        profile_text, profile_attachment = get_profile_data(target, peer_id)
        _send(vk, peer_id, profile_text, attachment=profile_attachment, exclude_actor=True)
        return

    if command == 'баланс' or command.startswith('баланс '):
        rest = command[len('баланс'):].strip() if command != 'баланс' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target):
            _send(vk, peer_id, 'Пользователь не найден.', exclude_actor=True)
            return
        _send(vk, peer_id, get_balance(target, vk), exclude_actor=True)
        return

    if command.startswith('ник '):
        nick = command[4:].strip()
        if not 1 <= len(nick) <= 30:
            _send(vk, peer_id, 'Ник должен быть от 1 до 30 символов.', exclude_actor=True)
            return
        set_nickname(user_id, nick)
        link = f'[id{user_id}|{nick}]'
        _send(vk, peer_id, f'Ваш новый никнейм: {link}', exclude_actor=True)
        return

    if command == 'активность' or command.startswith('активность '):
        rest = command[len('активность'):].strip() if command != 'активность' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target):
            _send(vk, peer_id, 'Пользователь не найден.')
            return
        _send(vk, peer_id, get_activity(target))
        return

    # ─── ЛЛ НОРМА ────────────────────────────────────────
    if command == 'норма' or command.startswith('норма '):
        handle_norma(command, user_id, peer_id, vk)
        return

    # ─── ТВИНКИ ─────────────────────────────────────────
    if command == 'твинк' or command.startswith('твинк '):
        parts = command.split(maxsplit=2)
        if len(parts) >= 2 and parts[1] == 'убрать':
            if len(parts) < 3:
                return
            target = _target(parts[2])
            if not target:
                return
            if not is_twink(target):
                return
            owner = get_owner(target)
            actor_level = __import__('admin_commands').get_admin_level(user_id, peer_id)
            if user_id != owner and actor_level < 5:
                return
            remove_twink(target)
            return

        if len(parts) < 2:
            return
        twink_id = _target(parts[1])
        if not twink_id:
            return
        if twink_id == user_id:
            return
        if not get_user(twink_id):
            try:
                info = vk.users.get(user_ids=twink_id)[0]
                name = f"{info.get('first_name','')} {info.get('last_name','')}".strip() or 'Пользователь'
                create_user(twink_id, name)
            except Exception as e:
                print(f'⚠️ Не удалось создать профиль твинка: {e}')
        if is_twink(twink_id):
            return
        add_twink(user_id, twink_id)
        return

    if command == 'твинки' or command.startswith('твинки '):
        parts = command.split(maxsplit=1)
        if len(parts) == 1:
            target = user_id
        else:
            t = _target(parts[1])
            if not t:
                return
            target = t
        owner = get_owner(target) or target
        twinks = get_twinks(owner)
        header = f'👥 Твинки {_user_link(vk, owner)}:'
        if not twinks:
            _send(vk, peer_id, header + '\n-нет', exclude_actor=True)
            return
        lines = [header]
        for tid in twinks:
            name = ''
            try:
                info = vk.users.get(user_ids=tid)[0]
                name = f"{info.get('first_name','')} {info.get('last_name','')}".strip() or 'Пользователь'
            except Exception:
                name = 'Пользователь'
            lines.append(f'- [id{tid}|{name}]')
        _send(vk, peer_id, '\n'.join(lines), exclude_actor=True)
        return

    # ─── ЗАЯВКА ─────────────────────────────────────────
    if command == 'заявка':
        _send(vk, peer_id, '📩 Заявка подаётся в личные сообщения бота.\n\nНапиши боту в ЛС: `лл заявка`.')
        return

    # ─── ЗАКРЕПЫ ────────────────────────────────────────
    if command == 'установить закреп':
        if get_admin_level(user_id, peer_id) < 4:
            _send(vk, peer_id, 'Недостаточно прав', exclude_actor=True)
            return
        from pin_manager import update_pin_in_chat
        update_pin_in_chat(vk, peer_id, notify=True)
        return

    if command == 'обновить закрепы':
        if user_id != CREATOR_ID:
            if get_admin_level(user_id, peer_id) < 7:
                _send(vk, peer_id, 'Недостаточно прав', exclude_actor=True)
                return
        from pin_manager import update_all_pins
        results = update_all_pins(vk)
        ok = len([r for r in results if r[1] in ('updated', 'created', 'recreated')])
        _send(vk, peer_id, f'Обновлено бесед: {ok} из {len(results)}.', exclude_actor=True)
        return

    # ─── ДУЭЛЬ ──────────────────────────────────────────
    if command.startswith('дуэль'):
        if not get_feature(peer_id, 'дуэль'):
            _send(vk, peer_id, 'Дуэли в этой беседе запрещены', exclude_actor=True)
            return
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            return
        opponent = parse_target_id(parts[1])
        if not opponent:
            return
        if opponent == user_id:
            return
        if not get_user(opponent):
            return
        if has_active_duel(user_id) or has_active_duel(opponent):
            _send(vk, peer_id, 'У одного из участников уже активна дуэль.', exclude_actor=True)
            return

        text_msg = (
            f'⚔️ {_user_link(vk, user_id)} вызвал на дуэль {_user_link(vk, opponent)}!\n\n'
            f'Ставка: 15% от Силы Гиаса проигравшего.'
        )
        from keyboards import duel_keyboard
        vk.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=text_msg,
            keyboard=json.dumps(duel_keyboard(), ensure_ascii=False),
            disable_mentions=True,
        )
        create_duel(user_id, opponent, peer_id, None)
        return

    # ─── РУЛЕТКА ────────────────────────────────────────
    if command.startswith('рулетка'):
        if not get_feature(peer_id, 'казино'):
            _send(vk, peer_id, 'Казино в этой беседе запрещено.', exclude_actor=True)
            return
        parts = command.split()
        if len(parts) != 2:
            return
        try:
            bet = int(parts[1])
        except ValueError:
            return
        if bet < 1000:
            _send(vk, peer_id, 'Минимальная ставка: 1 000 монет.', exclude_actor=True)
            return
        user = get_user(user_id)
        if not user:
            return
        # 5 — coins
        if bet > user[5]:
            _send(vk, peer_id, 'Недостаточно монет.', exclude_actor=True)
            return

        idx, number, color = spin_wheel()
        color_ru = {'red': 'Красное', 'black': 'Чёрное', 'green': 'Зелёное'}[color]
        if color == 'black':
            mult = 0
        elif color == 'red':
            mult = 2
        else:
            mult = 5
        win_amount = bet * mult
        update_coins(user_id, win_amount - bet)
        try:
            photo_path = draw_wheel(idx)
            attachment = upload_photo(vk, photo_path, peer_id)
        except Exception as e:
            print(f'⚠️ Не удалось сгенерировать/загрузить колесо: {e}')
            attachment = None

        text_roulette = (
            f'{_user_link(vk, user_id)}\n'
            f'Выпало: {number} — {color_ru}\n'
            f'Множитель: х{mult}\n'
            f'Выигрыш: {win_amount:,}'
        )
        if attachment:
            _send(vk, peer_id, text_roulette, attachment=attachment, exclude_actor=True)
        else:
            _send(vk, peer_id, text_roulette, exclude_actor=True)
        return

    # ─── КАЗИНО ─────────────────────────────────────────
    if command.startswith('деп'):
        if not get_feature(peer_id, 'казино'):
            _send(vk, peer_id, 'Казино в этой беседе запрещено.', exclude_actor=True)
            return
        parts = command.split()
        if len(parts) != 2:
            return
        try:
            bet = int(parts[1])
        except ValueError:
            return
        if bet <= 0:
            return
        result, mult, err = casino(user_id, bet)
        if err:
            _send(vk, peer_id, err, exclude_actor=True)
            return
        if result is None:
            return
        if mult == 0:
            _send(vk, peer_id, 'проиграл всю ставку')
        else:
            _send(vk, peer_id, f'получил модификатор х{mult}.\nВыигрыш составляет: {result:,}')
        return

    # ─── ПЕРЕВОД МОНЕТ ──────────────────────────────────
    if command == 'передать' or command.startswith('передать '):
        parts = command.split(maxsplit=2)
        if len(parts) != 3:
            return
        target = _target(parts[1])
        try:
            amount = int(parts[2])
        except ValueError:
            return
        if not target or amount <= 0:
            return
        if target == user_id:
            return
        if not get_user(target):
            return
        if not transfer_coins(user_id, target, amount):
            _send(vk, peer_id, 'У вас недостаточно монет.', exclude_actor=True)
            return
        _send(vk, peer_id, f'Передано {amount:,} 🪙 пользователю {_user_link(vk, target)}.')
        return

    # ─── РАБОТА (статистика) ────────────────────────────
    if command == 'работа' or command.startswith('работа '):
        rest = command[len('работа'):].strip() if command != 'работа' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target):
            _send(vk, peer_id, 'Пользователь не найден.', exclude_actor=True)
            return
        stats = job_stats(target, viewer_id=user_id)
        if stats is None:
            _send(vk, peer_id, f'У {_user_link(vk, target)} нет работы.', exclude_actor=True)
            return
        if isinstance(stats, str):
            _send(vk, peer_id, stats, exclude_actor=True)
            return
        mult = stats['multiplier']
        text_work = (
            f'Статистика работы {_user_link(vk, target)}\n'
            f'Работа: {stats["job_name"]}\n'
            f'Должность: {stats["level_name"]}\n'
            f'Зарплата: {stats["salary"]:,} 🪙 (×{mult})\n'
            f'⚡ Сила Гиаса: +{stats["power_per_work"]}\n'
            f'Отработано дней: {stats["days"]}'
        )
        _send(vk, peer_id, text_work, exclude_actor=True)
        return

    # ─── СЕМЬЯ ──────────────────────────────────────────
    if command == 'семья' or command.startswith('семья '):
        rest = command[len('семья'):].strip() if command != 'семья' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target):
            _send(vk, peer_id, 'Пользователь не найден.', exclude_actor=True)
            return
        stats = get_family_stats(target)

        def _fmt_users(ids):
            if not ids:
                return 'Нет'
            return ', '.join(_user_link(vk, uid) for uid in ids)

        partner_line = _user_link(vk, stats['partner']) if stats['partner'] else 'Нет'
        days_line = str(stats['days']) if stats['days'] is not None else '—'

        text_family = (
            f'Статистика семьи {_user_link(vk, target)}\n'
            f'Партнёр: {partner_line}\n'
            f'Дней в отношениях: {days_line}\n'
            f'Дети: {_fmt_users(stats["children"])}\n'
            f'Родители: {_fmt_users(stats["parents"])}'
        )
        _send(vk, peer_id, text_family, exclude_actor=True)
        return

    # ─── ОТНОШЕНИЯ ──────────────────────────────────────
    if command.startswith('начать отношения '):
        target = _target(command[len('начать отношения '):])
        ok, msg = start_relationship(user_id, target, vk)
        if ok:
            from keyboards import relationship_proposal_keyboard
            _send(vk, peer_id, msg, relationship_proposal_keyboard())
        else:
            _send(vk, peer_id, msg)
        return

    if command == 'расстаться':
        _send(vk, peer_id, end_relationship(user_id))
        return

    if command == 'поцеловаться':
        import random
        partner = get_partner_id(user_id)
        if not partner:
            return
        from handlers.rp_handlers import RP_RESPONSES
        from relationships import get_display_name as _gdn
        other = f'[id{partner}|{_gdn(partner) or "партнёр"}]'
        _send(vk, peer_id, random.choice(RP_RESPONSES['поцеловать']).format(target=other))
        return

    if command == 'обняться':
        partner = get_partner_id(user_id)
        if not partner:
            return
        from handlers.rp_handlers import RP_RESPONSES
        import random
        from relationships import get_display_name as _gdn
        other = f'[id{partner}|{_gdn(partner) or "партнёр"}]'
        _send(vk, peer_id, random.choice(RP_RESPONSES['обнять']).format(target=other))
        return

    if command.startswith('создать брак '):
        parts = command.split(maxsplit=3)
        if len(parts) < 4:
            return
        target = _target(parts[2])
        surname = parts[3].strip()
        from relationships import propose_marriage
        ok, msg = propose_marriage(user_id, target, surname)
        if ok:
            from keyboards import marriage_proposal_keyboard
            _send(vk, peer_id,
                  f'{msg}\n\n💍 Фамилия семьи: «{surname}»\n\nСогласиться или отказаться?',
                  marriage_proposal_keyboard())
        else:
            _send(vk, peer_id, msg)
        return

    if command == 'развестись':
        _send(vk, peer_id, divorce(user_id))
        return

    for cmdname in ('усыновить', 'удочерить'):
        if command.startswith(cmdname + ' '):
            target = _target(command[len(cmdname) + 1:])
            result = adopt(user_id, target, vk)
            if isinstance(result, tuple):
                ok, msg = result
            else:
                ok, msg = True, result
            if ok:
                from keyboards import family_proposal_keyboard
                _send(vk, peer_id, msg, family_proposal_keyboard())
            else:
                _send(vk, peer_id, msg)
            return

    if command.startswith('сдать в детдом '):
        _send(vk, peer_id, relinquish(user_id, _target(command[len('сдать в детдом '):]), vk))
        return

    if command == 'уйти из семьи':
        _send(vk, peer_id, leave_family(user_id))
        return

    # ─── RP ─────────────────────────────────────────────
    rp_names = ['обнять', 'поцеловать', 'пожать руку', 'погладить', 'ущипнуть', 'укусить',
                'дать пять', 'пнуть', 'положить в дурку', 'посадить на бутылку', 'застрелить',
                'курить', 'уснуть', 'разбудить', 'накормить', 'подарить', 'пиво']
    rp_command = next((x for x in sorted(rp_names, key=len, reverse=True)
                       if command == x or command.startswith(x + ' ')), None)
    if rp_command:
        result = handle_rp_command(rp_command, user_id, peer_id, vk, text, get_user)
        if result:
            rp_text, rp_photo = result
            if rp_text:
                _send(vk, peer_id, rp_text, attachment=rp_photo)
        return

    # ─── МАГАЗИН ────────────────────────────────────────
    if command == 'магазин':
        from keyboards import SHOP_MENU
        _send(vk, peer_id, '🛒 Магазин\n\nЧто вас интересует?', SHOP_MENU, exclude_actor=True)
        return

    m = re.match(r'^(дом|машина|телефон)\s+(\d+)$', command)
    if m:
        category = {'дом': 'housing', 'машина': 'car', 'телефон': 'phone'}[m.group(1)]
        idx = int(m.group(2)) - 1
        items = get_items(category)
        if not 0 <= idx < len(items):
            return
        item = items[idx]
        ok, msg = buy_property(user_id, category, item[0])
        _send(vk, peer_id, msg)
        return

    m = re.match(r'^продать\s+(дом|машина|телефон)$', command)
    if m:
        category = {'дом': 'housing', 'машина': 'car', 'телефон': 'phone'}[m.group(1)]
        current = get_property_value(user_id, category)
        if current == 'Отсутствует':
            return
        items = {x[0]: x[1] for x in get_items(category)}
        refund = items.get(current, 0) // 2
        with db_cursor(True) as (_, c):
            field = {'housing': 'housing', 'car': 'car', 'phone': 'phone'}[category]
            c.execute(f"UPDATE users SET {field}='Отсутствует',coins=coins+? WHERE user_id=?", (refund, user_id))
        _send(vk, peer_id, f'Имущество продано. Получено: {refund:,} 🪙.')
        return

    # ─── РАБОТА (действия) ──────────────────────────────
    if command == 'работать':
        text, promoted_text = work(user_id)
        _send(vk, peer_id, text)
        if promoted_text:
            _send(vk, peer_id, promoted_text)
        return

    if command == 'устроиться':
        from keyboards import profession_keyboard
        _send(vk, peer_id, '💼 Выберите профессию:', profession_keyboard(), exclude_actor=True)
        return

    if command == 'уволиться':
        _send(vk, peer_id, fire(user_id))
        return

    return


# ============ ЛЛ НОРМА ============

def handle_norma(command, user_id, peer_id, vk):
    """
    лл норма + [@user] — поставить норму сдана
    лл норма - [@user] — поставить норму не сдана
    Без @user — пользователь ставит себе, но бот проверяет по факту.
    """
    parts = command.split()
    if len(parts) < 2:
        return

    sign = parts[1]
    if sign not in ('+', '-'):
        return

    actor_level = get_admin_level(user_id, peer_id)

    # Если указан @user — это админ ставит другому
    if len(parts) >= 3:
        if actor_level < 4:
            _send(vk, peer_id, 'Недостаточно прав (нужен ЗК и выше).', exclude_actor=True)
            return

        target = _target(parts[2])
        if not target:
            return
        if not get_user(target):
            _send(vk, peer_id, 'Пользователь не найден.', exclude_actor=True)
            return

        if sign == '+':
            add_admin_stat(target, 'reports', 1)
            _send(vk, peer_id, f'✅ Норма сдана для {_user_link(vk, target)}.', exclude_actor=True)
        else:
            _send(vk, peer_id, f'❌ Норма НЕ сдана для {_user_link(vk, target)}.', exclude_actor=True)
        return

    # Без @user — сам себе
    if actor_level < 2:
        _send(vk, peer_id, 'Только для администраторов (Активист и выше).', exclude_actor=True)
        return

    # Бот проверяет факт: пользователь должен был сдать норму (сообщения/добавления)
    from weekly_report import check_user_norma
    ok, reason = check_user_norma(user_id)

    if sign == '+':
        if not ok:
            _send(vk, peer_id,
                  f'❌ Ты не можешь поставить себе «+»: {reason}',
                  exclude_actor=True)
            return
        add_admin_stat(user_id, 'reports', 1)
        _send(vk, peer_id, f'✅ Норма сдана для {_user_link(vk, user_id)}.', exclude_actor=True)
    else:
        _send(vk, peer_id, f'❌ Норма НЕ сдана для {_user_link(vk, user_id)}.', exclude_actor=True)