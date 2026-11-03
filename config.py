import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('VK_TOKEN', 'YOUR_VK_TOKEN_HERE')
RP_PHOTO_TOKEN = os.getenv('RP_PHOTO_TOKEN', '').strip()
GROUP_ID = int(os.getenv('VK_GROUP_ID', '240896963'))
CREATOR_ID = int(os.getenv('CREATOR_ID', '750158017'))

ALLOWED_IN_DM = {'заявка', 'отмена', 'вип', 'настроить набор'}

# --- БЕСЕДЫ ---
# Основные (рассылка, чистка, дуэли только в выходные)
MAIN_CHATS = [2000000007, 2000000006, 2000000005, 2000000012, 2000000013, 2000000014]

# Дополнительные (Анархия - дуэли 24/7, Казино - разрешено казино)
ANARCHY_CHAT = 2000000008
CASINO_CHAT = 2000000009
EXTRA_CHATS = [ANARCHY_CHAT, CASINO_CHAT]

# Админские (Цитадель, Контроль, Заявки)
CITADEL_CHAT = 2000000004
CONTROL_CHAT = 2000000015
APPLICATIONS_PEER_ID = int(os.getenv('APPLICATIONS_PEER_ID', '2000000011'))

ADMIN_CHATS = [CITADEL_CHAT, CONTROL_CHAT, APPLICATIONS_PEER_ID]

ALL_BOT_CHATS = MAIN_CHATS + EXTRA_CHATS + ADMIN_CHATS

REPORT_CHAT_ID = CONTROL_CHAT

# Ссылки для закрепа
PIN_COMMUNITY_LINK = 'https://vk.ru/nightfa11'
PIN_RULES_LINK = 'https://vk.ru/@nightfa11-osnovnye-polozheniya-i-pravila-proekta'
PIN_CASINO_LINK = 'https://vk.me/join/AZQ1d_4fuybFrKCTIpJBVO0Y'
PIN_ANARCHY_LINK = 'https://vk.me/join/AZQ1dz_85ybXLVjKd6O3v2QJ'

# Заявки
APPLICATION_COOLDOWN_DAYS = 3
APPLICATION_TIMEOUT_MINUTES = 30
APPLICATION_MIN_DELAY_SECONDS = 1

PROFILE_WELCOME_ALBUM_ID = 314239613
PROFILE_WELCOME_ALBUM_OWNER = -240896963

RP_ALBUMS = {
    'обнять': 314310270, 'поцеловать': 314310277, 'пожать руку': 314310278,
    'погладить': 314310281, 'ущипнуть': 314310285, 'укусить': 314310286,
    'дать пять': 314310289, 'пнуть': 314310291, 'положить в дурку': 314310292, 'посадить на бутылку': 314310296, 'уснуть': 314310297,
    'разбудить': 314310299, 'накормить': 314310300, 'подарить': 314310301,
}