import json,threading,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll,VkBotEventType
from config import TOKEN,GROUP_ID,CREATOR_ID,ALLOWED_IN_DM
from database import (
    migrate_database,user_exists,create_user,set_admin_level,ensure_chat,
    add_message_count,claim_power_for_messages,get_feature,record_chat_join,
    get_chat_join_date,get_welcome_data
)
from handlers.message_handlers import handle_command
from handlers.button_handlers import handle_button
from cleanup import run_cleanup
from reactions import maybe_react
from response_context import set_user
from admin_commands import get_admin_level
from applications import start_application, handle_dm_message, cancel_application
from pin_manager import update_all_pins

MOSCOW=ZoneInfo('Europe/Moscow')

def next_sunday(hour,minute):
    now=datetime.now(MOSCOW); days=(6-now.weekday())%7; t=(now+timedelta(days=days)).replace(hour=hour,minute=minute,second=0,microsecond=0)
    if t<=now:t+=timedelta(days=7)
    return t

def _obj_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def send_welcome(peer_id, user_id):
    try:
        info=vk.users.get(user_ids=user_id)[0]
        name=f"{info.get('first_name','')} {info.get('last_name','')}".strip() or 'участник'
    except Exception:
        name='участник'
    welcome, photo = get_welcome_data(peer_id)
    text=welcome.replace('{name}', name).replace('{id}', str(user_id))
    text=text.replace('{profile}', f'https://vk.com/id{user_id}')
    args={'peer_id':peer_id,'random_id':0,'message':text}
    if photo:
        args['attachment']=photo
    try:
        vk.messages.send(**args)
    except Exception as e:
        print(f'⚠️ Не удалось отправить приветствие в беседе {peer_id}: {e}')

def scheduler():
    while True:
        target=next_sunday(21,0); time.sleep(max(1,(target-datetime.now(MOSCOW)).total_seconds()))
        try:
            for result in run_cleanup(vk,CREATOR_ID,get_admin_level): print('🧹',result)
        except Exception as e: print('⚠️ Ошибка чистки:',e)

print('⚡ Запуск бота...')
vk_session=vk_api.VkApi(token=TOKEN); vk=vk_session.get_api(); longpoll=VkBotLongPoll(vk_session,GROUP_ID)
migrate_database()

# === СИНХРОНИЗАЦИЯ ЗАКРЕПОВ ПРИ ЗАПУСКЕ ===
try:
    print('📌 Проверяю актуальность закрепов...')
    pin_results = update_all_pins(vk)
    updated = sum(1 for _, status in pin_results if status == 'updated')
    print(f'📌 Закрепы синхронизированы. Обновлено: {updated}')
except Exception as e:
    print(f'⚠️ Не удалось синхронизировать закрепы при запуске: {e}')

threading.Thread(target=scheduler,daemon=True).start()
print('⚡ Бот готов.')

for event in longpoll.listen():
    try:
        if event.type == VkBotEventType.MESSAGE_EVENT:
            obj = event.object
            raw_payload = _obj_get(obj, 'payload', '{}')
            try:
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else (raw_payload or {})
            except Exception:
                payload = {}
            cmd = payload.get('cmd') if isinstance(payload, dict) else None
            event_id = _obj_get(obj, 'event_id')
            event_user_id = _obj_get(obj, 'user_id')
            event_peer_id = _obj_get(obj, 'peer_id')
            conversation_message_id = _obj_get(obj, 'conversation_message_id')
            try:
                vk.messages.sendMessageEventAnswer(
                    event_id=event_id,
                    user_id=event_user_id,
                    peer_id=event_peer_id,
                )
            except Exception as answer_error:
                print(f'⚠️ Не удалось подтвердить callback VK: {answer_error}')
            if cmd:
                handle_button(cmd, event_user_id, event_peer_id, conversation_message_id, vk, payload)
            continue

        if event.type==VkBotEventType.GROUP_JOIN:
            obj=event.object;uid=_obj_get(obj,'user_id');peer=_obj_get(obj,'peer_id')
            if uid and not user_exists(uid):
                info=vk.users.get(user_ids=uid)[0];create_user(uid,f"{info['first_name']} {info['last_name']}")
            if uid and peer:
                if uid==CREATOR_ID:
                    set_admin_level(peer,uid,6,'Лелуш ви Британия')
                if get_chat_join_date(peer, uid) is None:
                    record_chat_join(peer, uid)
                send_welcome(peer, uid)
            continue

        if event.type!=VkBotEventType.MESSAGE_NEW:continue
        m=event.object.message; text=m.get('text','').strip();peer=m['peer_id'];uid=m['from_id'];is_chat=peer>2000000000
        if uid<=0:continue

        action=m.get('action') or {}
        action_type=action.get('type') if isinstance(action,dict) else None
        member_id=action.get('member_id') if isinstance(action,dict) else None

        # === АВТОКИК ПРИ ВЫХОДЕ ===
        if is_chat and action_type == 'chat_kick_user' and member_id:
            if member_id == uid:
                if get_admin_level(member_id, peer) >= 1:
                    print(f'⏭️ Выход админа: {member_id} из {peer} — не трогаем.')
                    continue
                from database import is_twink
                if is_twink(member_id):
                    print(f'⏭️ Выход твинка: {member_id} из {peer} — не трогаем.')
                    continue
                try:
                    vk.messages.removeChatUser(chat_id=peer - 2000000000, user_id=member_id)
                    print(f'👢 Автокик после выхода: {member_id} из {peer}')
                except Exception as e:
                    print(f'⚠️ Не удалось кикнуть после выхода: {e}')
                try:
                    vk.messages.send(
                        peer_id=peer, random_id=0,
                        message='Империи нужны воистину верные люди.',
                        disable_mentions=True,
                    )
                except Exception as e:
                    print(f'⚠️ Не удалось отправить сообщение о выходе: {e}')
                continue
            continue

        invited_uid=action.get('member_id') if isinstance(action,dict) else None
        if is_chat and action_type in ('chat_invite_user','chat_invite_user_by_link') and invited_uid:
            if not user_exists(invited_uid):
                try:
                    info=vk.users.get(user_ids=invited_uid)[0]
                    create_user(invited_uid,f"{info['first_name']} {info['last_name']}")
                except Exception:
                    create_user(invited_uid,'Участник')
            ensure_chat(peer)
            if get_chat_join_date(peer,invited_uid) is None:
                record_chat_join(peer,invited_uid, invited_by=uid)
            send_welcome(peer,invited_uid)
            continue

        if not user_exists(uid):
            try:
                info=vk.users.get(user_ids=uid)[0];create_user(uid,f"{info['first_name']} {info['last_name']}")
            except Exception:
                create_user(uid,'Участник')

        # ЛС
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
            if handle_dm_message(uid, text, vk):
                continue
            continue

        # Беседа
        ensure_chat(peer);add_message_count(uid,peer)
        claim_power_for_messages(uid)
        if get_feature(peer,'мут') and get_admin_level(uid,peer)==0:
            try:vk.messages.delete(peer_id=peer,conversation_message_ids=m.get('conversation_message_id'),delete_for_all=True)
            except Exception:pass
            continue
        if not text.lower().startswith('лл'):
            maybe_react(text, peer, vk)
        if text.lower().startswith('лл '):handle_command(text[3:].strip().lower(),uid,peer,vk,text)
    except Exception as e:
        print('⚠️ Ошибка обработки события:',e)