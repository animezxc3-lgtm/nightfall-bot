import re
from database import *

MAX_CHILDREN=5

def profile_link(uid):
    name=get_display_name(uid) or 'Пользователь'
    return f'https://vk.com/id{uid} ({name})'

def parse_target_id(text):
    m=re.search(r'\[id(\d+)\|[^\]]+\]',text or '')
    if m:return int(m.group(1))
    m=re.search(r'(?:id)?(\d{3,15})',text or '')
    return int(m.group(1)) if m else None

def _row(uid):
    with db_cursor() as (_,c): c.execute('SELECT partner_id,married,family_surname FROM relationships WHERE user_id=?',(uid,)); return c.fetchone()
def get_partner_id(uid): r=_row(uid); return r[0] if r else None
def get_family_surname(uid): r=_row(uid); return r[2] if r else ''
def get_display_name(uid):
    u=get_user(uid)
    if not u:return None
    base=u[2] or (u[1].split()[0] if u[1] else f'пользователь {uid}')
    surname=get_family_surname(uid)
    return f'{base} {surname}'.strip() if surname else base

def get_children(uid):
    with db_cursor() as (_,c): c.execute('SELECT child_id FROM family_children WHERE parent_id=? ORDER BY id',(uid,)); return [r[0] for r in c.fetchall()]
def get_parents(uid):
    with db_cursor() as (_,c): c.execute('SELECT parent_id FROM family_children WHERE child_id=? ORDER BY id',(uid,)); return [r[0] for r in c.fetchall()]

def start_relationship(uid,target,vk=None):
    if not target or target==uid:return False,'Нельзя начать отношения с самим собой.'
    if get_partner_id(uid) or get_partner_id(target):return False,'Один из пользователей уже состоит в отношениях.'
    create_relationship_proposal(target,uid); return True,f'❤️ {profile_link(uid)} предлагает тебе начать отношения!'

def accept_relationship(target):
    p=get_relationship_proposal(target)
    if not p:return 'Для тебя нет действующего предложения отношений.'
    proposer=p[0]
    if get_partner_id(target) or get_partner_id(proposer): delete_relationship_proposal(target); return 'Предложение больше недействительно.'
    with db_cursor(True) as (_,c):
        c.execute('UPDATE relationships SET partner_id=? WHERE user_id=?',(target,proposer)); c.execute('UPDATE relationships SET partner_id=? WHERE user_id=?',(proposer,target))
    delete_relationship_proposal(target); return '❤️ Согласие принято! Теперь вы состоите в отношениях.'

def reject_relationship(target):
    p=get_relationship_proposal(target)
    if not p:return 'Предложение больше недействительно.'
    delete_relationship_proposal(target); return '💔 Предложение отклонено.'

def end_relationship(uid):
    partner=get_partner_id(uid)
    if not partner:return 'У тебя нет партнёра.'
    with db_cursor(True) as (_,c): c.execute("UPDATE relationships SET partner_id=NULL,married=0,family_surname='' WHERE user_id IN (?,?)",(uid,partner))
    return '💔 Вы больше не состоите в отношениях. Брак и фамилия семьи расторгнуты.'

def propose_marriage(uid,target,surname):
    if get_partner_id(uid)!=target or get_partner_id(target)!=uid:return False,'Сначала начните отношения друг с другом.'
    r=_row(uid)
    if r and r[1]:return False,'Вы уже состоите в браке.'
    if not 1<=len(surname)<=30:return False,'Фамилия должна быть от 1 до 30 символов.'
    create_marriage_proposal(target,uid,surname); return True,f'💍 {profile_link(uid)} делает тебе предложение руки и сердца!'

def accept_marriage(target):
    p=get_marriage_proposal(target)
    if not p:return 'У тебя нет ожидающего предложения брака.'
    proposer,surname,_=p
    if get_partner_id(target)!=proposer or get_partner_id(proposer)!=target: delete_marriage_proposal(target); return 'Предложение больше недействительно.'
    with db_cursor(True) as (_,c): c.execute('UPDATE relationships SET married=1,family_surname=? WHERE user_id IN (?,?)',(surname,target,proposer))
    delete_marriage_proposal(target); return f'💍 Согласие принято! Теперь вы семья с фамилией «{surname}».'

def reject_marriage(target):
    if not get_marriage_proposal(target):return 'У тебя нет ожидающего предложения брака.'
    delete_marriage_proposal(target); return '💔 Предложение брака отклонено.'

def divorce(uid): return end_relationship(uid) if get_partner_id(uid) else 'У тебя нет супруга/супруги.'

def adopt(parent,child,vk=None):
    if len(get_children(parent))>=MAX_CHILDREN:return False,'В семье уже 5 детей.'
    parents=get_parents(child)
    if len(parents)>=2:return False,'У данного пользователя уже есть родители.'
    create_family_proposal(child,parent,'ребёнок'); return True,f'👪 {profile_link(parent)} предлагает тебе стать членом семьи.'

def accept_family_addition(child):
    p=get_family_proposal(child)
    if not p:return 'У тебя нет действующего предложения вступить в семью.'
    parent,relation,_=p
    if len(get_children(parent))>=MAX_CHILDREN or len(get_parents(child))>=2: delete_family_proposal(child); return 'Предложение больше недействительно.'
    with db_cursor(True) as (_,c): c.execute('INSERT INTO family_children(parent_id,child_id) VALUES(?,?) ON CONFLICT DO NOTHING',(parent,child))
    delete_family_proposal(child); return '👪 Согласие принято! Ты добавлен(а) в семью.'

def reject_family_addition(child):
    if not get_family_proposal(child):return 'У тебя нет действующего предложения вступить в семью.'
    delete_family_proposal(child); return '💔 Предложение вступить в семью отклонено.'

def relinquish(parent,child,vk=None):
    if child not in get_children(parent):return ''
    with db_cursor(True) as (_,c): c.execute('DELETE FROM family_children WHERE child_id=?',(child,))
    return '🏠 Ребёнок больше не числится в семье.'

def leave_family(uid):
    if not get_parents(uid):return 'Ты не состоишь ни в одной семье.'
    with db_cursor(True) as (_,c): c.execute('DELETE FROM family_children WHERE child_id=?',(uid,))
    return '🚪 Ты ушёл/ушла из семьи.'

def relationship_status(uid,vk=None):
    p=get_partner_id(uid); r=_row(uid); married=bool(r and r[1]); surname=get_family_surname(uid); children=get_children(uid); parents=get_parents(uid)
    return f"❤️ Партнёр: {profile_link(p) if p else 'Нет'}\n💍 Брак: {'да' if married else 'нет'}\n👤 Фамилия семьи: {surname or 'не установлена'}\n👪 Родителей: {len(parents)}\n🧒 Детей: {len(children)}/{MAX_CHILDREN}"