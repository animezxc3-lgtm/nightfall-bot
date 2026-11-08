import json, re
from datetime import datetime, timedelta
from config import CREATOR_ID, ALLOWED_IN_DM, MAIN_CHATS, ANARCHY_CHAT, CASINO_CHAT
from database import (
    get_user, create_user, user_exists, transfer_coins, debit_gems, 
    update_coins, update_gems, update_power, clear_warnings, set_nickname, get_owner, 
    get_twinks, remove_twink, add_twink, is_twink, 
    get_feature, get_application, delete_application, 
    upsert_application, set_gif_link, set_status, 
    get_property_value, db_cursor, set_salary_multiplier, 
    increase_salary_multiplier, get_salary_multiplier, 
    add_admin_stat, has_active_duel, create_duel, get_duel_for_opponent, delete_duel,
    get_messages_stats, get_admin_chat_stats
)
from admin_commands import handle_admin_command, get_admin_level, get_display_admin_level
from games import casino
from wheel import spin_wheel, draw_wheel
from vk_upload import upload_photo
from jobs.work_handler import work, hire, fire, job_stats
from handlers.user_handlers import get_profile, get_profile_data, get_balance, get_activity, is_admin
from handlers.rp_handlers import handle_rp_command
from relationships import (
    parse_target_id, start_relationship, end_relationship, divorce,
    propose_marriage, adopt, relinquish, leave_family, get_partner_id,
    get_display_name, get_family_stats,
)
from property_shop import buy_property, get_items
from response_context import set_user, get_user_id, get_exclude_actor
from jobs.professions import PROFESSIONS
from tasks import (format_tasks, format_assigned_task, event as task_event, notify_task_rewards,
                   get_extra_task_slots, buy_extra_task_slot)

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
    if attachment: args['attachment'] = attachment
    args['disable_mentions'] = True
    vk.messages.send(**args)

def _record_task_event(vk, peer_id, user_id, kind, amount=1, data=None):
    try:
        awarded = task_event(user_id, kind, amount=amount, data=data, peer_id=peer_id)
        notify_task_rewards(vk, peer_id, user_id, awarded)
    except Exception as e:
        print(f'⚠️ Ошибка обновления задания ({kind}, user={user_id}): {e}')

def _target(s): return parse_target_id(s)

def get_display_name_safe(uid, fallback):
    return get_display_name(uid) or fallback

# ============ VIP МАГАЗИН (ТОЛЬКО ЛС) ============

VIP_PRICES = {
    1: 100, 2: 100, 3: 65, 4: 100, 5: 100, 6: 100,
}

def vip_shop_text():
    return (
        '💎 VIP-магазин\n\n'
        '1. GIF/видео в профиль — 100 💎\n'
        '2. Статус в профиле — 100 💎\n'
        '3. Снять предупреждение — 65 💎\n'
        '4. Повысить множитель зарплаты — 100 💎\n'
        '5. Второй слот ежедневных заданий навсегда — 100 💎\n'
        '6. Третий слот ежедневных заданий навсегда — 100 💎\n\n'
        'Покупка: `лл вип <номер>` (только в ЛС бота)'
    )

def _check_salary_mult_cap(user_id):
    return get_salary_multiplier(user_id) >= 7.0

def handle_command(command, user_id, peer_id, vk, text):
    raw_command = command.strip()
    if text and text.lower().startswith('лл '):
        raw_command = text[3:].strip()
    command = raw_command.lower()
    if not command: return
    
    list_commands = {'меню', 'магазин', 'беседы', 'админы', 'твинки'}
    set_user(user_id, command.split()[0] in list_commands)
    is_chat = peer_id > 2000000000
    if not is_chat: return

    # Команды создателя
    resource_commands = {'монеты': ('coins', 'монет'), 'гиас': ('power', 'силы Гиаса'), 'камни': ('soul_gems', 'камней души')}
    parts = command.split()
    if len(parts) >= 2 and parts[0] in ('выдать', 'отобрать'):
        if user_id != CREATOR_ID: return
        resource = parts[1]
        if resource in resource_commands:
            if len(parts) != 4: return
            target_id = _target(parts[2])
            try: amount = int(parts[3])
            except (TypeError, ValueError): amount = 0
            if not target_id or not get_user(target_id) or amount <= 0: return
            field, resource_label = resource_commands[resource]
            if parts[0] == 'выдать':
                if field == 'coins': update_coins(target_id, amount)
                elif field == 'power': update_power(target_id, amount)
                else: update_gems(target_id, amount)
                action = 'выдал'
            else:
                with db_cursor(True) as (_, cursor):
                    cursor.execute(f"UPDATE users SET {field}=COALESCE({field}, 0)-? WHERE user_id=? AND COALESCE({field}, 0)>=?", (amount, target_id, amount))
                    if cursor.rowcount != 1: return
                action = 'отобрал'
            _send(vk, peer_id, f'Создатель {action} у {_user_link(vk, target_id)} {amount} {resource_label}.', exclude_actor=True)
            return

    if handle_admin_command(command, user_id, peer_id, vk, text):
        return

    # ─── МЕНЮ ────────────────────────────────────────────
    if command == 'меню':
        from keyboards import menu_keyboard
        is_adm = get_admin_level(user_id, peer_id) >= 1
        _send(vk, peer_id, '📖 Меню Lelouch Bot\n\nВыбери нужный раздел ниже.', menu_keyboard(is_adm, user_id == CREATOR_ID), exclude_actor=True)
        return

    # VIP-магазин В БЕСЕДЕ ЗАПРЕЩЕН
    if command == 'вип магазин' or command.startswith('купить ') or command.startswith('вип '):
        _send(vk, peer_id, 'VIP-магазин доступен только в личных сообщениях бота!', exclude_actor=True)
        return

    # ─── ПРОФИЛЬ ────────────────────────────────────────
    if command == 'профиль' or command.startswith('профиль '):
        rest = command[len('профиль'):].strip() if command != 'профиль' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target): return
        profile_text, profile_attachment = get_profile_data(target, peer_id)
        _send(vk, peer_id, profile_text, attachment=profile_attachment, exclude_actor=True)
        _record_task_event(vk, peer_id, user_id, 'profile' if target == user_id else 'other_profile')
        return

    if command == 'баланс' or command.startswith('баланс '):
        rest = command[len('баланс'):].strip() if command != 'баланс' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target): return
        msg = f'Баланс {_user_link(vk, target)}:\n' + get_balance(target, vk).split('\n', 1)[1]
        _send(vk, peer_id, msg, exclude_actor=True)
        if target == user_id: _record_task_event(vk, peer_id, user_id, 'balance')
        return

    # ЗАДАНИЯ ОТКЛЮЧЕНЫ
    # if command == 'задание': _send(vk, peer_id, format_assigned_task(user_id, peer_id), exclude_actor=True); return
    # if command == 'задания': _send(vk, peer_id, format_tasks(user_id, peer_id), exclude_actor=True); return

    if command.startswith('ник '):
        nick = raw_command[4:].strip()
        if not 1 <= len(nick) <= 30: return
        set_nickname(user_id, nick)
        _send(vk, peer_id, f'Ваш новый никнейм: [id{user_id}|{nick}]', exclude_actor=True)
        return

    if command == 'активность' or command.startswith('активность '):
        rest = command[len('активность'):].strip() if command != 'активность' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target): return
        msg = f'Статистика сообщений {_user_link(vk, target)}:\n' + get_activity(target).split('\n', 1)[1]
        _send(vk, peer_id, msg)
        if target == user_id: _record_task_event(vk, peer_id, user_id, 'activity')
        return
    
    # ─── ТВИНКИ (СО СТАТИСТИКОЙ) ──────────────────────────
    if command == 'твинк' or command.startswith('твинк '):
        parts = command.split(maxsplit=2)
        if len(parts) >= 2 and parts[1] == 'убрать':
            if len(parts) < 3: return
            target = _target(parts[2])
            if not target or not is_twink(target): return
            owner = get_owner(target)
            actor_level = get_admin_level(user_id, peer_id)
            if user_id != owner and actor_level < 5: return
            remove_twink(target)
            _send(vk, peer_id, 'Твинк удален.', exclude_actor=True)
            return
        if len(parts) < 2: return
        twink_id = _target(parts[1])
        if not twink_id or twink_id == user_id or not get_user(twink_id): return
        if is_twink(twink_id): return
        add_twink(user_id, twink_id)
        _send(vk, peer_id, 'Твинк добавлен.', exclude_actor=True)
        return

    if command == 'твинки' or command.startswith('твинки '):
        parts = command.split(maxsplit=1)
        target = user_id if len(parts) == 1 else _target(parts[1])
        if not target: return
        owner = get_owner(target) or target
        twinks = get_twinks(owner)
        
        header = f'👥 Твинки {_user_link(vk, owner)}:'
        if not twinks: 
            _send(vk, peer_id, header + '\n-нет', exclude_actor=True)
            return
            
        lines = [header]
        for tid in twinks:
            # Статистика сообщений
            msg_stats = get_messages_stats(tid)
            
            # Статистика приглашений (за все время, за день, за неделю, за месяц)
            with db_cursor() as (_, c):
                today = datetime.now().strftime("%Y-%m-%d")
                week = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
                month = datetime.now().replace(day=1).strftime("%Y-%m-%d")
                
                inv_total = c.execute("SELECT COUNT(*) FROM chat_members WHERE invited_by=?", (tid,)).fetchone()[0]
                inv_today = c.execute("SELECT COUNT(*) FROM chat_members WHERE invited_by=? AND substr(first_join_at,1,10)=?", (tid, today)).fetchone()[0]
                inv_week = c.execute("SELECT COUNT(*) FROM chat_members WHERE invited_by=? AND substr(first_join_at,1,10)>=?", (tid, week)).fetchone()[0]
                inv_month = c.execute("SELECT COUNT(*) FROM chat_members WHERE invited_by=? AND substr(first_join_at,1,10)>=?", (tid, month)).fetchone()[0]

            lines.append(f'• {_user_link(vk, tid)}')
            lines.append(f'  💬 Сообщения:')
            lines.append(f'    Сегодня: {msg_stats["today"]} | За неделю: {msg_stats["week"]} | За месяц: {msg_stats["month"]} | Всего: {msg_stats["total"]}')
            lines.append(f'  👥 Приглашено:')
            lines.append(f'    Сегодня: {inv_today} | За неделю: {inv_week} | За месяц: {inv_month} | Всего: {inv_total}')
            lines.append('')
            
        if lines[-1] == '': lines.pop()
        _send(vk, peer_id, '\n'.join(lines), exclude_actor=True)
        return

    # ─── ЗАЯВКА ─────────────────────────────────────────
    if command == 'заявка':
        _send(vk, peer_id, '📩 Заявка подаётся в личные сообщения бота.\n\nНапиши боту в ЛС: `лл заявка`.')
        return

    # ─── ЗАКРЕПЫ ────────────────────────────────────────
    if command == 'установить закреп':
        if get_admin_level(user_id, peer_id) < 4: return
        from pin_manager import update_pin_in_chat
        update_pin_in_chat(vk, peer_id, notify=True); return

    if command == 'обновить закрепы':
        if user_id != CREATOR_ID and get_admin_level(user_id, peer_id) < 7: return
        from pin_manager import update_all_pins
        results = update_all_pins(vk)
        ok = len([r for r in results if r[1] in ('updated', 'created', 'recreated')])
        _send(vk, peer_id, f'Обновлено бесед: {ok} из {len(results)}.', exclude_actor=True); return

    # ─── ДУЭЛЬ ──────────────────────────────────────────
    if command.startswith('дуэль'):
        is_weekend = datetime.now().weekday() >= 5
        if peer_id != ANARCHY_CHAT and not is_weekend:
            _send(vk, peer_id, 'Дуэли в этой беседе проводятся только в субботу и воскресенье.', exclude_actor=True)
            return
        if not get_feature(peer_id, 'дуэль') and peer_id in MAIN_CHATS:
            _send(vk, peer_id, 'Дуэли в этой беседе отключены.', exclude_actor=True)
            return
            
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            _send(vk, peer_id, 'Укажи, кого вызываешь: `лл дуэль @user`', exclude_actor=True)
            return
        opponent = parse_target_id(parts[1])
        if not opponent or opponent == user_id or not get_user(opponent): return
        if has_active_duel(user_id) or has_active_duel(opponent):
            _send(vk, peer_id, 'У одного из участников уже активна дуэль.', exclude_actor=True); return

        text_msg = f'⚔️ {_user_link(vk, user_id)} вызвал на дуэль {_user_link(vk, opponent)}!\n\nСтавка: 15% от Силы Гиаса проигравшего.'
        from keyboards import duel_keyboard
        res = vk.messages.send(peer_id=peer_id, random_id=0, message=text_msg, keyboard=json.dumps(duel_keyboard(), ensure_ascii=False), disable_mentions=True)
        cmid = None
        try:
            if isinstance(res, int):
                info = vk.messages.getById(message_ids=res)
                items = info.get('items') or []
                if items: cmid = items[0].get('conversation_message_id')
        except: pass
        create_duel(user_id, opponent, peer_id, cmid)
        return

    # ─── РУЛЕТКА / КАЗИНО ───────────────────────────────
    if command.startswith('рулетка') or command.startswith('деп'):
        if peer_id not in (CASINO_CHAT,) and not get_feature(peer_id, 'казино'):
            _send(vk, peer_id, 'Казино в этой беседе запрещено.', exclude_actor=True)
            return
        
        parts = command.split()
        if len(parts) != 2: return
        try: bet = int(parts[1])
        except ValueError: return

        if command.startswith('деп'):
            if bet <= 0: return
            result, mult, err = casino(user_id, bet)
            if err: _send(vk, peer_id, err, exclude_actor=True); return
            if mult == 0: _send(vk, peer_id, 'проиграл всю ставку')
            else: _send(vk, peer_id, f'получил модификатор х{mult}.\nВыигрыш составляет: {result:,}')
            _record_task_event(vk, peer_id, user_id, 'casino')
            return

        if command.startswith('рулетка'):
            if bet < 1000:
                _send(vk, peer_id, 'Минимальная ставка: 1 000 монет.', exclude_actor=True); return
            user = get_user(user_id)
            if bet > user[5]:
                _send(vk, peer_id, 'Недостаточно монет.', exclude_actor=True); return

            idx, number, color = spin_wheel()
            color_ru = {'red': 'Красное', 'black': 'Чёрное', 'green': 'Зелёное'}[color]
            mult = 0 if color == 'black' else (2 if color == 'red' else 5)
            win_amount = bet * mult
            update_coins(user_id, win_amount - bet)
            try:
                photo_path = draw_wheel(idx)
                attachment = upload_photo(vk, photo_path, peer_id)
            except Exception as e:
                print(f'⚠️ {e}'); attachment = None
            text_roulette = f'{_user_link(vk, user_id)}\nВыпало: {number} — {color_ru}\nМножитель: х{mult}\nВыигрыш: {win_amount:,}'
            _send(vk, peer_id, text_roulette, attachment=attachment, exclude_actor=True)
            _record_task_event(vk, peer_id, user_id, 'casino')
            return

    # ─── ПЕРЕВОД МОНЕТ ──────────────────────────────────
    if command == 'передать' or command.startswith('передать '):
        remainder = raw_command[len('передать'):].strip()
        target = _target(remainder)
        if not target: return
        amount_text = re.sub(r'\[id\d+\|[^\]]+\]', ' ', remainder)
        amount_text = re.sub(r'https?://vk\.(?:com|ru)/id\d+', ' ', amount_text, flags=re.I)
        amount_text = re.sub(r'@id\d+', ' ', amount_text, flags=re.I)
        amount_text = re.sub(rf'\b{target}\b', ' ', amount_text)
        amount_match = re.search(r'(?<!\w)\d+(?!\w)', amount_text)
        try: amount = int(amount_match.group(0)) if amount_match else 0
        except ValueError: amount = 0
        if amount <= 0 or target == user_id or not get_user(target): return
        if not transfer_coins(user_id, target, amount):
            _send(vk, peer_id, 'У вас недостаточно монет.', exclude_actor=True); return
        _send(vk, peer_id, f'Передано {amount:,} 🪙 пользователю {_user_link(vk, target)}.')
        _record_task_event(vk, peer_id, user_id, 'transfer', amount=1, data={'transfer_amount': amount})
        return

    # ─── РАБОТА (статистика) ────────────────────────────
    if command == 'работа' or command.startswith('работа '):
        rest = command[len('работа'):].strip() if command != 'работа' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target): return
        stats = job_stats(target, viewer_id=user_id)
        if stats is None: return
        if isinstance(stats, str): _send(vk, peer_id, stats, exclude_actor=True); return
        text_work = (
            f'Статистика работы {_user_link(vk, target)}\nРабота: {stats["job_name"]}\nДолжность: {stats["level_name"]}\n'
            f'Зарплата: {stats["salary"]:,} 🪙 (×{stats["multiplier"]})\n⚡ Сила Гиаса: +{stats["power_per_work"]}\nОтработано дней: {stats["days"]}'
        )
        _send(vk, peer_id, text_work, exclude_actor=True)
        return

    # ─── СЕМЬЯ ──────────────────────────────────────────
    if command == 'семья' or command.startswith('семья '):
        rest = command[len('семья'):].strip() if command != 'семья' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target): return
        stats = get_family_stats(target)
        def _fmt(ids): return 'Нет' if not ids else ', '.join(_user_link(vk, u) for u in ids)
        text_family = (
            f'Статистика семьи {_user_link(vk, target)}\nПартнёр: {_user_link(vk, stats["partner"]) if stats["partner"] else "Нет"}\n'
            f'Дней в отношениях: {stats["days"] if stats["days"] is not None else "—"}\nДети: {_fmt(stats["children"])}\nРодители: {_fmt(stats["parents"])}'
        )
        _send(vk, peer_id, text_family, exclude_actor=True)
        return

               # ─── ОТНОШЕНИЯ (АЛИАСЫ) ─────────────────────────────
    if command.startswith('встречаться '):
        target = _target(command[len('встречаться '):])
        if not target or target == user_id: return
        
        actor_name = get_display_name(user_id) or 'Пользователь'
        actor_link = f'[id{user_id}|{actor_name}]'
        target_link = _user_link(vk, target)
        
        result = start_relationship(user_id, target, vk)
        if isinstance(result, tuple): ok, msg = result
        else: ok, msg = True, str(result)
        
        if ok:
            from keyboards import relationship_proposal_keyboard
            custom_msg = f'❤️ {actor_link} предлагает {target_link} начать отношения!'
            _send(vk, peer_id, custom_msg, relationship_proposal_keyboard())
        else: 
            _send(vk, peer_id, msg)
        return

    if command == 'семья' or command.startswith('семья '):
        rest = command[len('семья'):].strip() if command != 'семья' else ''
        target = _target(rest) if rest else user_id
        if not target or not get_user(target): return
        
        stats = get_family_stats(target)
        
        def _fmt_users(ids):
            if not ids: return 'Нет'
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

    if command.startswith('выгнать из семьи '):
        target = _target(command[len('выгнать из семьи '):])
        _send(vk, peer_id, relinquish(user_id, target, vk))
        return

    if command.startswith('отправить в детдом '):
        target = _target(command[len('отправить в детдом '):])
        _send(vk, peer_id, relinquish(user_id, target, vk))
        return

    if command == 'развод':
        _send(vk, peer_id, divorce(user_id))
        return

    if command == 'покинуть семью':
        _send(vk, peer_id, leave_family(user_id))
        return

    if command == 'цем':
        partner = get_partner_id(user_id)
        if not partner: return
        from handlers.rp_handlers import RP_RESPONSES
        import random
        other = f'[id{partner}|{get_display_name(partner) or "партнёр"}]'
        _send(vk, peer_id, random.choice(RP_RESPONSES['поцеловать']).format(target=other))
        return

    if command.startswith('создать брак '):
        raw_remainder = raw_command[len('создать брак '):].strip()
        target = _target(raw_remainder)
        if not target: return
        surname = re.sub(r'\[id\d+\|[^\]]+\]', ' ', raw_remainder)
        surname = re.sub(r'https?://vk\.(?:com|ru)/id\d+', ' ', surname, flags=re.I)
        surname = re.sub(r'@id\d+', ' ', surname, flags=re.I)
        surname = re.sub(rf'\b{target}\b', ' ', surname)
        surname = ' '.join(surname.split())
        if not surname or len(surname) > 30 or target == user_id: return
        
        result = propose_marriage(user_id, target, surname)
        if isinstance(result, tuple): ok, msg = result
        else: ok, msg = True, str(result)
        
        if ok:
            from keyboards import marriage_proposal_keyboard
            actor_name = get_display_name(user_id) or 'Пользователь'
            actor_link = f'[id{user_id}|{actor_name}]'
            target_link = _user_link(vk, target)
            
            text_msg = (
                f'💍 {actor_link} делает {target_link} предложение руки и сердца!\n'
                f'Предлагаемая фамилия: {surname}'
            )
            _send(vk, peer_id, text_msg, marriage_proposal_keyboard())
        else: 
            _send(vk, peer_id, msg)
        return
        
    if command == 'расстаться':
        _send(vk, peer_id, end_relationship(user_id))
        return

    # ─── RP ─────────────────────────────────────────────
    rp_names = ['обнять', 'поцеловать', 'пожать руку', 'погладить', 'ущипнуть', 'укусить', 'дать пять', 'пнуть', 'положить в дурку', 'посадить на бутылку', 'застрелить', 'курить', 'уснуть', 'разбудить', 'накормить', 'подарить', 'пиво', 'подрочить', 'секс', 'футджоб', 'принять душ', 'минет', 'куни', '69']
    rp_command = next((x for x in sorted(rp_names, key=len, reverse=True) if command == x or command.startswith(x + ' ')), None)
    if rp_command:
        result = handle_rp_command(rp_command, user_id, peer_id, vk, text, get_user)
        if result:
            rp_text, rp_photo = result
            if rp_text:
                _send(vk, peer_id, rp_text, attachment=rp_photo)
                _record_task_event(vk, peer_id, user_id, 'rp')
                rp_target = _target(text)
                if rp_target and rp_target == get_partner_id(user_id):
                    _record_task_event(vk, peer_id, user_id, 'partner_rp')
        return

    # ─── МАГАЗИН ────────────────────────────────────────
    if command == 'магазин':
        from keyboards import get_shop_menu
        is_adm = get_admin_level(user_id, peer_id) >= 1
        _send(vk, peer_id, '🛒 Магазин\n\nЧто вас интересует?', get_shop_menu(is_adm), exclude_actor=True)
        _record_task_event(vk, peer_id, user_id, 'shop')
        return

    m = re.match(r'^(дом|машина|телефон)\s+(\d+)$', command)
    if m:
        category = {'дом': 'housing', 'машина': 'car', 'телефон': 'phone'}[m.group(1)]
        idx = int(m.group(2)) - 1
        items = get_items(category)
        if not 0 <= idx < len(items): return
        item = items[idx]
        ok, msg = buy_property(user_id, category, item[0])
        _send(vk, peer_id, msg)
        if ok: _record_task_event(vk, peer_id, user_id, 'property')
        return

    m = re.match(r'^продать\s+(дом|машина|телефон)$', command)
    if m:
        category = {'дом': 'housing', 'машина': 'car', 'телефон': 'phone'}[m.group(1)]
        current = get_property_value(user_id, category)
        if current == 'Отсутствует': return
        items = {x[0]: x[1] for x in get_items(category)}
        refund = items.get(current, 0) // 2
        with db_cursor(True) as (_, c):
            field = {'housing': 'housing', 'car': 'car', 'phone': 'phone'}[category]
            c.execute(f"UPDATE users SET {field}='Отсутствует',coins=coins+? WHERE user_id=?", (refund, user_id))
        _send(vk, peer_id, f'Имущество продано. Получено: {refund:,} 🪙.')
        return

    # ─── РАБОТА (действия) ──────────────────────────────
    if command == 'работать':
        text_work, promoted_text = work(user_id)
        _send(vk, peer_id, text_work)
        if text_work == 'отработал рабочий день.':
            _record_task_event(vk, peer_id, user_id, 'work')
        if promoted_text: _send(vk, peer_id, promoted_text)
        return

    if command == 'устроиться':
        from keyboards import profession_keyboard
        _send(vk, peer_id, '💼 Выберите профессию:', profession_keyboard(), exclude_actor=True)
        return

    if command == 'уволиться': _send(vk, peer_id, fire(user_id)); return

    return

# ============ ЛЛ НОРМА ============
def handle_norma(command, user_id, peer_id, vk):
    parts = command.strip().split()
    if not parts or parts[0].lower() != 'норма': return

    sign = None
    target_text = None
    if len(parts) >= 3 and parts[1] in ('+', '-'):
        sign, target_text = parts[1], ' '.join(parts[2:])
    elif len(parts) >= 3 and parts[-1] in ('+', '-'):
        sign, target_text = parts[-1], ' '.join(parts[1:-1])

    if not sign or not target_text: return
    target = _target(target_text)
    if not target or target == user_id: return

    actor_level = get_admin_level(user_id, peer_id)
    if actor_level < 2:
        _send(vk, peer_id, 'Недостаточно прав. Норма доступна Активисту и выше.', exclude_actor=True)
        return
    if not get_user(target): return

    if get_display_admin_level(target) < 2:
        _send(vk, peer_id, f'{_user_link(vk, target)} не является администратором (минимум Активист).', exclude_actor=True)
        return

    if sign == '+':
        add_admin_stat(target, 'reports', 1)
        _send(vk, peer_id, f'Норма сдана для {_user_link(vk, target)}.', exclude_actor=True)
    else:
        _send(vk, peer_id, f'Норма НЕ сдана для {_user_link(vk, target)}.', exclude_actor=True)