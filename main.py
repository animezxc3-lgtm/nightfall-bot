import json, threading, time, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from config import TOKEN, GROUP_ID, CREATOR_ID, ALLOWED_IN_DM, REPORT_CHAT_ID
from database import (
    migrate_database, user_exists, create_user, set_admin_level, set_global_role, ensure_chat,
    add_message_count, claim_power_for_messages, get_feature, record_chat_join,
    get_chat_join_date, get_welcome_data, is_twink, get_owner,
    grant_one_time_coins, coin_grant_chat_scanned, mark_coin_grant_chat_scanned
)
from handlers.message_handlers import handle_command
from handlers.button_handlers import handle_button
from cleanup import run_cleanup
from reactions import maybe_react
from response_context import set_user
from admin_commands import get_admin_level, repair_legacy_local_role_peer_ids
from applications import start_application, handle_dm_message, cancel_application
from pin_manager import update_all_pins
from weekly_report import send_weekly_report
from tasks import event as task_event, notify_task_rewards

MOSCOW = ZoneInfo('Europe/Moscow')

def next_sunday(hour, minute):
    now = datetime.now(MOSCOW)
    days = (6 - now.weekday()) % 7
    t = (now + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if t <= now:
        t += timedelta(days=7)
    return t

def _obj_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def grant_starting_coins_to_chat_members(peer_id):
    """One-time campaign: grant 100,000 coins to members present in each discovered chat.

    A user can receive the grant only once across all chats. The chat is marked as
    scanned only after VK returns a successful member list.
    """
    if not peer_id or int(peer_id) <= 2000000000 or coin_grant_chat_scanned(peer_id):
        return
    try:
        response = vk.messages.getConversationMembers(peer_id=int(peer_id))
        items = response.get('items', []) if isinstance(response, dict) else []
        profiles = response.get('profiles', []) if isinstance(response, dict) else []
        names = {}
        for profile in profiles:
            try:
                pid = int(profile.get('id', 0))
                full_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
                if pid > 0 and full_name:
                    names[pid] = full_name
            except Exception:
                continue
        member_ids = set()
        for item in items:
            try:
                mid = int(item.get('member_id', item.get('id', 0)))
                if mid > 0:
                    member_ids.add(mid)
            except Exception:
                continue
        for member_id in member_ids:
            if not user_exists(member_id):
                name = names.get(member_id)
                if not name:
                    try:
                        info = vk.users.get(user_ids=member_id)[0]
                        name = f"{info.get('first_name', '')} {info.get('last_name', '')}".strip() or 'Участник'
                    except Exception:
                        name = 'Участник'
                create_user(member_id, name)
            if grant_one_time_coins(member_id, 100000):
                print(f'[COINS][ONE-TIME] user={member_id} +100000')
        mark_coin_grant_chat_scanned(peer_id)
        print(f'[COINS][ONE-TIME] Беседа {peer_id}: обработано участников {len(member_ids)}')
    except Exception as exc:
        # Do not mark the chat as scanned if VK request failed; retry on a later message.
        print(f'[COINS][ONE-TIME] Не удалось получить участников беседы {peer_id}: {exc}')


def send_welcome(peer_id, user_id):
    try:
        info = vk.users.get(user_ids=user_id)[0]
        name = f"{info.get('first_name','')} {info.get('last_name','')}".strip() or 'участник'
    except Exception:
        name = 'участник'
    welcome, photo = get_welcome_data(peer_id)
    # Keep legacy placeholders and support (user) anywhere in the greeting.
    # VK's [idN|Name] syntax creates a clickable mention rather than plain text.
    mention = f'[id{user_id}|{name}]'
    text = welcome.replace('{name}', name).replace('{id}', str(user_id))
    text = text.replace('{profile}', f'https://vk.com/id{user_id}')
    text = re.sub(r'\(user\)', lambda _m: mention, text, flags=re.IGNORECASE)
    args = {'peer_id': peer_id, 'random_id': 0, 'message': text}
    if photo:
        args['attachment'] = photo
    try:
        vk.messages.send(**args)
    except Exception as e:
        print(f'⚠️ Не удалось отправить приветствие в беседе {peer_id}: {e}')

def scheduler():
    while True:
        target = next_sunday(21, 0)
        time.sleep(max(1, (target - datetime.now(MOSCOW)).total_seconds()))
        try:
            for result in run_cleanup(vk, CREATOR_ID, get_admin_level):
                pass
        except Exception as e:
            print(f'⚠️ Ошибка чистки: {e}')

        try:
            send_weekly_report(vk, REPORT_CHAT_ID)
        except Exception as e:
            print(f'⚠️ Ошибка созыва: {e}')

print('⚡ Запуск бота...')
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)
migrate_database()
# Recover local roles written by older versions under the fabricated peer_id
# 2000000000 + chat-number. Ambiguous rows are left untouched for manual review.
try:
    repair_legacy_local_role_peer_ids(vk)
except Exception as e:
    print(f'[RIGHTS][MIGRATION] Не удалось выполнить восстановление старых ролей: {e}')

try:
    update_all_pins(vk)
except Exception as e:
    print(f'⚠️ Ошибка синхронизации закрепов: {e}')

threading.Thread(target=scheduler, daemon=True).start()
print('⚡ Бот готов.')

processed_events = set()
MAX_PROCESSED = 2000

for event in longpoll.listen():
    try:
        event_id = getattr(event, 'event_id', None)
        if event_id is not None:
            if event_id in processed_events:
                continue
            processed_events.add(event_id)
            if len(processed_events) > MAX_PROCESSED:
                processed_events.clear()

        # --- КНОПКИ ---
        if event.type == VkBotEventType.MESSAGE_EVENT:
            obj = event.object
            raw_payload = _obj_get(obj, 'payload', '{}')
            try:
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else (raw_payload or {})
            except Exception:
                payload = {}
            cmd = payload.get('cmd') if isinstance(payload, dict) else None
            event_id_cb = _obj_get(obj, 'event_id')
            event_user_id = _obj_get(obj, 'user_id')
            event_peer_id = _obj_get(obj, 'peer_id')
            conversation_message_id = _obj_get(obj, 'conversation_message_id')
            try:
                vk.messages.sendMessageEventAnswer(
                    event_id=event_id_cb,
                    user_id=event_user_id,
                    peer_id=event_peer_id,
                )
            except Exception:
                pass
            if cmd:
                handle_button(cmd, event_user_id, event_peer_id, conversation_message_id, vk, payload)
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
                if uid == CREATOR_ID:
                    set_global_role(uid, 7)
                if get_chat_join_date(peer, uid) is None:
                    record_chat_join(peer, uid)
                send_welcome(peer, uid)
            continue

        # --- СООБЩЕНИЯ ---
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue
            
        m = event.object.message
        text = m.get('text', '').strip()
        peer = m['peer_id']
        uid = m['from_id']
        is_chat = peer > 2000000000
        
        if uid <= 0:
            continue

        action = m.get('action') or {}
        action_type = action.get('type') if isinstance(action, dict) else None
        member_id = action.get('member_id') if isinstance(action, dict) else None

        # --- ВЫХОД ИЗ БЕСЕДЫ (авто-кик) ---
        if is_chat and action_type == 'chat_kick_user' and member_id:
            if member_id == uid:
                if get_admin_level(member_id, peer) >= 1:
                    continue
                if is_twink(member_id):
                    continue
                try:
                    vk.messages.removeChatUser(chat_id=peer - 2000000000, user_id=member_id)
                except Exception:
                    pass
                try:
                    vk.messages.send(
                        peer_id=peer, random_id=0,
                        message='Империи нужны воистину верные люди.',
                        disable_mentions=True,
                    )
                except Exception:
                    pass
                continue
            continue

        # --- ВХОД В БЕСЕДУ ---
        invited_uid = action.get('member_id') if isinstance(action, dict) else None
        if is_chat and action_type in ('chat_invite_user', 'chat_invite_user_by_link') and invited_uid:
            if not user_exists(invited_uid):
                try:
                    info = vk.users.get(user_ids=invited_uid)[0]
                    create_user(invited_uid, f"{info['first_name']} {info['last_name']}")
                except Exception:
                    create_user(invited_uid, 'Участник')
            ensure_chat(peer)
            # Fill inviter even if GROUP_JOIN recorded the member first.
            record_chat_join(peer, invited_uid, invited_by=uid)
            try:
                awarded_tasks = task_event(uid, 'invite', amount=1, peer_id=peer)
                notify_task_rewards(vk, peer, uid, awarded_tasks)
            except Exception as e:
                print(f'⚠️ Ошибка обновления админского задания на приглашение: {e}')
            send_welcome(peer, invited_uid)
            continue

        if not user_exists(uid):
            try:
                info = vk.users.get(user_ids=uid)[0]
                create_user(uid, f"{info['first_name']} {info['last_name']}")
            except Exception:
                create_user(uid, 'Участник')

        # --- ЛИЧНЫЕ СООБЩЕНИЯ ---
        if not is_chat:
            lowered = text.lower()
            if lowered.startswith('лл '):
                command = lowered[3:].strip()
                if command == 'заявка':
                    reply = start_application(uid, vk)
                    vk.messages.send(peer_id=uid, random_id=0, message=reply, disable_mentions=True)
                    continue
                if command == 'отмена':
                    cancel_application(uid, vk)
                    continue
            # Обработка состояний заявки и покупок в ЛС
            if handle_dm_message(uid, text, vk):
                continue
            continue

        # --- СООБЩЕНИЯ В БЕСЕДЕ ---
        ensure_chat(peer)
        grant_starting_coins_to_chat_members(peer)
        add_message_count(uid, peer)
        try:
            awarded_tasks = task_event(uid, 'messages', peer_id=peer)
            notify_task_rewards(vk, peer, uid, awarded_tasks)
        except Exception as e:
            print(f'⚠️ Ошибка обновления заданий по сообщениям пользователя {uid}: {e}')
        claim_power_for_messages(uid)
        
        # Мут
        if get_feature(peer, 'мут') and get_admin_level(uid, peer) == 0:
            try:
                vk.messages.delete(peer_id=peer, conversation_message_ids=m.get('conversation_message_id'), delete_for_all=True)
            except Exception:
                pass
            continue
            
        # Реакции на слова
        if not text.lower().startswith('лл'):
            maybe_react(text, peer, vk)
            
        # Обработка команд
        if text.lower().startswith('лл '):
            handle_command(text[3:].strip(), uid, peer, vk, text)
            
    except Exception as e:
        print(f'⚠️ Ошибка обработки события: {e}')