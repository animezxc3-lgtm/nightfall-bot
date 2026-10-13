"""Работа с лайками на посты ВК."""

import re


PER_PAGE = 50  # сколько лайков на страницу


def parse_wall_url(url):
    """Извлекает owner_id и post_id из ссылки на пост."""
    m = re.search(r'wall(-?\d+)_(\d+)', url or '')
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def get_likes_page(vk, owner_id, post_id, page=1, per_page=PER_PAGE):
    """
    Возвращает:
        (user_ids, total, error)
    """
    offset = (page - 1) * per_page

    try:
        response = vk.likes.getList(
            type='post',
            owner_id=owner_id,
            item_id=post_id,
            count=per_page,
            offset=offset,
        )
    except Exception as e:
        return [], 0, f'Ошибка VK: {e}'

    if 'items' not in response:
        return [], 0, 'Не удалось получить лайки.'

    user_ids = response.get('items', [])
    total = response.get('count', 0)

    return user_ids, total, None