import random, re
from config import RP_ALBUMS, GROUP_ID


# Шаблоны только с {target}. Actor добавляется сверху в message_handlers.
RP_RESPONSES = {
    'обнять': ['обнял(а) {target} 🤗', 'крепко обнял(а) {target} ❤️'],
    'поцеловать': ['поцеловал(а) {target} 😘', 'поцеловал(а) {target} ❤️'],
    'пожать руку': ['пожал(а) руку {target} 🤝', 'обменялся(ась) рукопожатием с {target} 🤝'],
    'погладить': ['погладил(а) {target} по голове 🥰', 'нежно погладил(а) {target} 🤗'],
    'ущипнуть': ['ущипнул(а) {target} 😈', 'ущипнул(а) {target} за щёку 🤭'],
    'укусить': ['укусил(а) {target} 🦷', 'легонько укусил(а) {target} 😈'],
    'дать пять': ['дал(а) пять {target} ✋', 'и {target} дали пять 🖐️'],
    'пнуть': ['пнул(а) {target} 🦵'],
    'положить в дурку': ['положил(а) {target} в дурку 🏥'],
    'посадить на бутылку': ['посадил(а) {target} на бутылку 😈'],
    'застрелить': ['застрелил(а) {target} 🔫', 'пристрелил(а) {target} 💥'],
    'курить': ['закурил(а) вместе с {target} 🚬', 'и {target} дымят в сторонке 🚬'],
    'пиво': ['выпил(а) пиво с {target} 🍺', 'и {target} распили бутылочку 🍺'],
    'уснуть': ['уснул(а) рядом с {target} 😴'],
    'разбудить': ['разбудил(а) {target} ⏰'],
    'накормить': ['накормил(а) {target} 🍲'],
    'подарить': ['подарил(а) {target} подарок 🎁'],
}


SELF_RESPONSES = {
    'обнять': 'обнял(а) себя. Всё так плохо?',
    'поцеловать': 'поцеловал(а) себя. Ох уж эти самовлюблённые...',
    'пожать руку': 'пожал(а) руку самому себе. Отличный приятель.',
    'погладить': 'погладил(а) себя. Хороший мальчик.',
    'ущипнуть': 'ущипнул(а) себя. Ну как? Думаешь, спишь?',
    'укусить': 'укусил(а) себя. Но с какой целью..?',
    'дать пять': 'дал(а) себе пять. Отличная работа!',
    'пнуть': 'пнул(а) себя. Приятно?',
    'положить в дурку': 'лёг в дурку. Осознание проблемы — первый шаг к её решению.',
    'посадить на бутылку': 'сел на бутылку. Похоже, он доволен новым местом.',
    'застрелить': 'застрелился. Ну ты и псих.',
    'курить': 'закурил(а) в одиночестве. Дым развеется — и ладно.',
    'пиво': 'выпил(а) пиво в одиночестве. Похоже, компания — это не его.',
    'уснуть': 'уснул(а). Завтра его ждут великие дела.',
    'разбудить': 'каким-то чудом разбудил(а) себя. Каковы ощущения?',
    'накормить': 'накормил(а) себя. Пожелаем ему приятного аппетита!',
    'подарить': 'сделал(а) себе подарок. Интересно, что же он выбрал?',
}


def get_random_photo_from_album(vk, album_id):
    try:
        photos = vk.photos.get(owner_id=-GROUP_ID, album_id=album_id, count=50)['items']
        if photos:
            return max(random.choice(photos)['sizes'], key=lambda x: x['width'] * x['height'])['url']
    except Exception as e:
        print('⚠️ RP photo:', e)
    return None


def _extract_target_id(text):
    if not text:
        return None
    m = re.search(r'\[id(\d+)\|', text)
    if m:
        return int(m.group(1))
    m = re.search(r'@id(\d+)', text)
    if m:
        return int(m.group(1))
    m = re.search(r'\b(\d{3,15})\b', text)
    return int(m.group(1)) if m else None


def _mention(uid, fallback='пользователь'):
    from relationships import get_display_name
    name = get_display_name(uid) or fallback
    return f'[id{uid}|{name}]'


def handle_rp_command(command, user_id, peer_id, vk, text, get_user):
    target = _extract_target_id(text)
    actor = _mention(user_id, 'пользователь')

    if target is None or target == user_id:
        if target == user_id:
            return '❌ Нельзя использовать это действие на самого себя.', None
        template = SELF_RESPONSES.get(command)
        if not template:
            return None, None
        return template, None

    if not get_user(target):
        return '❌ У пользователя нет профиля.', None

    target_mention = _mention(target, 'пользователь')
    templates = RP_RESPONSES.get(command)
    if not templates:
        return None, None
    body = random.choice(templates).format(target=target_mention)
    # actor добавляется сверху в _send
    result = f'{body}'
    photo = get_random_photo_from_album(vk, RP_ALBUMS.get(command)) if RP_ALBUMS.get(command) else None
    return result, photo