PROFESSIONS = {
    'шлюха': {
        'name': '🍆 Шлюха',
        'levels': [
            'Подзаборная',
            'Работница вокзала',
            'Элитная путана',
            'Содержанка',
            'Любовница олигарха',
            'Онлифанс модель',
        ],
    },
    'алкаш': {
        'name': '🍺 Алкаш',
        'levels': [
            'Собутыльник',
            'Постоянный клиент',
            'Знаток «Боярышника»',
            'Легенда двора',
            'Душа компании',
            'Король пивной',
        ],
    },
    'тиммейт': {
        'name': '🎯 Тиммейт из ада',
        'levels': [
            'Рандом',
            'Токсик',
            'АФК',
            'Фидлер',
            'ММР-судья',
            'Счёт 4/11',
        ],
    },
    'врач': {
        'name': '🩺 Врач',
        'levels': [
            'Медик-стажёр',
            'Интерн',
            'Доктор',
            'Специалист',
            'Ведущий доктор',
            'Главный доктор',
        ],
    },
    'вор': {
        'name': '🥷 Вор',
        'levels': [
            'Карманник',
            'Домушник',
            'Грабитель',
            'Профессионал',
            'Авторитет',
            'Вор в законе',
        ],
    },
}

SALARIES = [10000, 20000, 30000, 40000, 50000, 60000]
PROMOTION_DAYS = 14


def get_profession_list():
    return list(PROFESSIONS)


def get_profession_name(key):
    return PROFESSIONS.get(key, {}).get('name', key)


def get_level_name(key, index):
    levels = PROFESSIONS.get(key, {}).get('levels', [])
    return levels[index] if 0 <= index < len(levels) else 'Неизвестная ступень'


def get_salary(index):
    return SALARIES[index] if 0 <= index < len(SALARIES) else 0


def get_max_level():
    return len(SALARIES) - 1