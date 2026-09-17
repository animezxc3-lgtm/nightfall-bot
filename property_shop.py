PROPERTY_ITEMS = {
    "housing": [
        ("Изба на два хозяина", 15000, "🏚️"),
        ("Коробка с ремонтом", 30000, "🧱"),
        ("Комната в коммуналке", 50000, "🚪"),
        ("Муравейник", 80000, "🏢"),
        ("Барак имени себя", 110000, "🏚️"),
        ("Дом, который построил Вася", 150000, "🏠"),
        ("Замок последнего босса", 225000, "🏰"),
        ("Пентхаус на кредитке", 750000, "🌆"),
        ("Остров миллиардеров", 3750000, "🏝️"),
    ],
    "car": [
        ("ВАЗ «Доеду — не доеду»", 25000, "🛠️"),
        ("Приора боярина", 40000, "🚗"),
        ("Жигули дедушки", 55000, "🚗"),
        ("Таз", 70000, "🚗"),
        ("Тазик с характером", 90000, "🚗"),
        ("Корч", 100000, "🚗"),
        ("Камри-авторитет", 150000, "🚗"),
        ("Octavia таксиста", 140000, "🚗"),
        ("Тачка с Авито", 180000, "🚗"),
        ("Машина соседа", 225000, "🚗"),
        ("БМВ на последние деньги", 375000, "🚗"),
        ("Приора с сабвуфером", 450000, "🚗"),
        ("Болид Формулы-1", 1500000, "🏎️"),
        ("Batmobile", 3750000, "🦇"),
        ("DeLorean", 7500000, "🚗"),
    ],
    "phone": [
        ("Nokia из 2007-го", 5000, "📱"),
        ("Телефон мамы", 10000, "📱"),
        ("Кирпич", 15000, "📱"),
        ("Телефон с трещиной", 22500, "📱"),
        ("Redmi с рекламой", 35000, "📱"),
        ("Айфон в кредит", 50000, "📱"),
        ("iPhone «зарядка отдельно»", 60000, "📱"),
        ("Nokia 3310 — бессмертный", 75000, "📱"),
        ("Калькулятор с SIM-картой", 112500, "📱"),
        ("Geass Phone", 225000, "📱"),
        ("Death Note Phone", 375000, "📱"),
        ("Телефон Лелуша", 750000, "📱"),
    ],
}

CATEGORY_NAMES = {
    "housing": "🏠 Жильё",
    "car": "🚗 Автомобили",
    "phone": "📱 Телефоны",
}

CATEGORY_DB_FIELDS = {
    "housing": "housing",
    "car": "car",
    "phone": "phone",
}


def get_items(category):
    return PROPERTY_ITEMS.get(category, [])


def find_item(category, name):
    for item_name, price, emoji in get_items(category):
        if item_name.lower() == name.strip().lower():
            return {"name": item_name, "price": price, "emoji": emoji, "category": category}
    return None


def format_price(amount):
    return f"{amount:,}".replace(",", " ")


def shop_text():
    return (
        "🛒 **Магазин имущества**\n\n"
        "Выбери категорию:\n"
        "🏠 Жильё\n"
        "🚗 Автомобили\n"
        "📱 Телефоны\n\n"
        "Покупка заменяет имущество той же категории."
    )


def category_text(category):
    items = get_items(category)
    if not items:
        return "❌ Категория не найдена."
    lines = [f"{CATEGORY_NAMES[category]}\n"]
    for i, (name, price, emoji) in enumerate(items, 1):
        lines.append(f"{i}. {emoji} {name} — {format_price(price)} 🪙")
    lines.append("\n💡 Покупка: `лл дом <номер>`, `лл машина <номер>` или `лл телефон <номер>`.")
    return "\n".join(lines)


def buy_property(user_id, category, item_name):
    from database import get_user, purchase_property
    item = find_item(category, item_name)
    if not item:
        return False, "❌ Такой предмет не найден."
    user = get_user(user_id)
    if not user:
        return False, "❌ Профиль не найден."
    current = user[8] if category == "housing" else user[9] if category == "car" else user[10]
    if current != 'Отсутствует':
        return False, f"❌ У тебя уже есть имущество этой категории: {current}. Сначала продай его."
    if user[4] < item["price"]:
        return False, (
            f"❌ Недостаточно монет.\n"
            f"Цена: {format_price(item['price'])} 🪙\n"
            f"Твой баланс: {format_price(user[4])} 🪙"
        )
    ok = purchase_property(user_id, category, item["name"], item["price"])
    if not ok:
        return False, "❌ Не удалось совершить покупку. Попробуй ещё раз."
    return True, (
        f"✅ Покупка совершена!\n"
        f"{item['emoji']} {item['name']}\n"
        f"💰 Потрачено: {format_price(item['price'])} 🪙"
    )