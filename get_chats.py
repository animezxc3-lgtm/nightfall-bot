import os
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = os.getenv("VK_GROUP_ID")

if not TOKEN or not GROUP_ID:
    print("Ошибка: проверь VK_TOKEN и VK_GROUP_ID в файле .env")
    raise SystemExit(1)

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()

print("Подключение к VK...")
print("Ожидание сообщений. Для остановки нажми Ctrl+C.\n")

try:
    longpoll = VkBotLongPoll(vk_session, int(GROUP_ID))

    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            message = event.object.message

            peer_id = message.get("peer_id")
            text = message.get("text", "")
            from_id = message.get("from_id")

            if not peer_id or peer_id < 2000000000:
                continue

            try:
                result = vk.messages.getConversationsById(
                    peer_ids=[peer_id]
                )
                items = result.get("items", [])

                title = (
                    items[0].get("chat_settings", {}).get("title", "Без названия")
                    if items else "Название неизвестно"
                )
            except Exception as e:
                title = f"Не удалось получить название: {e}"

            try:
                users = vk.users.get(user_ids=[from_id])
                sender = (
                    f"{users[0]['first_name']} {users[0]['last_name']}"
                    if users else f"ID {from_id}"
                )
            except Exception:
                sender = f"ID {from_id}"

            print("-" * 50)
            print(f"Беседа: {title}")
            print(f"peer_id: {peer_id}")
            print(f"Участник: {sender} (ID {from_id})")
            print(f"Сообщение: {text}")
            print("-" * 50, flush=True)

except KeyboardInterrupt:
    print("\nМониторинг остановлен.")

except Exception as e:
    print(f"Ошибка: {e}")