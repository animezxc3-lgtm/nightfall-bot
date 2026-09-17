import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('VK_TOKEN', 'YOUR_VK_TOKEN_HERE')
GROUP_ID = int(os.getenv('VK_GROUP_ID', '240896963'))
CREATOR_ID = int(os.getenv('CREATOR_ID', '750158017'))

# Команды в ЛС разрешены только для заявок
ALLOWED_IN_DM = {'заявка', 'отмена'}

# Беседа, в которую падают заявки на администратора
APPLICATIONS_PEER_ID = int(os.getenv('APPLICATIONS_PEER_ID', '2000000011'))
# Ссылки для закрепа
PIN_COMMUNITY_LINK = 'https://vk.ru/nightfa11'
PIN_RULES_LINK = 'https://vk.ru/@nightfa11-osnovnye-polozheniya-i-pravila-proekta'
PIN_MENU_LINK = 'https://vk.ru/@nightfa11'
PIN_CASINO_LINK = 'https://vk.me/join/AZQ1d_4fuybFrKCTIpJBVO0Y'
PIN_ANARCHY_LINK = 'https://vk.me/join/AZQ1dz_85ybXLVjKd6O3v2QJ'

# Заявки
APPLICATION_COOLDOWN_DAYS = 3
APPLICATION_TIMEOUT_MINUTES = 30
APPLICATION_MIN_DELAY_SECONDS = 1  # задержка перед след. вопросом

PROFILE_WELCOME_ALBUM_ID = 314239613
PROFILE_WELCOME_ALBUM_OWNER = -240896963

RP_ALBUMS = {
    'обнять': 314310270, 'поцеловать': 314310277, 'пожать руку': 314310278,
    'погладить': 314310281, 'ущипнуть': 314310285, 'укусить': 314310286,
    'дать пять': 314310289, 'пнуть': 314310291, 'положить в дурку': 314310292, 'посадить на бутылку': 314310296, 'уснуть': 314310297,
    'разбудить': 314310299, 'накормить': 314310300, 'подарить': 314310301,
}