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

def menu_keyboard(is_admin=False, is_creator=False):
    rows = [
        [_btn('📋 Основные', 'menu_basic')],
        [_btn('❤️ Отношения', 'menu_relationships'), _btn('🎭 RP', 'menu_rp')],
        [_btn('💼 Работа', 'menu_work'), _btn('🎭 Развлечение', 'menu_entertainment')],
    ]
    if is_admin:
        rows[2].append(_btn('👑 Администрирование', 'menu_admin'))
    if is_creator:
        rows.append([_btn('♛ Создатель', 'menu_creator')])
    return {'inline': True, 'buttons': rows}

def back_to_menu_keyboard(is_admin=False):
    return {'inline': True, 'buttons': [[_btn('⬅️ В меню', 'menu_main')]]}

def MAIN_MENU(is_admin=False):
    return menu_keyboard(is_admin)

def get_shop_menu(is_admin=False):
    buttons = [
        [_btn('🏠 Жильё', 'shop_category', category='housing'),
         _btn('🚗 Автомобили', 'shop_category', category='car')],
        [_btn('📱 Телефоны', 'shop_category', category='phone')],
    ]
    if is_admin:
        buttons.append([_btn('💎 VIP-магазин', 'vip_shop')])
    return {'inline': True, 'buttons': buttons}

def shop_items_keyboard(category):
    return {'inline': True, 'buttons': [[_btn('⬅️ Назад', 'shop_main')]]}

def profession_keyboard():
    PROFESSION_BUTTONS = {'шлюха':'🍆 Шлюха','алкаш':'🍺 Алкаш','тиммейт':'🎯 Тиммейт из ада','врач':'🩺 Врач','вор':'🥷 Вор'}
    buttons = [_btn(label, 'hire', profession=key) for key, label in PROFESSION_BUTTONS.items()]
    rows = [buttons[:2], buttons[2:4], buttons[4:5]]
    return {'inline': True, 'buttons': rows}

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

# --- Кнопки для заявок (ТОЛЬКО ОСНОВНЫЕ БЕСЕДЫ) ---
def application_chat_select_keyboard():
    from config import MAIN_CHATS
    buttons = []
    
    # Только 6 основных бесед, по 2 в ряд для красоты
    row = []
    for i, peer_id in enumerate(MAIN_CHATS, 1):
        row.append(_btn(f'NightFall {i}', 'app_chat_select', peer_id=peer_id))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    return {'inline': True, 'buttons': buttons}

# --- Кнопки для выбора роли (ТОЛЬКО АКТИВИСТ, РЕКРУТЕР, АДМИН) ---
def application_role_select_keyboard(peer_id):
    from database import get_recruit_settings
    open_roles = get_recruit_settings(peer_id)
    # Оставляем только Активиста (2), Рекрутера (3) и Администратора (4)
    roles = {
        2: '⚡ Активист', 
        3: '🎯 Рекрутер', 
        4: '📱 Администратор'
    }
    buttons = []
    for level, name in roles.items():
        if level in open_roles:
            buttons.append([_btn(name, 'app_role_select', peer_id=peer_id, role=level)])
            
    if not buttons:
        buttons.append([_btn('Набор закрыт', 'app_role_cancel')])
        
    return {'inline': True, 'buttons': buttons}

# --- Кнопки для настройки набора (ВСЕ БЕСЕДЫ) ---
def settings_chats_keyboard():
    from config import MAIN_CHATS, EXTRA_CHATS
    buttons = []
    
    # Основные по 2 в ряд
    row = []
    for i, peer_id in enumerate(MAIN_CHATS, 1):
        row.append(_btn(f'NightFall {i}', 'settings_open', peer_id=peer_id))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    # Дополнительные
    buttons.append([
        _btn('NF || Anarchy', 'settings_open', peer_id=EXTRA_CHATS[0]),
        _btn('NF || Casino', 'settings_open', peer_id=EXTRA_CHATS[1])
    ])
    
    return {'inline': True, 'buttons': buttons}

def recruit_settings_keyboard(peer_id):
    from database import get_recruit_settings
    open_roles = get_recruit_settings(peer_id)
    roles = {
        1: '🎓 Стажёр', 2: '⚡ Активист', 3: '🎯 Рекрутер', 4: '📱 Админ', 5: '🌟 Куратор'
    }
    buttons = []
    for level, name in roles.items():
        status = '✅' if level in open_roles else '❌'
        buttons.append([_btn(f'{status} {name}', 'toggle_recruit', peer_id=peer_id, role=level)])
    buttons.append([_btn('⬅️ Назад', 'settings_menu')])
    return {'inline': True, 'buttons': buttons}