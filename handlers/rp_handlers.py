import random, re
from config import RP_ALBUMS, GROUP_ID


RP_RESPONSES = {
    'обнять': ['{actor} обнял(а) {target} 🤗', '{actor} крепко обнял(а) {target} ❤️'],
    'поцеловать': ['{actor} поцеловал(а) {target} 😘', '{actor} поцеловал(а) {target} ❤️'],
    'пожать руку': ['{actor} пожал(а) руку {target} 🤝', '{actor} и {target} обменялись рукопожатием 🤝'],
    'погладить': ['{actor} погладил(а) {target} по голове 🥰', '{actor} нежно погладил(а) {target} 🤗'],
    'ущипнуть': ['{actor} ущипнул(а) {target} 😈', '{actor} ущипнул(а) {target} за щёку 🤭'],
    'укусить': ['{actor} укусил(а) {target} 🦷', '{actor} легонько укусил(а) {target} 😈'],
    'дать пять': ['{actor} дал(а) пять {target} ✋', '{actor} и {target} дали пять 🖐️'],
    'пнуть': ['{actor} пнул(а) {target} 🦵'],
    'положить в дурку': ['{actor} положил(а) {target} в дурку 🏥'],
    'посадить на бутылку': ['{actor} посадил(а) {target} на бутылку 😈'],
    'застрелить': ['{actor} застрелил(а) {target} 🔫', '{actor} пристрелил(а) {target} 💥'],
    'курить': ['{actor} закурил(а) вместе с {target} 🚬', '{actor} и {target} дымят в сторонке 🚬'],
    'пиво': ['{actor} выпил(а) пиво с {target} 🍺', '{actor} и {target} распили бутылочку 🍺'],
    'уснуть': ['{actor} уснул(а) рядом с {target} 😴'],
    'разбудить': ['{actor} разбудил(а) {target} ⏰'],
    'накормить': ['{actor} накормил(а) {target} 🍲'],
    'подарить': ['{actor} подарил(а) {target} подарок 🎁'],
}


SELF_RESPONSES = {
    'обнять': '{actor} обнял(а) себя. Всё так плохо?',
    'поцеловать': '{actor} поцеловал(а) себя. Ох уж эти самовлюблённые...',
    'пожать руку': '{actor} пожал(а) руку самому себе. Отличный приятель.',
    'погладить': '{actor} погладил(а) себя. Хороший мальчик.',
    'ущипнуть': '{actor} ущипнул(а) себя. Ну как? Думаешь, спишь?',
    'укусить': '{actor} укусил(а) себя. Но с какой целью..?',
    'дать пять': '{actor} дал(а) себе пять. Отличная работа!',
    'пнуть': '{actor} пнул(а) себя. Приятно?',
    'положить в дурку': '{actor} лёг в дурку. Осознание проблемы — первый шаг к её решению.',
    'посадить на бутылку': '{actor} сел на бутылку. Похоже, он доволен новым местом.',
    'застрелить': '{actor} застрелился. Ну ты и псих.',
    'курить': '{actor} закурил(а) в одиночестве. Дым развеется — и ладно.',
    'пиво': '{actor} выпил(а) пиво в одиночестве. Похоже, компания — это не его.',
    'уснуть': '{actor} уснул(а). Завтра его ждут великие дела.',
    'разбудить': '{actor} каким-то чудом разбудил(а) себя. Каковы ощущения?',
    'накормить': '{actor} накормил(а) себя. Пожелаем ему приятного аппетита!',
    'подарить': '{actor} сделал(а) себе подарок. Интересно, что же он выбрал?',
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
        return template.format(actor=actor), None

    if not get_user(target):
        return '❌ У пользователя нет профиля.', None

    target_mention = _mention(target, 'пользователь')
    templates = RP_RESPONSES.get(command)
    if not templates:
        return None, None
    result = random.choice(templates).format(actor=actor, target=target_mention)
    photo = get_random_photo_from_album(vk, RP_ALBUMS.get(command)) if RP_ALBUMS.get(command) else None
    return result, photo