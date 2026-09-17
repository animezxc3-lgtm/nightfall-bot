# VKBot — SQLite version

Это версия VK-бота, переведённая с PostgreSQL на SQLite.

## Что изменено

- PostgreSQL больше не нужен.
- База автоматически создаётся в `data/bot.db`.
- Сохранены существующие таблицы и логика статистики.
- Подсчёт сообщений ведётся отдельно по пользователю и беседе.
- Еженедельная очистка использует статистику сообщений конкретной беседы.
- VK Long Poll оставлен без изменения по смыслу.
- Добавлены характерные реакции на отдельные слова/фразы:
  - `Британия` → `Британия падёт.`
  - `бублик` → `Кольцо без начала и конца. Интересно.`
  - `пингвин` → `Почему именно пингвин?..`
  - `кактус` → `Наконец-то растение, способное постоять за себя.`
  - `пельмени` → `Даже величайшие планы иногда уступают пельменям.`
  - `ход конём` → `Иногда лучший ход — тот, которого противник не предусмотрел.`
- Реакции не срабатывают на команды `лл ...`.
- Между реакциями в одной беседе установлен cooldown 30 секунд.

## Запуск на Windows

1. Установить Python.
2. Открыть терминал в папке `VKBot`.
3. Установить зависимости:

```bash
pip install -r requirements.txt
```

4. Открыть `.env` и указать:
   - `VK_TOKEN`
   - `VK_GROUP_ID`
   - `CREATOR_ID`

5. Запустить:

```bash
python main.py
```

При первом запуске будет создан `data/bot.db`.

## Запуск на VPS

Подойдёт обычный Linux VPS (Ubuntu/Debian).

```bash
sudo apt update
sudo apt install -y python3 python3-venv
cd /path/to/VKBot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Для постоянной работы рекомендуется systemd или другой менеджер процессов.

### systemd

Создай `/etc/systemd/system/vkbot.service`:

```ini
[Unit]
Description=VKBot
After=network.target

[Service]
WorkingDirectory=/path/to/VKBot
ExecStart=/path/to/VKBot/.venv/bin/python /path/to/VKBot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vkbot
sudo systemctl status vkbot
```

Логи:

```bash
journalctl -u vkbot -f
```

## Резервная копия

Основной файл базы:

```text
data/bot.db
```

Его стоит регулярно копировать. Например, простой вариант:

```bash
cp data/bot.db backups/bot-$(date +%F).db
```

Не храните токен VK в GitHub или публичных архивах.

## Важно про SQLite

SQLite хорошо подходит для одного экземпляра этого бота и умеренной нагрузки. Если позже бот будет работать в нескольких процессах/на нескольких серверах или нагрузка станет очень высокой, можно вернуть PostgreSQL без изменения VK Long Poll.
