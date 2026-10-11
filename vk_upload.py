"""Загрузка фото в VK."""

import requests


def upload_photo(vk, photo_path, peer_id, max_retries=3):
    """
    Загружает фото в VK с 3 попытками.
    """
    for attempt in range(1, max_retries + 1):
        try:
            server = vk.photos.getMessagesUploadServer(peer_id=peer_id)
            upload_url = server['upload_url']
        except Exception as e:
            print(f'[{attempt}] Не удалось получить сервер загрузки: {e}')
            continue

        try:
            with open(photo_path, 'rb') as f:
                response = requests.post(
                    upload_url,
                    files={'photo': ('wheel.png', f, 'image/png')},
                    timeout=15,
                ).json()
        except Exception as e:
            print(f'[{attempt}] Не удалось загрузить фото: {e}')
            continue

        # Проверяем ответ
        if not response.get('photo'):
            print(f'[{attempt}] VK не вернул photo: {response}')
            continue

        try:
            saved = vk.photos.saveMessagesPhoto(
                photo=response['photo'],
                server=response['server'],
                hash=response['hash'],
            )[0]
            return f"photo{saved['owner_id']}_{saved['id']}"
        except Exception as e:
            print(f'[{attempt}] Не удалось сохранить фото: {e}')
            continue

    print(f'Не удалось загрузить фото после {max_retries} попыток')
    return None