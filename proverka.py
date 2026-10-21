import sqlite3
import vk_api
from config import TOKEN

# Подключаемся к VK
vk = vk_api.VkApi(token=TOKEN).get_api()

# Подключаемся к БД
conn = sqlite3.connect("data/bot.db")
cur = conn.cursor()
cur.execute("SELECT peer_id FROM chat_settings ORDER BY peer_id")
peer_ids = [row[0] for row in cur.fetchall()]
conn.close()

if not peer_ids:
    print("Беседы не найдены.")
    exit()

# Получаем названия
try:
    data = vk.messages.getConversationsById(
        peer_ids=','.join(map(str, peer_ids))
    ).get('items', [])
except Exception as e:
    print(f"Ошибка VK: {e}")
    exit()

for item in data:
    pid = item['peer']['id']
    title = item.get('chat_settings', {}).get('title', '(без названия)')
    print(f"peer_id={pid} — {title}")