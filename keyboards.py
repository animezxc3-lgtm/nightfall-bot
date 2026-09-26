import json


def _btn(label, cmd, **extra):
    payload = {'cmd': cmd}
    payload.update(extra)
    return {
        'action': {
            'type': 'callback',
            'label': label,
            'payload': json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
        }
    }


def menu_keyboard(is_admin=False):
    rows = [
        [_btn('📋 Основные', 'menu_basic')],
        [_btn('❤️ Отношения', 'menu_relationships'), _btn('🎭 RP', 'menu_rp')],
        [_btn('💼 Работа', 'menu_work'), _btn('🎭 Развлечение', 'menu_entertainment')],
    ]
    if is_admin:
        rows[2].append(_btn('👑 Администрирование', 'menu_admin'))
    return {'inline': True, 'buttons': rows}


def back_to_menu_keyboard(is_admin=False):
    return {'inline': True, 'buttons': [[_btn('⬅️ В меню', 'menu_main')]]}


def MAIN_MENU(is_admin=False):
    return menu_keyboard(is_admin)


SHOP_MENU = {
    'inline': True,
    'buttons': [
        [_btn('🏠 Жильё', 'shop_category', category='housing'),
         _btn('🚗 Автомобили', 'shop_category', category='car')],
        [_btn('📱 Телефоны', 'shop_category', category='phone')],
    ],
}


def profession_keyboard():
    PROFESSION_BUTTONS = {
        'шлюха': '🍆 Шлюха',
        'алкаш': '🍺 Алкаш',
        'тиммейт': '🎯 Тиммейт из ада',
        'врач': '🩺 Врач',
        'вор': '🥷 Вор',
    }
    buttons = [_btn(label, 'hire', profession=key) for key, label in PROFESSION_BUTTONS.items()]
    rows = [buttons[:2], buttons[2:4], buttons[4:5]]
    return {'inline': True, 'buttons': rows}


def shop_items_keyboard(category):
    return {'inline': True, 'buttons': [[_btn('⬅️ Назад', 'shop_main')]]}


def marriage_proposal_keyboard():
    return {'inline': True, 'buttons': [[
        _btn('💍 Согласиться', 'marriage_accept'),
        _btn('❌ Отказаться', 'marriage_reject'),
    ]]}


def relationship_proposal_keyboard():
    return {'inline': True, 'buttons': [[
        _btn('❤️ Согласиться', 'relationship_accept'),
        _btn('❌ Отказаться', 'relationship_reject'),
    ]]}


def family_proposal_keyboard():
    return {'inline': True, 'buttons': [[
        _btn('👪 Принять', 'family_accept'),
        _btn('❌ Отказаться', 'family_reject'),
    ]]}


def duel_keyboard():
    return {'inline': True, 'buttons': [[
        _btn('✅ Принять', 'duel_accept'),
        _btn('❌ Отказаться', 'duel_decline'),
    ]]}


def application_review_keyboard(applicant_id):
    return {'inline': True, 'buttons': [[
        _btn('✅ Принять', 'app_accept', applicant=applicant_id),
        _btn('❌ Отклонить', 'app_decline', applicant=applicant_id),
    ]]}


def rp_keyboard():
    return back_to_menu_keyboard()