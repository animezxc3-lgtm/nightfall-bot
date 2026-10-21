import json
from keyboards import menu_keyboard, back_to_menu_keyboard, get_shop_menu, profession_keyboard, shop_items_keyboard, _btn
from admin_commands import get_admin_level
from database import get_duel_for_opponent, delete_duel


def handle_button(cmd, user_id, peer_id, conversation_message_id, vk, payload=None):
    payload = payload if isinstance(payload, dict) else {}

    def edit(text, kb=None, attachment=None):
        keyboard_json = json.dumps(kb, ensure_ascii=False, separators=(',', ':')) if kb is not None else None
        if conversation_message_id is not None:
            try:
                vk.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=text, keyboard=keyboard_json, attachment=attachment, disable_mentions=True)
                return
            except: pass
        try:
            args = {'peer_id': peer_id, 'random_id': 0, 'message': text, 'keyboard': keyboard_json, 'disable_mentions': True}
            if attachment: args['attachment'] = attachment
            vk.messages.send(**args)
        except: pass

    is_admin = get_admin_level(user_id, peer_id) >= 1

    if cmd in ('app_accept', 'app_decline'):
        applicant_id = payload.get('applicant')
        if not applicant_id: return
        decision = 'accept' if cmd == 'app_accept' else 'decline'
        from applications import review_application
        result = review_application(applicant_id, user_id, decision, vk, conversation_message_id)
        if result != 'ok': edit(result)
        return

    if cmd in ('duel_accept', 'duel_decline'):
        duel = get_duel_for_opponent(user_id)
        if not duel: return
        challenger_id, opponent_id, _, _ = duel
        delete_duel(user_id)
        if user_id != opponent_id: return
        from relationships import get_display_name
        def _mention(uid): return f'[id{uid}|{get_display_name(uid) or "пользователь"}]'
        empty_kb = json.dumps({'inline': True, 'buttons': []}, ensure_ascii=False)
        if cmd == 'duel_decline':
            try: vk.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=f'⚔️ {_mention(opponent_id)} отказался от дуэли.', keyboard=empty_kb, disable_mentions=True)
            except: pass
            return
        import random, time
        time.sleep(2)
        winner_id = random.choice([challenger_id, opponent_id])
        loser_id = opponent_id if winner_id == challenger_id else challenger_id
        from database import get_power, transfer_power
        prize = int(get_power(loser_id) * 0.15)
        if prize > 0: transfer_power(loser_id, winner_id, prize)
        try: vk.messages.edit(peer_id=peer_id, conversation_message_id=conversation_message_id, message=f'⚔️ {_mention(opponent_id)} принял вызов!\n\n🏆 {_mention(winner_id)} победил! Его выигрышем является {prize} ⚡ Силы Гиаса.', keyboard=empty_kb, disable_mentions=True)
        except: pass
        return

    if cmd == 'menu_main':
        edit('📖 Меню Lelouch Bot\n\nВыбери нужный раздел ниже.', menu_keyboard(is_admin)); return
    if cmd == 'menu_work':
        edit('💼 КОМАНДЫ РАБОТЫ\n\nлл устроиться\nлл работать\nлл уволиться\nлл работа [@user]\n\n💡 Множитель зарплаты можно повысить в VIP-магазине.', menu_keyboard(is_admin)); return
    if cmd == 'menu_shop':
        edit('🛒 КОМАНДА МАГАЗИНА\n\nлл магазин\nлл дом <номер>\nлл машина <номер>\nлл телефон <номер>\nлл продать дом\nлл продать машину\nлл продать телефон', menu_keyboard(is_admin)); return
    if cmd == 'menu_admin':
        if not is_admin:
            edit('Этот раздел доступен только администраторам.', menu_keyboard(False)); return
        edit('👑 АДМИНИСТРАТИВНЫЕ КОМАНДЫ\n\n🛡 МОДЕРАЦИЯ:\nлл пред @user\nлл анпред @user\nлл фулл анпред @user\nлл кик @user\nлл фулл кик @user\nлл бан @user\nлл разбан @user\nлл банстат\n\n👥 УПРАВЛЕНИЕ:\nлл админы\nлл проверить @user\nлл снять @user\nлл выдать права @user <номер_беседы> <должность>\nлл чс адм @user\nлл убрать чс адм @user\n\n📊 НОРМЫ И ОТЧЁТЫ:\nлл норма + @user\nлл норма - @user\n\n👥 ТВИНКИ:\nлл твинк @user\nлл твинк убрать @user\nлл твинки [@user]\n\n🖼 ОФОРМЛЕНИЕ:\nлл аватар @user <ID фото>\nлл изменить приветствие <ID фото> <текст>\nлл приветствие\n\n⚙️ НАСТРОЙКИ БЕСЕДЫ:\nлл переключить мут\nлл переключить чистку\nлл переключить казино\nлл переключить дуэль\nлл переключить рассылку\nлл рассылка <текст>\n\n📌 ЗАКРЕПЫ:\nлл установить закреп\nлл обновить закрепы\n\n📊 СТАТИСТИКА:\nлл беседа\nлл беседы', menu_keyboard(True)); return
    if cmd == 'profile':
        from handlers.user_handlers import get_profile_data
        t, a = get_profile_data(user_id, peer_id); edit(t, attachment=a); return
    if cmd == 'balance':
        from handlers.user_handlers import get_balance
        edit(get_balance(user_id)); return
    if cmd == 'shop_main':
        edit('🛒 Магазин\n\nЧто вас интересует?', get_shop_menu(is_admin)); return
    if cmd == 'vip_shop':
        from handlers.message_handlers import vip_shop_text
        edit(vip_shop_text(), {'inline': True, 'buttons': [[_btn('⬅️ Назад', 'shop_main')]]}); return
    if cmd == 'hire':
        from jobs.work_handler import hire
        edit(hire(user_id, payload.get('profession', ''))); return
    if cmd == 'shop_category':
        from property_shop import category_text
        cat = payload.get('category'); edit(category_text(cat), shop_items_keyboard(cat)); return

    if cmd in ('relationship_accept', 'relationship_reject'):
        from relationships import accept_relationship, reject_relationship
        edit(accept_relationship(user_id) if cmd == 'relationship_accept' else reject_relationship(user_id)); return
    if cmd in ('marriage_accept', 'marriage_reject'):
        from relationships import accept_marriage, reject_marriage
        edit(accept_marriage(user_id) if cmd == 'marriage_accept' else reject_marriage(user_id)); return
    if cmd in ('family_accept', 'family_reject'):
        from relationships import accept_family_addition, reject_family_addition
        edit(accept_family_addition(user_id) if cmd == 'family_accept' else reject_family_addition(user_id)); return