import json, threading, time, re
from datetime import datetime, timedelta
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from config import TOKEN, GROUP_ID, CREATOR_ID, ALLOWED_IN_DM, ALL_BOT_CHATS, MAIN_CHATS, EXTRA_CHATS, APPLICATIONS_PEER_ID
from database import (
    migrate_database, user_exists, create_user, set_admin_level, set_global_role, ensure_chat,
    add_message_count, claim_power_for_messages, get_feature, record_chat_join,
    get_chat_join_date, get_welcome_data, is_twink, get_owner, get_user_admin_rights,
    grant_one_time_coins, coin_grant_chat_scanned, mark_coin_grant_chat_scanned
)
from handlers.message_handlers import handle_command
from handlers.button_handlers import handle_button
from reactions import maybe_react
from response_context import set_user
from admin_commands import get_admin_level, repair_legacy_local_role_peer_ids
from applications import start_application, handle_dm_message, cancel_application
from pin_manager import update_all_pins
from weekly_report import send_weekly_report
from tasks import event as task_event, notify_task_rewards

def _obj_get(obj, key, default=None):
    if isinstance(obj, dict): return obj.get(key, default)
    return getattr(obj, key, default)

def grant_starting_coins_to_chat_members(peer_id):
    if not peer_id or int(peer_id) <= 2000000000 or coin_grant_chat_scanned(peer_id): return
    try:
        response = vk.messages.getConversationMembers(peer_id=int(peer_id))
        items, profiles = response.get('items', []), response.get('profiles', [])
        names = {int(p['id']): f"{p['first_name']} {p['last_name']}".strip() for p in profiles if p.get('id')}
        member_ids = set()
        for item in items:
            mid = int(item.get('member_id', item.get('id', 0)))
            if mid > 0: member_ids.add(mid)
        for mid in member_ids:
            if not user_exists(mid):
                name = names.get(mid, 'Участник')
                create_user(mid, name)
            if grant_one_time_coins(mid, 100000):
                print(f'[COINS][ONE-TIME] user={mid} +100000')
        mark_coin_grant_chat_scanned(peer_id)
    except Exception as exc:
        print(f'[COINS][ONE-TIME] Ошибка беседы {peer_id}: {exc}')

def send_welcome(peer_id, user_id):
    try:
        info = vk.users.get(user_ids=user_id)[0]
        name = f"{info.get('first_name','')} {info.get('last_name','')}".strip() or 'участник'
    except Exception: name = 'участник'
    welcome, photo = get_welcome_data(peer_id)
    mention = f'[id{user_id}|{name}]'
    text = welcome.replace('{name}', name).replace('{id}', str(user_id)).replace('{profile}', f'https://vk.com/id{user_id}')
    text = re.sub(r'\(user\)', lambda _m: mention, text, flags=re.IGNORECASE)
    args = {'peer_id': peer_id, 'random_id': 0, 'message': text}
    if photo: args['attachment'] = photo
    try: vk.messages.send(**args)
    except Exception as e: print(f'⚠️ Приветствие {peer_id}: {e}')

print('⚡ Запуск бота...')
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)
migrate_database()
try: repair_legacy_local_role_peer_ids(vk)
except Exception as e: print(f'[RIGHTS][MIGRATION] {e}')

try: update_all_pins(vk)
except Exception as e: print(f'⚠️ Ошибка синхронизации закрепов: {e}')

print('⚡ Бот готов.')

processed_events = set()
MAX_PROCESSED = 2000

for event in longpoll.listen():
    try:
        event_id = getattr(event, 'event_id', None)
        if event_id is not None:
            if event_id in processed_events: continue
            processed_events.add(event_id)
            if len(processed_events) > MAX_PROCESSED: processed_events.clear()

        # --- КНОПКИ ---
        if event.type == VkBotEventType.MESSAGE_EVENT:
            obj = event.object
            raw_payload = _obj_get(obj, 'payload', '{}')
            try: payload = json.loads(raw_payload) if isinstance(raw_payload, str) else (raw_payload or {})
            except Exception: payload = {}
            cmd = payload.get('cmd') if isinstance(payload, dict) else None
            event_id_cb = _obj_get(obj, 'event_id')
            event_user_id = _obj_get(obj, 'user_id')
            event_peer_id = _obj_get(obj, 'peer_id')
            conversation_message_id = _obj_get(obj, 'conversation_message_id')
            try:
                vk.messages.sendMessageEventAnswer(event_id=event_id_cb, user_id=event_user_id, peer_id=event_peer_id)
            except Exception: pass
            if cmd: handle_button(cmd, event_user_id, event_peer_id, conversation_message_id, vk, payload)
            continue

        # --- ВСТУПЛЕНИЕ В БЕСЕДУ ---
        if event.type == VkBotEventType.GROUP_JOIN:
            obj = event.object
            uid = _obj_get(obj, 'user_id')
            peer = _obj_get(obj, 'peer_id')
            if uid and not user_exists(uid):
                info = vk.users.get(user_ids=uid)[0]
                create_user(uid, f"{info['first_name']} {info['last_name']}")
            if uid and peer:
                if uid == CREATOR_ID: set_global_role(uid, 7)
                if get_chat_join_date(peer, uid) is None: record_chat_join(peer, uid)
                if peer in EXTRA_CHATS: send_welcome(peer, uid)
                elif peer in MAIN_CHATS: send_welcome(peer, uid)
            continue

        # --- СООБЩЕНИЯ ---
        if event.type != VkBotEventType.MESSAGE_NEW: continue
            
        m = event.object.message
        text = m.get('text', '').strip()
        peer = m['peer_id']
        uid = m['from_id']
        is_chat = peer > 2000000000
        
        if uid <= 0: continue

        # ФИЛЬТР БЕСЕД: Бот работает только в разрешенных
        if is_chat and peer not in ALL_BOT_CHATS: continue

        action = m.get('action') or {}
        action_type = action.get('type') if isinstance(action, dict) else None
        member_id = action.get('member_id') if isinstance(action, dict) else None

        # --- ВЫХОД ИЗ БЕСЕДЫ ---
        if is_chat and action_type == 'chat_kick_user' and member_id:
            if member_id == uid:
                g_level, l_roles = get_user_admin_rights(member_id)
                is_any_admin = (g_level > 0) or any(lvl > 0 for _, lvl in l_roles)
                if is_any_admin or is_twink(member_id): continue
                try: vk.messages.removeChatUser(chat_id=peer - 2000000000, user_id=member_id)
                except Exception: pass
                try: vk.messages.send(peer_id=peer, random_id=0, message='Империи нужны воистину верные люди.', disable_mentions=True)
                except Exception: pass
                continue
            continue

        # --- ВХОД В БЕСЕДУ ---
        invited_uid = action.get('member_id') if isinstance(action, dict) else None
        if is_chat and action_type in ('chat_invite_user', 'chat_invite_user_by_link') and invited_uid:
            if not user_exists(invited_uid):
                try:
                    info = vk.users.get(user_ids=invited_uid)[0]
                    create_user(invited_uid, f"{info['first_name']} {info['last_name']}")
                except Exception: create_user(invited_uid, 'Участник')
            ensure_chat(peer)
            record_chat_join(peer, invited_uid, invited_by=uid)
            
            if peer in EXTRA_CHATS:
                in_main = False
                for mc in MAIN_CHATS:
                    try:
                        members = vk.messages.getConversationMembers(peer_id=mc).get('items', [])
                        if any(mem.get('member_id') == invited_uid for mem in members):
                            in_main = True
                            break
                    except Exception: pass
                if not in_main:
                    try: vk.messages.removeChatUser(chat_id=peer - 2000000000, user_id=invited_uid)
                    except Exception: pass
                    continue
            else:
                send_welcome(peer, invited_uid)
            
            try:
                awarded_tasks = task_event(uid, 'invite', amount=1, peer_id=peer)
                notify_task_rewards(vk, peer, uid, awarded_tasks)
            except Exception as e: print(f'⚠️ Ошибка заданий: {e}')
            continue

        if not user_exists(uid):
            try:
                info = vk.users.get(user_ids=uid)[0]
                create_user(uid, f"{info['first_name']} {info['last_name']}")
            except Exception: create_user(uid, 'Участник')

        # --- ЛИЧНЫЕ СООБЩЕНИЯ ---
        if not is_chat:
            lowered = text.lower()
            if lowered.startswith('лл '):
                command = lowered[3:].strip()
                if command == 'заявка':
                    reply = start_application(uid, vk)
                    if reply:
                        vk.messages.send(peer_id=uid, random_id=0, message=reply, disable_mentions=True)
                    continue
                if command == 'отмена':
                    cancel_application(uid, vk)
                    continue
                if command.startswith('вип ') or command.startswith('купить '):
                    from handlers.message_handlers import VIP_PRICES, _check_salary_mult_cap
                    from database import debit_gems, clear_warnings, increase_salary_multiplier, update_gems
                    from tasks import get_extra_task_slots, buy_extra_task_slot
                    parts = command.split()
                    if len(parts) == 2:
                        try: n = int(parts[1])
                        except ValueError: n = 0
                        price = VIP_PRICES.get(n)
                        if price:
                            if n == 4 and _check_salary_mult_cap(uid):
                                vk.messages.send(peer_id=uid, random_id=0, message='Множитель уже максимальный (×7).', disable_mentions=True)
                            elif n in (5, 6):
                                owned_slots = get_extra_task_slots(uid)
                                wanted = n - 4
                                if owned_slots >= wanted:
                                    vk.messages.send(peer_id=uid, random_id=0, message='Этот слот уже открыт.', disable_mentions=True)
                                elif wanted != owned_slots + 1:
                                    vk.messages.send(peer_id=uid, random_id=0, message='Сначала открой предыдущий слот.', disable_mentions=True)
                                elif not debit_gems(uid, price):
                                    vk.messages.send(peer_id=uid, random_id=0, message='Недостаточно Камней души.', disable_mentions=True)
                                else:
                                    ok, message = buy_extra_task_slot(uid, n - 3)
                                    if not ok: update_gems(uid, price)
                                    vk.messages.send(peer_id=uid, random_id=0, message=message, disable_mentions=True)
                            elif not debit_gems(uid, price):
                                vk.messages.send(peer_id=uid, random_id=0, message='Недостаточно Камней души.', disable_mentions=True)
                            else:
                                if n == 1:
                                    vk.messages.send(peer_id=uid, random_id=0, message='GIF/видео куплено. Пришли ссылку на документ VK следующим сообщением.', disable_mentions=True)
                                    from database import upsert_application
                                    upsert_application(uid, 'await_gif', 0, [])
                                elif n == 2:
                                    vk.messages.send(peer_id=uid, random_id=0, message='Статус куплен. Напиши текст статуса (до 30 символов).', disable_mentions=True)
                                    from database import upsert_application
                                    upsert_application(uid, 'await_status', 0, [])
                                elif n == 3:
                                    clear_warnings(uid, None) 
                                    vk.messages.send(peer_id=uid, random_id=0, message='Предупреждение снято.', disable_mentions=True)
                                    try: vk.messages.send(peer_id=APPLICATIONS_PEER_ID, random_id=0, message=f'💎 VIP-ЛОГ\nПользователь: [id{uid}|{uid}]\nКупил(а): Снятие предупреждения', disable_mentions=True)
                                    except: pass
                                elif n == 4:
                                    new_mult = increase_salary_multiplier(uid, 0.5, 7.0)
                                    vk.messages.send(peer_id=uid, random_id=0, message=f'Множитель зарплаты повышен до ×{new_mult}.', disable_mentions=True)
                                    try: vk.messages.send(peer_id=APPLICATIONS_PEER_ID, random_id=0, message=f'💎 VIP-ЛОГ\nПользователь: [id{uid}|{uid}]\nКупил(а): Повышение множителя зарплаты (текущий ×{new_mult})', disable_mentions=True)
                                    except: pass
                    continue
                if command == 'настроить набор':
                    if uid != CREATOR_ID: continue
                    from keyboards import settings_chats_keyboard
                    vk.messages.send(peer_id=uid, random_id=0, message='⚙️ Выбери беседу для настройки набора:', keyboard=json.dumps(settings_chats_keyboard(), ensure_ascii=False), disable_mentions=True)
                    continue

            if handle_dm_message(uid, text, vk): continue
            continue

        # --- СООБЩЕНИЯ В БЕСЕДЕ ---
        ensure_chat(peer)
        grant_starting_coins_to_chat_members(peer)
        add_message_count(uid, peer)
        try:
            awarded_tasks = task_event(uid, 'messages', peer_id=peer)
            notify_task_rewards(vk, peer, uid, awarded_tasks)
        except Exception as e: print(f'⚠️ Задания: {e}')
        claim_power_for_messages(uid)
        
        if get_feature(peer, 'мут') and get_admin_level(uid, peer) == 0:
            try: vk.messages.delete(peer_id=peer, conversation_message_ids=m.get('conversation_message_id'), delete_for_all=True)
            except Exception: pass
            continue
            
        if not text.lower().startswith('лл'): maybe_react(text, peer, vk)
        if text.lower().startswith('лл '): handle_command(text[3:].strip(), uid, peer, vk, text)
            
    except Exception as e:
        print(f'⚠️ Ошибка обработки события: {e}')