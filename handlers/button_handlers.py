import json
from keyboards import menu_keyboard, back_to_menu_keyboard, get_shop_menu, profession_keyboard, shop_items_keyboard, _btn
from config import CREATOR_ID, MAIN_CHATS, EXTRA_CHATS, ALL_BOT_CHATS
from admin_commands import get_admin_level
from database import get_duel_for_opponent, delete_duel, upsert_application, toggle_recruit_role
from applications import QUESTIONS

def handle_button(cmd, user_id, peer_id, conversation_message_id, vk, payload=None):
    payload = payload if isinstance(payload, dict) else {}

    def edit(text, kb=None, attachment=None):
        keyboard_json = json.dumps(kb, ensure_ascii=False, separators=(',', ':')) if kb is not None else None
        if conversation_message_id is not None:
            try:
                vk.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=text, keyboard=keyboard_json, attachment=attachment, disable_mentions=True)
                return
            except Exception as e: print(f'Не удалось отредактировать: {e}')
        try:
            args = {'peer_id': peer_id, 'random_id': 0, 'message': text, 'keyboard': keyboard_json, 'disable_mentions': True}
            if attachment: args['attachment'] = attachment
            vk.messages.send(**args)
        except Exception as e: print(f'Не удалось отправить: {e}')

    is_admin = get_admin_level(user_id, peer_id) >= 1
    is_creator = int(user_id) == int(CREATOR_ID)
    def menu_kb(admin=None): return menu_keyboard(is_admin if admin is None else admin, is_creator)

    # --- НАСТРОЙКИ НАБОРА (ТОЛЬКО ДЛЯ СОЗДАТЕЛЯ) ---
    if cmd == 'settings_open':
        if not is_creator: return
        target_peer = payload.get('peer_id')
        from keyboards import recruit_settings_keyboard
        edit('⚙️ Настройка открытых ролей (нажми, чтобы переключить):', recruit_settings_keyboard(target_peer))
        return

    if cmd == 'toggle_recruit':
        if not is_creator: return
        target_peer = payload.get('peer_id')
        role = payload.get('role')
        toggle_recruit_role(target_peer, role)
        from keyboards import recruit_settings_keyboard
        edit('⚙️ Настройка открытых ролей:', recruit_settings_keyboard(target_peer))
        return

    # --- ЗАЯВКИ (ВЫБОР БЕСЕДЫ И РОЛИ) ---
    if cmd == 'app_chat_select':
        target_peer = payload.get('peer_id')
        # Сохраняем выбранную беседу в steps
        upsert_application(user_id, 'await_role', -1, [str(target_peer)]) 
        from keyboards import application_role_select_keyboard
        edit('📋 Шаг 2: Выбери роль, на которую ты претендуешь:', application_role_select_keyboard(target_peer))
        return

    if cmd == 'app_role_select':
        target_peer = payload.get('peer_id')
        role = payload.get('role')
        # Сохраняем в БД и переходим к вопросам
        upsert_application(user_id, 'in_progress', 0, [str(target_peer), str(role)])
        edit('Отлично! Теперь ответь на вопросы текстом.\n\n1️⃣ ' + QUESTIONS[0])
        return
        
    if cmd == 'app_role_cancel':
        from database import delete_application
        delete_application(user_id)
        edit('❌ Набор в этой беседе закрыт. Заявка отменена.')
        return

    # ЗАЯВКИ (Одобрение/Отклонение)
    if cmd in ('app_accept', 'app_decline'):
        applicant_id = payload.get('applicant')
        if not applicant_id:
            edit('Ошибка: не указан заявитель.')
            return
        decision = 'accept' if cmd == 'app_accept' else 'decline'
        from applications import review_application
        result = review_application(applicant_id, user_id, decision, vk, conversation_message_id)
        if result == 'ok': pass
        else: edit(result)
        return

    # ДУЭЛЬ
    if cmd in ('duel_accept', 'duel_decline'):
        duel = get_duel_for_opponent(user_id)
        if not duel:
            edit('Эта дуэль больше неактуальна.')
            return
        challenger_id, opponent_id, duel_peer_id, _duel_msg_id = duel
        delete_duel(user_id)
        if user_id != opponent_id: return
        from relationships import get_display_name
        def _mention(uid): return f'[id{uid}|{get_display_name(uid) or "пользователь"}]'
        challenger_mention = _mention(challenger_id)
        opponent_mention = _mention(opponent_id)
        empty_kb = json.dumps({'inline': True, 'buttons': []}, ensure_ascii=False)

        if cmd == 'duel_decline':
            new_text = f'⚔️ {opponent_mention} отказался от дуэли с {challenger_mention}. Поединок не состоится.'
            try: vk.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=new_text, keyboard=empty_kb, disable_mentions=True)
            except Exception as e: print(f'Error: {e}')
            return

        try: vk.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=f'⚔️ {opponent_mention} принял вызов!\n\n1...\n2...\n3...', keyboard=empty_kb, disable_mentions=True)
        except Exception as e: print(f'Error: {e}')

        import random, time
        time.sleep(2)
        winner_id = random.choice([challenger_id, opponent_id])
        loser_id = opponent_id if winner_id == challenger_id else challenger_id
        from database import get_power, transfer_power
        loser_power = get_power(loser_id)
        prize = int(loser_power * 0.15)
        if prize > 0: transfer_power(loser_id, winner_id, prize)
        winner_mention = _mention(winner_id)
        final_text = f'⚔️ {opponent_mention} принял вызов!\n\n1...\n2...\n3...\n\n🏆 {winner_mention} победил! Его выигрышем является {prize} ⚡ Силы Гиаса.'
        try: vk.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=final_text, keyboard=empty_kb, disable_mentions=True)
        except Exception as e: print(f'Error: {e}')
        return

    # МЕНЮ (остальное как было)
    if cmd == 'menu_main': edit('📖 Меню Lelouch Bot\n\nВыбери нужный раздел ниже.', menu_kb()); return
    if cmd == 'menu_basic': edit('📋 ОСНОВНЫЕ КОМАНДЫ\n\nлл профиль\nлл баланс\nлл ник <новый ник>\nлл активность\nлл задания\nлл дуэль @user\nлл передать @user <сумма>\nлл магазин\nлл дом <номер>\nлл машина <номер>\nлл телефон <номер>\nлл продать дом\nлл продать машину\nлл продать телефон', menu_kb()); return
    if cmd == 'menu_relationships': edit('❤️ КОМАНДЫ ОТНОШЕНИЙ\n\nлл начать отношения @user\nлл расстаться\nлл поцеловаться\nлл обняться\nлл семья [@user]\nлл создать брак @user <фамилия>\nлл развестись\nлл усыновить @user\nлл удочерить @user\nлл сдать в детдом @user\nлл уйти из семьи', menu_kb()); return
    if cmd == 'menu_rp': edit('🎭 RP-КОМАНДЫ\n\nлл обнять @user\nлл поцеловать @user\nлл пожать руку @user\nлл погладить @user\nлл ущипнуть @user\nлл укусить @user\nлл дать пять @user\nлл пнуть @user\nлл положить в дурку @user\nлл застрелить @user\nлл посадить на бутылку @user\nлл уснуть [@user]\nлл разбудить @user\nлл накормить @user\nлл подарить @user\nлл курить [@user]\nлл пиво [@user]', menu_kb()); return
    if cmd == 'menu_entertainment': edit('🎭 РАЗВЛЕЧЕНИЯ\n\n⚔️ Дуэли:\nлл дуэль @user\n\n🎰 Казино:\nлл деп <сумма>\nлл рулетка <сумма>\n\n💡 Минимальная ставка: 1 000 🪙', menu_kb()); return
    if cmd == 'menu_work': edit('💼 КОМАНДЫ РАБОТЫ\n\nлл устроиться\nлл работать\nлл уволиться\nлл работа [@user]\n\n💡 Множитель зарплаты можно повысить в VIP-магазине.', menu_kb()); return
    if cmd == 'menu_shop': edit('🛒 КОМАНДА МАГАЗИНА\n\nлл магазин\nлл дом <номер>\nлл машина <номер>\nлл телефон <номер>\nлл продать дом\nлл продать машину\nлл продать телефон', menu_kb()); return
    
    if cmd == 'menu_creator':
        if not is_creator: edit('Этот раздел доступен только создателю.', menu_kb()); return
        edit('♛ КОМАНДЫ СОЗДАТЕЛЯ\n\n💰 ВЫДАЧА РЕСУРСОВ:\nлл выдать монеты @user <количество>\nлл выдать гиас @user <количество>\nлл выдать камни @user <количество>\n\n➖ ИЗЪЯТИЕ РЕСУРСОВ:\nлл отобрать монеты @user <количество>\nлл отобрать гиас @user <количество>\nлл отобрать камни @user <количество>\n\nУказывать можно упоминание, ссылку или ID пользователя. Количество должно быть положительным целым числом.', menu_kb())
        return

    if cmd == 'menu_admin':
        if not is_admin: edit('Этот раздел доступен только администраторам.', menu_kb(False)); return
        edit('👑 АДМИНИСТРАТИВНЫЕ КОМАНДЫ\n\n🛡 МОДЕРАЦИЯ:\nлл пред @user\nлл анпред @user\nлл фулл анпред @user\nлл кик @user\nлл фулл кик @user\nлл бан @user\nлл разбан @user\nлл банстат\n\n👥 УПРАВЛЕНИЕ:\nлл админы\nлл админ стат\nлл проверить @user\nлл снять @user\nлл выдать права @user <номер_беседы> <должность>\nлл чс адм @user\nлл убрать чс адм @user\n\n📊 НОРМЫ И ОТЧЁТЫ:\nлл норма @user + (только Адм и выше)\nлл норма @user - (только Адм и выше)\n\n👥 ТВИНКИ:\nлл твинк @user\nлл твинк убрать @user\nлл твинки [@user]\n\n🖼 ОФОРМЛЕНИЕ:\nлл аватар @user <ID фото>\nлл обновить рп\nлл изменить приветствие <ID фото из альбома> <текст>\nлл приветствие\n\n⚙️ НАСТРОЙКИ БЕСЕДЫ:\nлл переключить мут\nлл переключить чистку\nлл переключить казино\nлл переключить дуэль\nлл переключить рассылку\nлл рассылка <текст>\n\n📌 ЗАКРЕПЫ:\nлл установить закреп\nлл обновить закрепы\n\n📊 СТАТИСТИКА:\nлл беседа\nлл беседы\nлл админ стат', menu_kb(True))
        return

    if cmd == 'profile':
        from handlers.user_handlers import get_profile_data
        profile_text, profile_attachment = get_profile_data(user_id, peer_id)
        edit(profile_text, attachment=profile_attachment)
        return
    if cmd == 'balance':
        from handlers.user_handlers import get_balance
        edit(get_balance(user_id))
        return
    if cmd == 'work': edit('💼 КОМАНДЫ РАБОТЫ\n\nлл устроиться\nлл работать\nлл уволиться\nлл работа [@user]', menu_kb()); return
    if cmd == 'casino': edit('🎰 КОМАНДЫ КАЗИНО\n\nлл деп <сумма>\nлл рулетка <сумма>\n\n💡 Минимальная ставка: 1 000 🪙', menu_kb()); return
    if cmd == 'shop': edit('🛒 КОМАНДЫ МАГАЗИНА\n\nлл магазин\nлл дом <номер>\nлл машина <номер>\nлл телефон <номер>\nлл продать дом\nлл продать машину\nлл продать телефон', menu_kb()); return
    if cmd == 'hire':
        from jobs.work_handler import hire
        result = hire(user_id, payload.get('profession', ''))
        edit(result)
        return
    if cmd == 'shop_category':
        from property_shop import category_text
        cat = payload.get('category')
        edit(category_text(cat), shop_items_keyboard(cat))
        return
    if cmd == 'shop_main':
        edit('🛒 Магазин\n\nЧто вас интересует?', get_shop_menu(is_admin))
        return
    if cmd == 'vip_shop':
        from handlers.message_handlers import vip_shop_text
        back_btn = {'inline': True, 'buttons': [[_btn('⬅️ Назад', 'shop_main')]]}
        edit(vip_shop_text(), back_btn)
        return
    if cmd == 'buy_property':
        from property_shop import buy_property, category_text
        cat = payload.get('category')
        name = payload.get('item')
        ok, msg = buy_property(user_id, cat, name)
        edit(msg + '\n\n' + category_text(cat), menu_kb())
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
    return