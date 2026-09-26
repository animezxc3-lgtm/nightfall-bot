"""Логика заявок на администратора."""
import time
import json
from datetime import datetime, timedelta

from config import (
    APPLICATIONS_PEER_ID, APPLICATION_COOLDOWN_DAYS,
    APPLICATION_TIMEOUT_MINUTES, APPLICATION_MIN_DELAY_SECONDS,
)
from database import (
    get_application, upsert_application, delete_application,
    set_application_cooldown, get_application_cooldown,
    is_in_admin_blacklist, get_global_role,
    db_cursor,
)
from keyboards import application_review_keyboard


QUESTIONS = [
    'Ваше имя?',
    'Ваша фамилия?',
    'Ваш возраст?',
    'В какой беседе вы хотите стать администратором?',
    'Сколько времени готовы уделять проекту?',
    'Почему хотите стать администратором?',
    'Был ли у вас опыт администрирования? Если да, то опишите подробнее.',
    'Что такое флуд и спам?',
    'В беседе возник конфликт. Каковы будут ваши действия, если не получится урегулировать ситуацию?',
    'Что будете делать, если участник скинул в беседу картинку, относящуюся к 18+ контенту?',
]


_EMOJI_DIGITS = {
    '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
    '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣',
}


def _num(n):
    if n == 10:
        return '🔟'
    return ''.join(_EMOJI_DIGITS[d] for d in str(n))


def _validate_name(text):
    text = text.strip()
    if not (2 <= len(text) <= 30):
        return False, 'Имя должно быть от 2 до 30 символов.'
    if not all(ch.isalpha() or ch in "- " for ch in text):
        return False, 'Имя должно содержать только буквы, пробел или дефис.'
    return True, ''


def _validate_surname(text):
    text = text.strip()
    if not (2 <= len(text) <= 30):
        return False, 'Фамилия должна быть от 2 до 30 символов.'
    if not all(ch.isalpha() or ch in "- " for ch in text):
        return False, 'Фамилия должна содержать только буквы, пробел или дефис.'
    return True, ''


def _validate_default(text):
    if not text or len(text.strip()) < 1:
        return False, 'Ответ не может быть пустым.'
    return True, ''


def validate_answer(step, text):
    if step == 0:
        return _validate_name(text)
    if step == 1:
        return _validate_surname(text)
    return _validate_default(text)


def _timeout_expired(app):
    try:
        updated = datetime.strptime(app['updated_at'], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return False
    return datetime.now() - updated > timedelta(minutes=APPLICATION_TIMEOUT_MINUTES)


def _vk_name(vk, uid):
    try:
        info = vk.users.get(user_ids=uid)[0]
        return f"{info.get('first_name','')} {info.get('last_name','')}".strip()
    except Exception:
        return 'Пользователь'


def start_application(user_id, vk):
    app = get_application(user_id)
    if app and app['state'] == 'in_progress':
        if not _timeout_expired(app):
            return 'У тебя уже есть активная заявка. Продолжай отвечать на вопросы или напиши `лл отмена`.'
        delete_application(user_id)
        return 'Твоя прошлая заявка была сброшена из-за долгого отсутствия. Начни заново: `лл заявка`.'

    if is_in_admin_blacklist(user_id):
        return 'Ты в чёрном списке администрации. Подача заявки невозможна.'

    cd = get_application_cooldown(user_id)
    if cd:
        delta = cd - datetime.now()
        days = delta.days
        hours = delta.seconds // 3600
        if days > 0:
            return f'Ты сможешь подать новую заявку через {days} д. {hours} ч.'
        return f'Ты сможешь подать новую заявку через {hours} ч.'

    if get_global_role(user_id) > 0:
        return 'Ты уже состоишь в администрации проекта.'
    with db_cursor() as (_, c):
        r = c.execute("SELECT 1 FROM admin_chat_rights WHERE user_id=? AND level>0 LIMIT 1", (user_id,)).fetchone()
    if r:
        return

    upsert_application(user_id, 'in_progress', 0, [])
    return (
        '📋 Заявка на администратора\n\n'
        'Я задам 10 вопросов. Отвечай на каждый отдельным сообщением.\n\n'
        '❗ Принимается ТОЛЬКО 1 ОТВЕТ НА ПОСТАВЛЕННЫЙ ВОПРОС.\n'
        'Если отправишь несколько — зачтётся первый, остальные проигнорирую.\n\n'
        'Чтобы прервать — напиши `лл отмена`.\n\n'
        '━━━━━━━━━━━━━━━\n\n'
        f'{_num(1)} {QUESTIONS[0]}'
    )


def handle_dm_message(user_id, text, vk):
    app = get_application(user_id)
    if not app or app['state'] != 'in_progress':
        return False

    if _timeout_expired(app):
        delete_application(user_id)
        vk.messages.send(
            peer_id=user_id, random_id=0,
            message='Твоя заявка была сброшена из-за долгого отсутствия.\nНачни заново: `лл заявка`.',
            disable_mentions=True,
        )
        return True

    text = (text or '').strip()
    if not text:
        return True

    step = app['current_step']
    answers = list(app['answers'])

    ok, err = validate_answer(step, text)
    if not ok:
        vk.messages.send(
            peer_id=user_id, random_id=0,
            message=f'{err}\n\n{_num(step+1)} {QUESTIONS[step]}',
            disable_mentions=True,
        )
        return True

    answers.append(text)
    step += 1

    time.sleep(APPLICATION_MIN_DELAY_SECONDS)

    if step >= len(QUESTIONS):
        upsert_application(user_id, 'sent', step, answers)
        send_to_review(user_id, answers, vk)
        vk.messages.send(
            peer_id=user_id, random_id=0,
            message='Спасибо! Твоя заявка отправлена на рассмотрение.\n\nОтвет придёт в личные сообщения в течение 24 часов.',
            disable_mentions=True,
        )
        return True

    upsert_application(user_id, 'in_progress', step, answers)
    vk.messages.send(
        peer_id=user_id, random_id=0,
        message=f'Принято.\n\n{_num(step+1)} {QUESTIONS[step]}',
        disable_mentions=True,
    )
    return True


def cancel_application(user_id, vk):
    app = get_application(user_id)
    if not app or app['state'] != 'in_progress':
        vk.messages.send(
            peer_id=user_id, random_id=0,
            message='У тебя нет активной заявки.',
            disable_mentions=True,
        )
        return
    delete_application(user_id)
    vk.messages.send(
        peer_id=user_id, random_id=0,
        message='Заявка отменена. Ты можешь подать новую командой `лл заявка`.',
        disable_mentions=True,
    )


def send_to_review(user_id, answers, vk):
    applicant_name = _vk_name(vk, user_id)
    lines = [
        '📩 Новая заявка на администратора',
        f'👤 [id{user_id}|{applicant_name}]',
        f'📅 {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        '━━━━━━━━━━━━━━━',
    ]
    for i, (q, a) in enumerate(zip(QUESTIONS, answers), 1):
        lines.append(f'{_num(i)} {q}')
        lines.append(f'▸ {a}')
        lines.append('')
    lines.append('━━━━━━━━━━━━━━━')
    lines.append('Принять или отклонить заявку:')

    text = '\n'.join(lines)
    try:
        result = vk.messages.send(
            peer_id=APPLICATIONS_PEER_ID,
            random_id=0,
            message=text,
            keyboard=json.dumps(application_review_keyboard(user_id), ensure_ascii=False),
            disable_mentions=True,
        )
    except Exception as e:
        print(f'Не удалось отправить заявку в беседу: {e}')
        return

    cmid = None
    try:
        if isinstance(result, int):
            info = vk.messages.getById(message_ids=result)
            items = info.get('items') or []
            if items:
                cmid = items[0].get('conversation_message_id')
    except Exception as e:
        print(f'Не удалось получить cmid заявки: {e}')

    upsert_application(user_id, 'sent', len(QUESTIONS), answers, APPLICATIONS_PEER_ID, cmid)


def review_application(applicant_id, reviewer_id, decision, vk, cmid):
    app = get_application(applicant_id)
    if not app or app['state'] != 'sent':
        return 'Заявка уже обработана или неактуальна.'

    applicant_name = _vk_name(vk, applicant_id)
    reviewer_name = _vk_name(vk, reviewer_id)

    if decision == 'accept':
        final = (
            f'📩 Заявка от [id{applicant_id}|{applicant_name}]\n\n'
            f'Принята администратором [id{reviewer_id}|{reviewer_name}].'
        )
        upsert_application(applicant_id, 'accepted', app['current_step'], app['answers'],
                           app['review_peer_id'], app['review_msg_id'])
    else:
        final = (
            f'📩 Заявка от [id{applicant_id}|{applicant_name}]\n\n'
            f'Отклонена администратором [id{reviewer_id}|{reviewer_name}].'
        )
        upsert_application(applicant_id, 'declined', app['current_step'], app['answers'],
                           app['review_peer_id'], app['review_msg_id'])
        set_application_cooldown(applicant_id, APPLICATION_COOLDOWN_DAYS)

    if cmid is not None:
        try:
            vk.messages.edit(
                peer_id=APPLICATIONS_PEER_ID,
                conversation_message_id=cmid,
                message=final,
                keyboard=json.dumps({'inline': True, 'buttons': []}, ensure_ascii=False),
                disable_mentions=True,
            )
        except Exception as e:
            print(f'Не удалось отредактировать сообщение заявки: {e}')

    if decision == 'accept':
        msg = 'Поздравляем! Твоя заявка на администратора принята.\nОжидай дальнейших указаний от старшей администрации.'
    else:
        msg = f'К сожалению, твоя заявка на администратора отклонена.\nТы сможешь подать новую через {APPLICATION_COOLDOWN_DAYS} дня.'
    try:
        vk.messages.send(peer_id=applicant_id, random_id=0, message=msg, disable_mentions=True)
    except Exception as e:
        print(f'Не удалось уведомить {applicant_id}: {e}')

    return 'ok'