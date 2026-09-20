import json
from keyboards import menu_keyboard, back_to_menu_keyboard, SHOP_MENU, profession_keyboard, shop_items_keyboard
from admin_commands import get_admin_level
from database import get_duel_for_opponent, delete_duel


def handle_button(cmd, user_id, peer_id, conversation_message_id, vk, payload=None):
    payload = payload if isinstance(payload, dict) else {}

    def edit(text, kb=None):
        keyboard_json = json.dumps(kb, ensure_ascii=False, separators=(',', ':')) if kb is not None else None
        if conversation_message_id is not None:
            try:
                vk.messages.edit(
                    peer_id=peer_id,
                    conversation_message_id=conversation_message_id,
                    message=text,
                    keyboard=keyboard_json,
                    disable_mentions=True,
                )
                return
            except Exception as e:
                print(f'⚠️ Не удалось отредактировать сообщение меню: {e}')
        try:
            vk.messages.send(
                peer_id=peer_id,
                random_id=0,
                message=text,
                keyboard=keyboard_json,
                disable_mentions=True,
            )
        except Exception as e:
            print(f'⚠️ Не удалось отправить новое сообщение меню: {e}')

    is_admin = get_admin_level(user_id, peer_id) >= 1

    if cmd in ('app_accept', 'app_decline'):
        applicant_id = payload.get('applicant')
        if not applicant_id:
            edit('❌ Ошибка: не указан заявитель.')
            return
        decision = 'accept' if cmd == 'app_accept' else 'decline'
        from applications import review_application
        result = review_application(applicant_id, user_id, decision, vk, conversation_message_id)
        if result == 'ok':
            pass
        else:
            edit(result)
        return

    if cmd in ('duel_accept', 'duel_decline'):
        duel = get_duel_for_opponent(user_id)
        if not duel:
            edit('❌ Эта дуэль больше неактуальна.')
            return
        challenger_id, opponent_id, duel_peer_id, _duel_msg_id = duel
        delete_duel(user_id)

        if user_id != opponent_id:
            edit('❌ Эта дуэль не для тебя.')
            return

        from relationships import get_display_name

        def _mention(uid):
            name = get_display_name(uid) or 'пользователь'
            return f'[id{uid}|{name}]'

        challenger_mention = _mention(challenger_id)
        opponent_mention = _mention(opponent_id)

        empty_kb = json.dumps({'inline': True, 'buttons': []}, ensure_ascii=False)

        if cmd == 'duel_decline':
            new_text = f'⚔️ {opponent_mention} отказался от дуэли с {challenger_mention}. Поединок не состоится.'
            try:
                vk.messages.edit(
                    peer_id=peer_id,
                    conversation_message_id=conversation_message_id,
                    message=new_text,
                    keyboard=empty_kb,
                    disable_mentions=True,
                )
            except Exception as e:
                print(f'⚠️ Не удалось отредактировать отказ от дуэли: {e}')
            return

        try:
            vk.messages.edit(
                peer_id=peer_id,
                conversation_message_id=conversation_message_id,
                message=f'⚔️ {opponent_mention} принял вызов!\n\n1...\n2...\n3...',
                keyboard=empty_kb,
                disable_mentions=True,
            )
        except Exception as e:
            print(f'⚠️ Не удалось обновить сообщение дуэли: {e}')

        import random, time
        time.sleep(2)

        winner_id = random.choice([challenger_id, opponent_id])
        loser_id = opponent_id if winner_id == challenger_id else challenger_id

        from database import get_power, transfer_power
        loser_power = get_power(loser_id)
        prize = int(loser_power * 0.15)
        if prize > 0:
            transfer_power(loser_id, winner_id, prize)

        winner_mention = _mention(winner_id)
        final_text = (
            f'⚔️ {opponent_mention} принял вызов!\n\n'
            f'1...\n2...\n3...\n\n'
            f'🏆 {winner_mention} победил! Его выигрышем является {prize} ⚡ Силы Гиаса.'
        )
        try:
            vk.messages.edit(
                peer_id=peer_id,
                conversation_message_id=conversation_message_id,
                message=final_text,
                keyboard=empty_kb,
                disable_mentions=True,
            )
        except Exception as e:
            print(f'⚠️ Не удалось отредактировать финал дуэли: {e}')
        return

    if cmd == 'menu_main':
        edit('📖 Меню Lelouch Bot\n\nВыбери нужный раздел ниже.', menu_keyboard(is_admin))
        return

    if cmd == 'menu_basic':
        edit(
            '📋 ОСНОВНЫЕ КОМАНДЫ\n\n'
            'лл профиль\n'
            'лл баланс\n'
            'лл ник <новый ник>\n'
            'лл активность\n'
            'лл дуэль @user\n'
            'лл передать @user <сумма>\n'
            'лл магазин\n'
            'лл дом <номер>\n'
            'лл машина <номер>\n'
            'лл телефон <номер>\n'
            'лл продать дом\n'
            'лл продать машину\n'
            'лл продать телефон',
            back_to_menu_keyboard(is_admin),
        )
        return

    if cmd == 'menu_relationships':
        edit(
            '❤️ КОМАНДЫ ОТНОШЕНИЙ\n\n'
            'лл начать отношения @user\n'
            'лл расстаться\n'
            'лл поцеловаться\n'
            'лл обняться\n'
            'лл создать брак @user <фамилия>\n'
            'лл развестись\n'
            'лл усыновить @user\n'
            'лл удочерить @user\n'
            'лл сдать в детдом @user\n'
            'лл уйти из семьи',
            back_to_menu_keyboard(is_admin),
        )
        return

    if cmd == 'menu_rp':
        edit(
            '🎭 RP-КОМАНДЫ\n\n'
            'лл обнять @user\n'
            'лл поцеловать @user\n'
            'лл пожать руку @user\n'
            'лл погладить @user\n'
            'лл ущипнуть @user\n'
            'лл укусить @user\n'
            'лл дать пять @user\n'
            'лл пнуть @user\n'
            'лл положить в дурку @user\n'
            'лл застрелить @user\n'
            'лл посадить на бутылку @user\n'
            'лл уснуть [@user]\n'
            'лл разбудить @user\n'
            'лл накормить @user\n'
            'лл подарить @user\n'
            'лл курить [@user]\n'
            'лл пиво [@user]',
            back_to_menu_keyboard(is_admin),
        )
        return

    if cmd == 'menu_entertainment':
        edit(
            '🎭 РАЗВЛЕЧЕНИЯ\n\n'
            '⚔️ Дуэли:\n'
            'лл дуэль @user\n\n'
            '🎰 Казино:\n'
            'лл деп <сумма>\n\n'
            '💡 Минимальная ставка в казино: 1 000 🪙',
            back_to_menu_keyboard(is_admin),
        )
        return

    if cmd == 'menu_work':
        edit(
            '💼 КОМАНДЫ РАБОТЫ\n\n'
            'лл устроиться\n'
            'лл работать\n'
            'лл уволиться',
            back_to_menu_keyboard(is_admin),
        )
        return

    if cmd == 'menu_shop':
        edit(
            '🛒 КОМАНДА МАГАЗИНА\n\n'
            'лл магазин\n'
            'лл дом <номер>\n'
            'лл машина <номер>\n'
            'лл телефон <номер>\n'
            'лл продать дом\n'
            'лл продать машину\n'
            'лл продать телефон',
            back_to_menu_keyboard(is_admin),
        )
        return

    if cmd == 'menu_admin':
        if not is_admin:
            edit('❌ Этот раздел доступен только администраторам.', back_to_menu_keyboard(False))
            return
        edit(
            '👑 АДМИНИСТРАТИВНЫЕ КОМАНДЫ\n\n'
            '🛡 МОДЕРАЦИЯ:\n'
            'лл пред @user\n'
            'лл анпред @user\n'
            'лл фулл анпред @user\n'
            'лл кик @user\n'
            'лл фулл кик @user\n'
            'лл бан @user\n'
            'лл разбан @user\n'
            'лл банстат\n'
            '\n'
            '👥 УПРАВЛЕНИЕ:\n'
            'лл админы\n'
            'лл проверить @user\n'
            'лл снять @user\n'
            'лл выдать права @user <уровень> <номер_беседы>\n'
            'лл чс адм @user\n'
            'лл убрать чс адм @user\n'
            '\n'
            '👥 ТВИНКИ:\n'
            'лл твинк @user\n'
            'лл твинк убрать @user\n'
            'лл твинки [@user]\n'
            '\n'
            '🖼 ОФОРМЛЕНИЕ:\n'
            'лл аватар @user <ID фото>\n'
            'лл изменить приветствие <ID фото> <текст>\n'
            'лл приветствие\n'
            '\n'
            '⚙️ НАСТРОЙКИ БЕСЕДЫ:\n'
            'лл переключить мут\n'
            'лл переключить чистку\n'
            'лл переключить казино\n'
            'лл переключить дуэль\n'
            'лл переключить рассылку\n'
            'лл рассылка <текст>\n'
            'лл скрыть беседу\n'
            'лл показать беседу\n'
            '\n'
            '📌 ЗАКРЕПЫ:\n'
            'лл установить закреп\n'
            'лл обновить закрепы\n'
            '\n'
            '📊 СТАТИСТИКА:\n'
            'лл беседа\n'
            'лл беседы',
            back_to_menu_keyboard(True),
        )
        return

    if cmd == 'profile':
        from handlers.user_handlers import get_profile
        edit(get_profile(user_id, peer_id))
        return
    if cmd == 'balance':
        from handlers.user_handlers import get_balance
        edit(get_balance(user_id))
        return
    if cmd == 'work':
        edit('💼 КОМАНДЫ РАБОТЫ\n\nлл устроиться\nлл работать\nлл уволиться', back_to_menu_keyboard(is_admin))
        return
    if cmd == 'casino':
        edit(
            '🎰 КОМАНДЫ КАЗИНО\n\n'
            'лл деп <сумма>\n\n'
            '💡 Минимальная ставка: 1 000 🪙',
            back_to_menu_keyboard(is_admin),
        )
        return
    if cmd == 'shop':
        edit(
            '🛒 КОМАНДЫ МАГАЗИНА\n\n'
            'лл магазин\n'
            'лл дом <номер>\n'
            'лл машина <номер>\n'
            'лл телефон <номер>\n'
            'лл продать дом\n'
            'лл продать машину\n'
            'лл продать телефон',
            back_to_menu_keyboard(is_admin),
        )
        return
    if cmd == 'hire':
        from jobs.work_handler import hire
        result = hire(user_id, payload.get('profession', ''))
        edit(result, back_to_menu_keyboard(is_admin))
        return
    if cmd == 'shop_category':
        from property_shop import category_text
        cat = payload.get('category')
        edit(category_text(cat), shop_items_keyboard(cat))
        return
    if cmd == 'shop_main':
        edit('🛒 Магазин\n\nЧто вас интересует?', SHOP_MENU)
        return
    if cmd == 'buy_property':
        from property_shop import buy_property, category_text
        cat = payload.get('category')
        name = payload.get('item')
        ok, msg = buy_property(user_id, cat, name)
        edit(msg + '\n\n' + category_text(cat), back_to_menu_keyboard(is_admin))
        return
    if cmd in ('relationship_accept', 'relationship_reject'):
        from relationships import accept_relationship, reject_relationship
        edit(accept_relationship(user_id) if cmd == 'relationship_accept' else reject_relationship(user_id))
        return
    if cmd in ('marriage_accept', 'marriage_reject'):
        from relationships import accept_marriage, reject_marriage
        edit(accept_marriage(user_id) if cmd == 'marriage_accept' else reject_marriage(user_id))
        return
    if cmd in ('family_accept', 'family_reject'):
        from relationships import accept_family_addition, reject_family_addition
        edit(accept_family_addition(user_id) if cmd == 'family_accept' else reject_family_addition(user_id))
        return

    edit('❌ Неизвестная кнопка.')