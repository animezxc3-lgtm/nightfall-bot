import json,re
from config import CREATOR_ID,ALLOWED_IN_DM
from database import *
from admin_commands import handle_admin_command
from games import casino
from jobs.work_handler import work,hire,fire
from handlers.user_handlers import get_profile,get_balance,set_nickname_command,get_activity
from handlers.rp_handlers import handle_rp_command
from relationships import parse_target_id,start_relationship,end_relationship,divorce,adopt,relinquish,leave_family,get_partner_id,get_display_name
from property_shop import buy_property,get_items
from response_context import set_user, get_user_id, get_exclude_actor

def _user_link(vk, user_id, fallback='Пользователь'):
    try:
        info=vk.users.get(user_ids=user_id)[0]
        label=get_display_name_safe(user_id, info.get('first_name','Пользователь'))
    except Exception:
        label=get_display_name_safe(user_id, fallback)
    return f'[id{user_id}|{label}]'

def _send(vk,peer_id,msg,keyboard=None,attachment=None,exclude_actor=False):
    actor=get_user_id()
    if actor and not exclude_actor and not get_exclude_actor():
        msg=f'{_user_link(vk,actor)} {msg}'
    args={'peer_id':peer_id,'random_id':0,'message':msg}
    if keyboard is not None: args['keyboard']=json.dumps(keyboard,ensure_ascii=False)
    if attachment: args['attachment']=attachment
    args['disable_mentions'] = True
    vk.messages.send(**args)

def _target(s): return parse_target_id(s)

def get_display_name_safe(uid, fallback):
    from relationships import get_display_name
    return get_display_name(uid) or fallback

def handle_command(command,user_id,peer_id,vk,text):
    list_commands={'меню','магазин','беседы','админы','банстат','твинки'}
    set_user(user_id, command.split()[0] in list_commands)
    is_chat=peer_id>2000000000
    if not is_chat:
        return

    if handle_admin_command(command,user_id,peer_id,vk,text): return

    if command == 'меню':
        from keyboards import menu_keyboard
        from admin_commands import get_admin_level
        is_admin = get_admin_level(user_id, peer_id) >= 1
        _send(vk, peer_id, '📖 Меню Lelouch Bot\n\nВыбери нужный раздел ниже. При нажатии текст этого сообщения будет заменён на выбранный раздел.', menu_keyboard(is_admin), exclude_actor=True)
        return

    if command == 'профиль' or command.startswith('профиль '):
        target = _target(command[len('профиль'):].strip()) if command != 'профиль' else user_id
        if not target or not get_user(target):
            _send(vk, peer_id, '❌ Пользователь не найден.', exclude_actor=True)
            return
        _send(vk, peer_id, get_profile(target, peer_id), exclude_actor=True)
        return
    if command == 'баланс' or command.startswith('баланс '):
        target = _target(command[len('баланс'):].strip()) if command != 'баланс' else user_id
        if not target or not get_user(target):
            _send(vk, peer_id, '❌ Пользователь не найден.', exclude_actor=True)
            return
        _send(vk, peer_id, get_balance(target, vk), exclude_actor=True)
        return
    if command.startswith('ник '):
        nick = command[4:].strip()
        if not 1 <= len(nick) <= 30:
            _send(vk, peer_id, '❌ Ник должен быть от 1 до 30 символов.', exclude_actor=True)
            return
        set_nickname(user_id, nick)
        link = f'[id{user_id}|{nick}]'
        _send(vk, peer_id, f'Ваш новый никнейм: {link}', exclude_actor=True)
        return
    if command == 'активность' or command.startswith('активность '):
        target = _target(command[len('активность'):].strip()) if command != 'активность' else user_id
        if not target or not get_user(target):
            _send(vk, peer_id, '❌ Пользователь не найден.')
            return
        _send(vk, peer_id, get_activity(target))
        return

    # === ТВИНКИ ===
    if command == 'твинк' or command.startswith('твинк '):
        parts = command.split(maxsplit=2)
        if len(parts) >= 2 and parts[1] == 'убрать':
            if len(parts) < 3:
                _send(vk, peer_id, '❌ Формат: `лл твинк убрать @user`', exclude_actor=True)
                return
            target = _target(parts[2])
            if not target:
                _send(vk, peer_id, '❌ Укажи пользователя.', exclude_actor=True)
                return
            if not is_twink(target):
                _send(vk, peer_id, '❌ Этот пользователь не является твинком.', exclude_actor=True)
                return
            owner = get_owner(target)
            actor_level = __import__('admin_commands').get_admin_level(user_id, peer_id)
            if user_id != owner and actor_level < 5:
                _send(vk, peer_id, '❌ Убирать чужих твинков могут только Вершитель правосудия и выше.', exclude_actor=True)
                return
            remove_twink(target)
            _send(vk, peer_id, f'✅ {_user_link(vk, target)} больше не твинк.')
            return

        if len(parts) < 2:
            _send(vk, peer_id, 'Используй @user для того, чтобы привязать твинк-аккаунт.', exclude_actor=True)
            return
        twink_id = _target(parts[1])
        if not twink_id:
            _send(vk, peer_id, '❌ Укажи пользователя.', exclude_actor=True)
            return
        if twink_id == user_id:
            _send(vk, peer_id, '❌ Нельзя привязать себя к себе.', exclude_actor=True)
            return
        if not get_user(twink_id):
            try:
                info = vk.users.get(user_ids=twink_id)[0]
                name = f"{info.get('first_name','')} {info.get('last_name','')}".strip() or 'Пользователь'
                create_user(twink_id, name)
            except Exception as e:
                print(f'⚠️ Не удалось создать профиль твинка: {e}')
        if is_twink(twink_id):
            existing_owner = get_owner(twink_id)
            _send(vk, peer_id, f'❌ Этот аккаунт уже привязан как твинк к [id{existing_owner}|владельцу].', exclude_actor=True)
            return
        ok = add_twink(user_id, twink_id)
        if ok:
            _send(vk, peer_id, f'✅ {_user_link(vk, twink_id)} привязан как твой твинк.')
        else:
            _send(vk, peer_id, '❌ Не удалось привязать твинк.', exclude_actor=True)
        return

    if command == 'твинки' or command.startswith('твинки '):
        parts = command.split(maxsplit=1)
        if len(parts) == 1:
            target = user_id
        else:
            t = _target(parts[1])
            if not t:
                _send(vk, peer_id, '❌ Укажи пользователя.', exclude_actor=True)
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

    # === ЗАЯВКА (в беседе) ===
    if command == 'заявка':
        _send(vk, peer_id, '📩 Заявка подаётся в личные сообщения бота.\n\nНапиши боту в ЛС: `лл заявка`.')
        return

    # === ЗАКРЕПЫ ===
    if command == 'установить закреп':
        from admin_commands import get_admin_level
        if get_admin_level(user_id, peer_id) < 4:
            _send(vk, peer_id, '❌ Недостаточно прав. Требуется уровень 4 — Главный администратор.', exclude_actor=True)
            return
        from pin_manager import update_pin_in_chat
        ok, status = update_pin_in_chat(vk, peer_id, notify=True)
        if status == 'created':
            _send(vk, peer_id, '📌 Сообщение закрепа отправлено. Закрепи его вручную через VK. Дальше я буду обновлять его сам.')
        elif status == 'updated':
            _send(vk, peer_id, '✅ Закреп обновлён.')
        elif status == 'recreated':
            _send(vk, peer_id, '⚠️ Старое сообщение закрепа не найдено. Отправлено новое — закрепи его вручную.')
        return

    if command == 'обновить закрепы':
        if user_id != CREATOR_ID:
            from admin_commands import get_admin_level
            if get_admin_level(user_id, peer_id) < 6:
                _send(vk, peer_id, '❌ Только Лелуш ви Британия может обновлять все закрепы.', exclude_actor=True)
                return
        from pin_manager import update_all_pins
        _send(vk, peer_id, '⏳ Начинаю обновление закрепов...')
        results = update_all_pins(vk)
        ok = len([r for r in results if r[1] in ('updated','created','recreated')])
        _send(vk, peer_id, f'✅ Обновлено бесед: {ok} из {len(results)}.', exclude_actor=True)
        return

    # === ДУЭЛЬ ===
    if command.startswith('дуэль'):
        if not get_feature(peer_id, 'дуэль'):
            _send(vk, peer_id, '❌ Дуэли в этой беседе отключены.', exclude_actor=True)
            return
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            _send(vk, peer_id, '❌ Формат: `лл дуэль @user`', exclude_actor=True)
            return
        opponent = parse_target_id(parts[1])
        if not opponent:
            _send(vk, peer_id, '❌ Укажи пользователя для дуэли.', exclude_actor=True)
            return
        if opponent == user_id:
            _send(vk, peer_id, '❌ Нельзя вызвать на дуэль самого себя.', exclude_actor=True)
            return
        if not get_user(opponent):
            _send(vk, peer_id, '❌ У пользователя нет профиля.', exclude_actor=True)
            return
        if has_active_duel(user_id) or has_active_duel(opponent):
            _send(vk, peer_id, '❌ У одного из вас уже есть активная дуэль.', exclude_actor=True)
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

    # === КАЗИНО ===
    if command.startswith('деп'):
        if not get_feature(peer_id, 'казино'):
            _send(vk, peer_id, '❌ Казино в этой беседе отключено.', exclude_actor=True)
            return
        parts = command.split()
        if len(parts) != 2:
            _send(vk, peer_id, '❌ Формат: `лл деп <ставка>`', exclude_actor=True)
            return
        try:
            bet = int(parts[1])
        except ValueError:
            bet = 0
        if bet <= 0:
            _send(vk, peer_id, '❌ Ставка должна быть положительным числом.', exclude_actor=True)
            return
        result, mult, err = casino(user_id, bet)
        if err:
            _send(vk, peer_id, err, exclude_actor=True)
            return
        if mult == 0:
            _send(vk, peer_id, 'проиграл всю ставку')
        else:
            _send(vk, peer_id, f'получил модификатор х{mult}.\nВыигрыш составляет: {result:,}')
        return

    if command=='передать' or command.startswith('передать '):
        parts=command.split(maxsplit=2)
        if len(parts)!=3: _send(vk,peer_id,'❌ Формат: `лл передать @user сумма`'); return
        target=_target(parts[1])
        try: amount=int(parts[2])
        except ValueError: amount=0
        if not target or amount<=0: _send(vk,peer_id,'❌ Укажи корректного пользователя и положительную сумму.'); return
        if target==user_id: _send(vk,peer_id,'❌ Нельзя передать монеты самому себе.'); return
        if not get_user(target): _send(vk,peer_id,'❌ У пользователя нет профиля.'); return
        if not transfer_coins(user_id,target,amount): _send(vk,peer_id,'❌ Недостаточно монет.'); return
        _send(vk,peer_id,f'✅ Передано {amount:,} 🪙 пользователю {_user_link(vk,target)}.'); return

    # Relations
    if command.startswith('начать отношения '):
        target=_target(command[len('начать отношения '):]); ok,msg=start_relationship(user_id,target,vk)
        if ok:
            from keyboards import relationship_proposal_keyboard
            _send(vk,peer_id,msg,relationship_proposal_keyboard())
        else:_send(vk,peer_id,msg)
        return
    if command == 'расстаться': _send(vk,peer_id,end_relationship(user_id)); return
    if command == 'поцеловаться':
        import random
        partner=get_partner_id(user_id)
        if not partner: _send(vk,peer_id,'❌ У тебя нет партнёра.'); return
        from handlers.rp_handlers import RP_RESPONSES
        from relationships import get_display_name as _gdn
        other=f'[id{partner}|{_gdn(partner) or "партнёр"}]'
        _send(vk,peer_id,random.choice(RP_RESPONSES['поцеловать']).format(target=other)); return
    if command == 'обняться':
        partner=get_partner_id(user_id)
        if not partner: _send(vk,peer_id,'❌ У тебя нет партнёра.'); return
        from handlers.rp_handlers import RP_RESPONSES
        import random
        from relationships import get_display_name as _gdn
        other=f'[id{partner}|{_gdn(partner) or "партнёр"}]'
        _send(vk,peer_id,random.choice(RP_RESPONSES['обнять']).format(target=other)); return
    if command.startswith('создать брак '):
        parts=command.split(maxsplit=3)
        if len(parts)<4: _send(vk,peer_id,'❌ Формат: `лл создать брак @user фамилия`'); return
        target=_target(parts[2]); surname=parts[3].strip()
        from relationships import propose_marriage
        ok,msg=propose_marriage(user_id,target,surname)
        if ok:
            from keyboards import marriage_proposal_keyboard
            _send(vk,peer_id,f'{msg}\n\n💍 Фамилия семьи: «{surname}»\n\nСогласиться или отказаться?',marriage_proposal_keyboard())
        else:_send(vk,peer_id,msg)
        return
    if command=='развестись': _send(vk,peer_id,divorce(user_id)); return
    for cmdname in ('усыновить','удочерить'):
        if command.startswith(cmdname+' '):
            target=_target(command[len(cmdname)+1:]); result=adopt(user_id,target,vk)
            if isinstance(result,tuple): ok,msg=result
            else: ok=True;msg=result
            if ok:
                from keyboards import family_proposal_keyboard
                _send(vk,peer_id,msg,family_proposal_keyboard())
            else:_send(vk,peer_id,msg)
            return
    if command.startswith('сдать в детдом '): _send(vk,peer_id,relinquish(user_id,_target(command[len('сдать в детдом '):]),vk)); return
    if command=='уйти из семьи': _send(vk,peer_id,leave_family(user_id)); return

    # RP
    rp_names=['обнять','поцеловать','пожать руку','погладить','ущипнуть','укусить','дать пять','пнуть','положить в дурку','посадить на бутылку','застрелить','курить','уснуть','разбудить','накормить','подарить','пиво']
    rp_command=next((x for x in sorted(rp_names,key=len,reverse=True) if command==x or command.startswith(x+' ')),None)
    if rp_command:
        result=handle_rp_command(rp_command,user_id,peer_id,vk,text,get_user)
        if result:
            rp_text,rp_photo=result
            if rp_text:
                _send(vk,peer_id,rp_text,attachment=rp_photo)
        return

    # Property
    if command=='магазин':
        from keyboards import SHOP_MENU
        _send(vk,peer_id,'🛒 Магазин\n\nЧто вас интересует?',SHOP_MENU,exclude_actor=True); return
    m=re.match(r'^(дом|машина|телефон)\s+(\d+)$',command)
    if m:
        category={'дом':'housing','машина':'car','телефон':'phone'}[m.group(1)]; idx=int(m.group(2))-1; items=get_items(category)
        if not 0<=idx<len(items): _send(vk,peer_id,'❌ Такого номера нет.'); return
        item=items[idx]
        ok,msg=buy_property(user_id,category,item[0])
        _send(vk,peer_id,msg); return
    m=re.match(r'^продать\s+(дом|машина|телефон)$',command)
    if m:
        category={'дом':'housing','машина':'car','телефон':'phone'}[m.group(1)]; current=get_property_value(user_id,category)
        if current=='Отсутствует': _send(vk,peer_id,'❌ У тебя нет такого имущества.'); return
        items={x[0]:x[1] for x in get_items(category)}; refund=items.get(current,0)//2
        with db_cursor(True) as (_,c):
            field={'housing':'housing','car':'car','phone':'phone'}[category]
            c.execute(f"UPDATE users SET {field}='Отсутствует',coins=coins+? WHERE user_id=?",(refund,user_id))
        _send(vk,peer_id,f'✅ Имущество продано. Получено: {refund:,} 🪙.'); return

    # Work
    if command=='работать':
        result=work(user_id)
        _send(vk,peer_id,result); return
    if command=='устроиться':
        from keyboards import profession_keyboard
        _send(vk,peer_id,'💼 Выберите профессию:',profession_keyboard(),exclude_actor=True); return
    if command=='уволиться': _send(vk,peer_id,fire(user_id)); return

    _send(vk,peer_id,'❌ Неизвестная команда.')