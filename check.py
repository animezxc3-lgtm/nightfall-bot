import vk_api
from config import TOKEN

vk = vk_api.VkApi(token=TOKEN).get_api()

try:
    info = vk.messages.getConversationsById(peer_ids=2000000103)
    print("Беседа:", info)
except Exception as e:
    print("Ошибка беседы:", e)

try:
    members = vk.messages.getConversationMembers(peer_id=2000000103)
    print("Участники:", members)
except Exception as e:
    print("Ошибка участников:", e)

try:
    r = vk.messages.send(peer_id=2000000103, random_id=0, message="тест из скрипта")
    print("Отправлено:", r)
except Exception as e:
    print("Ошибка отправки:", e)