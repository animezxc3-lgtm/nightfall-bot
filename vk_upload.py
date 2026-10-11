"""Загрузка фото в VK."""

import requests


def upload_photo(vk, photo_path, peer_id):
    """
    Загружает фото в VK и возвращает attachment.
    """
    try:
        server = vk.photos.getMessagesUploadServer(peer_id=peer_id)
        upload_url = server['upload_url']
    except Exception as e:
        print(f'Не удалось получить сервер загрузки: {e}')
        return None

    try:
        with open(photo_path, 'rb') as f:
            response = requests.post(
                upload_url,
                files={'photo': ('wheel.png', f, 'image/png')}
            ).json()
    except Exception as e:
        print(f'Не удалось загрузить фото: {e}')
        return None

    try:
        saved = vk.photos.saveMessagesPhoto(
            photo=response['photo'],
            server=response['server'],
            hash=response['hash'],
        )[0]
        return f"photo{saved['owner_id']}_{saved['id']}"
    except Exception as e:
        print(f'Не удалось сохранить фото: {e}')
        return None