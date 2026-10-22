"""SQLite storage for VKBot."""

from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3

DB_PATH = Path(__file__).resolve().parent / "data" / "bot.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_WELCOME = '👋 Добро пожаловать, {name}! Твой профиль создан.'

def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

@contextmanager
def db_cursor(commit=False):
    conn = _connect()
    try:
        cur = conn.cursor()
        if commit: cur.execute("BEGIN IMMEDIATE")
        yield conn, cur
        if commit: conn.commit()
    except Exception:
        if conn.in_transaction: conn.rollback()
        raise
    finally:
        conn.close()

def get_db():
    return _connect()

def _week_start(d):
    return d - timedelta(days=d.weekday())

def _month_start(d):
    return d.replace(day=1)

def migrate_database():
    with db_cursor(True) as (_, c):
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, nickname TEXT DEFAULT '',
            soul_gems INTEGER DEFAULT 0, power INTEGER DEFAULT 0, coins INTEGER DEFAULT 100,
            job TEXT DEFAULT 'Отсутствует', salary INTEGER DEFAULT 0, work_days INTEGER DEFAULT 0,
            housing TEXT DEFAULT 'Отсутствует', car TEXT DEFAULT 'Отсутствует', phone TEXT DEFAULT 'Отсутствует',
            role TEXT DEFAULT 'Участник', rights TEXT DEFAULT 'Участник', warnings INTEGER DEFAULT 0,
            admin_warnings INTEGER DEFAULT 0, join_date TEXT DEFAULT (CURRENT_DATE), messages_total INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0, job_level INTEGER DEFAULT 0, job_exp INTEGER DEFAULT 0,
            job_last_work TEXT, family_surname TEXT DEFAULT '', profile_image TEXT DEFAULT '',
            custom_role TEXT DEFAULT '', last_message_at TEXT, status TEXT DEFAULT '',
            gif_link TEXT DEFAULT '', salary_multiplier REAL DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS messages_stats (user_id INTEGER NOT NULL, date TEXT NOT NULL, count INTEGER DEFAULT 0, PRIMARY KEY(user_id, date));
        CREATE TABLE IF NOT EXISTS chat_message_stats (peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL, date TEXT NOT NULL, count INTEGER DEFAULT 0, PRIMARY KEY(peer_id, user_id, date));
        CREATE TABLE IF NOT EXISTS chat_settings (peer_id INTEGER PRIMARY KEY, welcome_message TEXT DEFAULT '', welcome_photo TEXT DEFAULT '', cleanup_enabled INTEGER DEFAULT 0, casino_enabled INTEGER DEFAULT 1, mute_enabled INTEGER DEFAULT 0, duel_enabled INTEGER DEFAULT 1, broadcast_enabled INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS relationships (user_id INTEGER PRIMARY KEY, partner_id INTEGER, married INTEGER DEFAULT 0, family_surname TEXT DEFAULT '', relationship_since TEXT);
        CREATE TABLE IF NOT EXISTS warning_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, peer_id INTEGER, is_admin_warning INTEGER DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin_chat_rights (peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL, level INTEGER NOT NULL, PRIMARY KEY(peer_id, user_id));
        CREATE TABLE IF NOT EXISTS chat_members (peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL, first_join_at TEXT NOT NULL, invited_by INTEGER, PRIMARY KEY(peer_id, user_id));
        CREATE TABLE IF NOT EXISTS global_roles (user_id INTEGER PRIMARY KEY, level INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS one_time_coin_grants (
            user_id INTEGER PRIMARY KEY,
            amount INTEGER NOT NULL DEFAULT 100000,
            granted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS coin_grant_scanned_chats (
            peer_id INTEGER PRIMARY KEY,
            scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS duels (opponent_id INTEGER PRIMARY KEY, challenger_id INTEGER NOT NULL, peer_id INTEGER NOT NULL, message_id INTEGER, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin_blacklist (user_id INTEGER PRIMARY KEY, added_by INTEGER NOT NULL, added_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS applications (user_id INTEGER PRIMARY KEY, state TEXT NOT NULL, current_step INTEGER DEFAULT 0, answers TEXT DEFAULT '[]', review_peer_id INTEGER, review_msg_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS application_cooldowns (user_id INTEGER PRIMARY KEY, until_ts TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chat_pins (peer_id INTEGER PRIMARY KEY, conversation_message_id INTEGER, message_id INTEGER, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS kick_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, peer_id INTEGER, kicked_by INTEGER, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS twinks (twink_id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, added_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin_weekly_stats (user_id INTEGER NOT NULL, week_key TEXT NOT NULL, messages INTEGER DEFAULT 0, invites INTEGER DEFAULT 0, reports INTEGER DEFAULT 0, gems_awarded INTEGER DEFAULT 0, PRIMARY KEY(user_id, week_key));
        CREATE TABLE IF NOT EXISTS hidden_chats (peer_id INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS power_message_rewards (user_id INTEGER PRIMARY KEY, claimed_thresholds INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS family_children (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            UNIQUE(parent_id, child_id)
        );
        CREATE TABLE IF NOT EXISTS relationship_proposals (
            target_id INTEGER PRIMARY KEY,
            proposer_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS marriage_proposals (
            target_id INTEGER PRIMARY KEY,
            proposer_id INTEGER NOT NULL,
            surname TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS family_proposals (
            target_id INTEGER PRIMARY KEY,
            proposer_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chat_weekly_message_totals (
            peer_id INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY(peer_id, week_start, user_id)
        );
        CREATE TABLE IF NOT EXISTS rp_photos (
            command TEXT NOT NULL,
            attachment TEXT NOT NULL,
            photo_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            synced_at TEXT NOT NULL,
            PRIMARY KEY(command, photo_id, owner_id)
        );
        CREATE INDEX IF NOT EXISTS idx_rp_photos_command ON rp_photos(command);
        CREATE TABLE IF NOT EXISTS weekly_tasks (
            user_id INTEGER PRIMARY KEY,
            week_key TEXT NOT NULL,
            task1_json TEXT NOT NULL,
            task2_json TEXT NOT NULL,
            completed1 INTEGER DEFAULT 0,
            completed2 INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS task_progress (
            user_id INTEGER NOT NULL,
            week_key TEXT NOT NULL,
            task_id TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, week_key, task_id)
        );
        CREATE TABLE IF NOT EXISTS daily_task_slots (
            user_id INTEGER PRIMARY KEY,
            extra_slots INTEGER NOT NULL DEFAULT 0 CHECK(extra_slots BETWEEN 0 AND 2)
        );
        CREATE TABLE IF NOT EXISTS daily_task_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_date TEXT NOT NULL,
            scope_peer_id INTEGER NOT NULL DEFAULT 0,
            task_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            kind TEXT NOT NULL,
            goal INTEGER NOT NULL,
            coins INTEGER NOT NULL,
            power INTEGER NOT NULL DEFAULT 0,
            gems INTEGER NOT NULL DEFAULT 0,
            progress INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_daily_task_user_date ON daily_task_instances(user_id, task_date, status);
        CREATE INDEX IF NOT EXISTS idx_daily_task_scope ON daily_task_instances(user_id, scope_peer_id, task_date);
        """)

        # CREATE TABLE IF NOT EXISTS does not add columns to an older database.
        # Ensure columns required by current code exist without deleting user data.
        required_columns = {
            'users': {
                'nickname': "TEXT DEFAULT ''",
                'soul_gems': 'INTEGER DEFAULT 0',
                'power': 'INTEGER DEFAULT 0',
                'coins': 'INTEGER DEFAULT 100',
                'job': "TEXT DEFAULT 'Отсутствует'",
                'salary': 'INTEGER DEFAULT 0',
                'work_days': 'INTEGER DEFAULT 0',
                'housing': "TEXT DEFAULT 'Отсутствует'",
                'car': "TEXT DEFAULT 'Отсутствует'",
                'phone': "TEXT DEFAULT 'Отсутствует'",
                'role': "TEXT DEFAULT 'Участник'",
                'rights': "TEXT DEFAULT 'Участник'",
                'warnings': 'INTEGER DEFAULT 0',
                'admin_warnings': 'INTEGER DEFAULT 0',
                'join_date': 'TEXT',
                'messages_total': 'INTEGER DEFAULT 0',
                'banned': 'INTEGER DEFAULT 0',
                'job_level': 'INTEGER DEFAULT 0',
                'job_exp': 'INTEGER DEFAULT 0',
                'job_last_work': 'TEXT',
                'family_surname': "TEXT DEFAULT ''",
                'profile_image': "TEXT DEFAULT ''",
                'custom_role': "TEXT DEFAULT ''",
                'last_message_at': 'TEXT',
                'status': "TEXT DEFAULT ''",
                'gif_link': "TEXT DEFAULT ''",
                'salary_multiplier': 'REAL DEFAULT 1.0',
            },
            'chat_settings': {
                'welcome_message': "TEXT DEFAULT ''",
                'welcome_photo': "TEXT DEFAULT ''",
                'cleanup_enabled': 'INTEGER DEFAULT 0',
                'casino_enabled': 'INTEGER DEFAULT 1',
                'mute_enabled': 'INTEGER DEFAULT 0',
                'duel_enabled': 'INTEGER DEFAULT 1',
                'broadcast_enabled': 'INTEGER DEFAULT 0',
            },
            'warning_events': {
                'peer_id': 'INTEGER',
                'is_admin_warning': 'INTEGER DEFAULT 0',
                'created_at': 'TEXT',
            },
            'chat_pins': {
                'conversation_message_id': 'INTEGER',
                'message_id': 'INTEGER',
                'updated_at': "TEXT DEFAULT ''",
            },
            'relationships': {
                'partner_id': 'INTEGER',
                'married': 'INTEGER DEFAULT 0',
                'family_surname': "TEXT DEFAULT ''",
                'relationship_since': 'TEXT',
            },
        }
        for table_name, columns in required_columns.items():
            existing = {
                row[1] for row in c.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    c.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )

def user_exists(user_id):
    with db_cursor() as (_, c):
        c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        return c.fetchone() is not None

def create_user(user_id, name):
    with db_cursor(True) as (_, c):
        c.execute("INSERT INTO users(user_id,name,join_date) VALUES(?,?,CURRENT_DATE) ON CONFLICT(user_id) DO UPDATE SET name=excluded.name", (user_id, name))
        c.execute("INSERT INTO relationships(user_id) VALUES(?) ON CONFLICT(user_id) DO NOTHING", (user_id,))

def get_user(user_id):
    with db_cursor() as (_, c):
        c.execute("SELECT user_id,name,nickname,soul_gems,power,coins,job,salary,work_days,housing,car,phone,role,rights,warnings,join_date,messages_total,banned,job_level,job_exp,job_last_work,family_surname,profile_image,custom_role,admin_warnings,last_message_at,status,gif_link,salary_multiplier FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        return tuple(r) if r else None

def ensure_chat(peer_id):
    with db_cursor(True) as (_, c): c.execute("INSERT INTO chat_settings(peer_id) VALUES(?) ON CONFLICT(peer_id) DO NOTHING", (peer_id,))

def add_message_count(user_id, peer_id):
    today = datetime.now().strftime("%Y-%m-%d")
    with db_cursor(True) as (_, c):
        c.execute("INSERT INTO messages_stats(user_id, date, count) VALUES(?,?,1) ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1", (user_id, today))
        c.execute("INSERT INTO chat_message_stats(peer_id, user_id, date, count) VALUES(?,?,?,1) ON CONFLICT(peer_id, user_id, date) DO UPDATE SET count = count + 1", (peer_id, user_id, today))
        c.execute("UPDATE users SET messages_total = messages_total + 1, last_message_at = CURRENT_TIMESTAMP WHERE user_id=?", (user_id,))

def get_admin_level_for_chat(peer_id, user_id):
    with db_cursor() as (_, c):
        try:
            r = c.execute("SELECT MAX(level) FROM admin_chat_rights WHERE peer_id=? AND user_id=?", (peer_id, user_id)).fetchone()
            return int(r[0]) if r and r[0] is not None else 0
        except: return 0

def set_admin_level(peer_id, user_id, level, role_name):
    with db_cursor(True) as (_, c):
        try: lvl = int(level)
        except: lvl = 0
        if lvl <= 0: c.execute("DELETE FROM admin_chat_rights WHERE peer_id=? AND user_id=?", (peer_id, user_id))
        else: c.execute("INSERT INTO admin_chat_rights(peer_id,user_id,level) VALUES(?,?,?) ON CONFLICT(peer_id,user_id) DO UPDATE SET level=excluded.level", (peer_id, user_id, lvl))

def get_admins_for_chat(peer_id):
    with db_cursor() as (_, c):
        return c.execute("SELECT user_id, level FROM admin_chat_rights WHERE peer_id=? AND level>0 ORDER BY level DESC", (peer_id,)).fetchall()

def get_global_role(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT level FROM global_roles WHERE user_id=?", (user_id,)).fetchone()
        return int(r[0]) if r else 0

def set_global_role(user_id, level):
    level = int(level)
    if level not in (0, 6, 7):
        raise ValueError(f'Глобальными могут быть только уровни 6 и 7; получен {level}')
    with db_cursor(True) as (_, c):
        if level == 0:
            c.execute("DELETE FROM global_roles WHERE user_id=?", (user_id,))
        else:
            c.execute("INSERT INTO global_roles(user_id,level) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET level=excluded.level", (user_id, level))

def get_all_global_roles():
    with db_cursor() as (_, c): return c.execute("SELECT user_id, level FROM global_roles WHERE level>0").fetchall()

def get_user_admin_rights(user_id):
    """Return valid global and local admin assignments without mutating stored data."""
    with db_cursor() as (_, c):
        global_row = c.execute(
            'SELECT level FROM global_roles WHERE user_id=? AND level>0', (int(user_id),)
        ).fetchone()
        local_rows = c.execute(
            'SELECT peer_id, level FROM admin_chat_rights WHERE user_id=? AND level BETWEEN 1 AND 5 ORDER BY level DESC, peer_id',
            (int(user_id),),
        ).fetchall()
    global_level = int(global_row[0]) if global_row and int(global_row[0]) in (6, 7) else 0
    return global_level, [(int(peer), int(level)) for peer, level in local_rows]

def add_warning(user_id, peer_id, is_admin=False):
    with db_cursor(True) as (_, c):
        c.execute("INSERT INTO warning_events(user_id, peer_id, is_admin_warning, created_at) VALUES(?,?,?,CURRENT_TIMESTAMP)", (user_id, peer_id, 1 if is_admin else 0))
        field = 'admin_warnings' if is_admin else 'warnings'
        c.execute(f"UPDATE users SET {field} = {field} + 1 WHERE user_id=?", (user_id,))
        return c.execute(f"SELECT {field} FROM users WHERE user_id=?", (user_id,)).fetchone()[0]

def remove_warning(user_id, peer_id, is_admin=False):
    with db_cursor(True) as (_, c):
        field = 'admin_warnings' if is_admin else 'warnings'
        r = c.execute("SELECT id FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=? ORDER BY id DESC LIMIT 1", (user_id, peer_id, 1 if is_admin else 0)).fetchone()
        if r: 
            c.execute("DELETE FROM warning_events WHERE id=?", (r[0],))
            c.execute(f"UPDATE users SET {field} = MAX(0, {field} - 1) WHERE user_id=?", (user_id,))
        return c.execute(f"SELECT {field} FROM users WHERE user_id=?", (user_id,)).fetchone()[0]

def clear_warnings(user_id, peer_id, is_admin=False):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=?", (user_id, peer_id, 1 if is_admin else 0))
        c.execute(f"UPDATE users SET {'admin_warnings' if is_admin else 'warnings'} = 0 WHERE user_id=?", (user_id,))

def get_warning_count(user_id, peer_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT COUNT(*) FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=0", (user_id, peer_id)).fetchone()
        return r[0] if r else 0

def get_warning_stats(user_id, is_admin=False):
    now = datetime.now()
    week = _week_start(now).strftime("%Y-%m-%d")
    month = _month_start(now).strftime("%Y-%m-%d")
    flag = 1 if is_admin else 0
    with db_cursor() as (_, c):
        total = c.execute("SELECT COUNT(*) FROM warning_events WHERE user_id=? AND is_admin_warning=?", (user_id, flag)).fetchone()[0]
        w = c.execute("SELECT COUNT(*) FROM warning_events WHERE user_id=? AND is_admin_warning=? AND created_at >= ?", (user_id, flag, week)).fetchone()[0]
        m = c.execute("SELECT COUNT(*) FROM warning_events WHERE user_id=? AND is_admin_warning=? AND created_at >= ?", (user_id, flag, month)).fetchone()[0]
        return {'total': total, 'week': w, 'month': m}

def add_kick_event(user_id, peer_id, kicked_by):
    with db_cursor(True) as (_, c): c.execute("INSERT INTO kick_events(user_id, peer_id, kicked_by, created_at) VALUES(?,?,?,CURRENT_TIMESTAMP)", (user_id, peer_id, kicked_by))

def get_kick_stats(user_id):
    now = datetime.now()
    week = _week_start(now).strftime("%Y-%m-%d")
    month = _month_start(now).strftime("%Y-%m-%d")
    with db_cursor() as (_, c):
        total = c.execute("SELECT COUNT(*) FROM kick_events WHERE user_id=?", (user_id,)).fetchone()[0]
        w = c.execute("SELECT COUNT(*) FROM kick_events WHERE user_id=? AND created_at >= ?", (user_id, week)).fetchone()[0]
        m = c.execute("SELECT COUNT(*) FROM kick_events WHERE user_id=? AND created_at >= ?", (user_id, month)).fetchone()[0]
        return {'total': total, 'week': w, 'month': m}

def ban_user(user_id):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
def unban_user(user_id):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
def is_banned(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT banned FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(r[0]) if r else False
def get_banned_users():
    with db_cursor() as (_, c): return c.execute("SELECT user_id, name FROM users WHERE banned=1").fetchall()

def update_coins(user_id, amount):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, user_id))

def grant_one_time_coins(user_id, amount=100000):
    """Grant the initial coin bonus once per VK user, even across multiple chats/restarts."""
    user_id = int(user_id)
    amount = int(amount)
    if user_id <= 0 or amount <= 0:
        return False
    with db_cursor(True) as (_, c):
        inserted = c.execute(
            "INSERT OR IGNORE INTO one_time_coin_grants(user_id, amount) "
            "SELECT ?, ? WHERE EXISTS(SELECT 1 FROM users WHERE user_id=?)",
            (user_id, amount, user_id),
        ).rowcount
        if inserted:
            c.execute("UPDATE users SET coins=COALESCE(coins, 0)+? WHERE user_id=?", (amount, user_id))
            return c.execute("SELECT changes()").fetchone()[0] > 0
        return False

def coin_grant_chat_scanned(peer_id):
    with db_cursor() as (_, c):
        return c.execute("SELECT 1 FROM coin_grant_scanned_chats WHERE peer_id=?", (int(peer_id),)).fetchone() is not None

def mark_coin_grant_chat_scanned(peer_id):
    with db_cursor(True) as (_, c):
        c.execute("INSERT OR IGNORE INTO coin_grant_scanned_chats(peer_id) VALUES(?)", (int(peer_id),))

def transfer_coins(sender, target, amount):
    if amount <= 0 or sender == target: return False
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET coins=coins-? WHERE user_id=? AND coins>=?", (amount, sender, amount))
        if c.rowcount != 1: return False
        c.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, target))
        return True

def set_nickname(user_id, nickname):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET nickname=? WHERE user_id=?", (nickname, user_id))

def set_salary(user_id, amount):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET salary=? WHERE user_id=?", (amount, user_id))

def increment_work_days(user_id):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET work_days=work_days+1 WHERE user_id=?", (user_id,))

def update_job_field(user_id, field, value):
    with db_cursor(True) as (_, c):
        columns = {'job_name': 'job', 'level': 'job_level', 'exp': 'job_exp', 'last_work': 'job_last_work'}
        col = columns.get(field)
        if col: c.execute(f"UPDATE users SET {col}=? WHERE user_id=?", (value, user_id))

def get_salary_multiplier(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT salary_multiplier FROM users WHERE user_id=?", (user_id,)).fetchone()
        return float(r[0]) if r and r[0] else 1.0

def increase_salary_multiplier(user_id, step=0.5, max_value=7.0):
    current = get_salary_multiplier(user_id)
    new = min(current + step, max_value)
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET salary_multiplier=? WHERE user_id=?", (new, user_id))
    return new

def set_salary_multiplier(user_id, multiplier):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET salary_multiplier=? WHERE user_id=?", (multiplier, user_id))

def purchase_property(user_id, category, item_name, price):
    field = {'housing': 'housing', 'car': 'car', 'phone': 'phone'}.get(category)
    if not field: return False
    with db_cursor(True) as (_, c):
        c.execute(f"UPDATE users SET {field}=?, coins=coins-? WHERE user_id=? AND coins>=?", (item_name, price, user_id, price))
        return c.rowcount == 1

def get_property_value(user_id, category):
    field = {'housing': 'housing', 'car': 'car', 'phone': 'phone'}.get(category)
    if not field: return 'Отсутствует'
    with db_cursor() as (_, c):
        r = c.execute(f"SELECT {field} FROM users WHERE user_id=?", (user_id,)).fetchone()
        return r[0] if r else 'Отсутствует'

POWER_RANKS = [
    (0, 'Наблюдатель'), (100, 'Новичок'), (300, 'Стратег'), (700, 'Тактик'),
    (1500, 'Командир'), (3000, 'Лидер'), (6000, 'Властитель'),
    (10000, 'Претендент на Трон'), (20000, 'Королевская Особа'), (50000, 'Император'),
]
POWER_PER_THRESHOLD = 10
MESSAGES_PER_THRESHOLD = 250

def get_power_rank(power):
    name = POWER_RANKS[0][1]
    for threshold, rank in POWER_RANKS:
        if power >= threshold: name = rank
        else: break
    return name

def get_power(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT power FROM users WHERE user_id=?", (user_id,)).fetchone()
        return int(r[0]) if r else 0

def update_power(user_id, amount):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET power=power+? WHERE user_id=?", (amount, user_id))

def transfer_power(sender, target, amount):
    if amount <= 0 or sender == target: return False
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET power=power-? WHERE user_id=? AND power>=?", (amount, sender, amount))
        if c.rowcount != 1: return False
        c.execute("UPDATE users SET power=power+? WHERE user_id=?", (amount, target))
        return True

def claim_power_for_messages(user_id):
    with db_cursor(True) as (_, c):
        r = c.execute("SELECT messages_total FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not r: return 0
        total = int(r[0] or 0)
        current_thresholds = total // MESSAGES_PER_THRESHOLD
        r2 = c.execute("SELECT claimed_thresholds FROM power_message_rewards WHERE user_id=?", (user_id,)).fetchone()
        claimed = int(r2[0]) if r2 else 0
        if current_thresholds <= claimed: return 0
        new_thresholds = current_thresholds - claimed
        reward = new_thresholds * POWER_PER_THRESHOLD
        c.execute("UPDATE users SET power=power+? WHERE user_id=?", (reward, user_id))
        c.execute("INSERT INTO power_message_rewards(user_id, claimed_thresholds) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET claimed_thresholds=excluded.claimed_thresholds", (user_id, current_thresholds))
        return reward

def get_gems(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT soul_gems FROM users WHERE user_id=?", (user_id,)).fetchone()
        return int(r[0]) if r and r[0] is not None else 0

def update_gems(user_id, amount):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET soul_gems=soul_gems+? WHERE user_id=?", (amount, user_id))

def debit_gems(user_id, amount):
    if amount <= 0: return False
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET soul_gems=COALESCE(soul_gems, 0)-? WHERE user_id=? AND COALESCE(soul_gems, 0)>=?", (amount, user_id, amount))
        return c.rowcount == 1

def set_profile_image(user_id, attachment):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET profile_image=? WHERE user_id=?", (attachment or '', user_id))

def set_status(user_id, status):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET status=? WHERE user_id=?", (status or '', user_id))

def set_gif_link(user_id, link):
    with db_cursor(True) as (_, c): c.execute("UPDATE users SET gif_link=? WHERE user_id=?", (link or '', user_id))

def get_all_chats():
    with db_cursor() as (_, c): return c.execute("SELECT peer_id, cleanup_enabled FROM chat_settings").fetchall()

def get_feature(peer_id, feature):
    with db_cursor() as (_, c):
        valid = {'cleanup', 'casino', 'mute', 'duel', 'broadcast'}
        if feature not in valid: return False
        field = f"{feature}_enabled"
        r = c.execute(f"SELECT {field} FROM chat_settings WHERE peer_id=?", (peer_id,)).fetchone()
        return bool(r[0]) if r else False

def toggle_feature(peer_id, feature):
    ensure_chat(peer_id)
    with db_cursor(True) as (_, c):
        valid = {'cleanup', 'casino', 'mute', 'duel', 'broadcast'}
        if feature not in valid: return False
        field = f"{feature}_enabled"
        c.execute(f"UPDATE chat_settings SET {field} = NOT COALESCE({field}, 0) WHERE peer_id=?", (peer_id,))
        r = c.execute(f"SELECT {field} FROM chat_settings WHERE peer_id=?", (peer_id,)).fetchone()
        return bool(r[0]) if r else False

def get_welcome_data(peer_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT welcome_message, welcome_photo FROM chat_settings WHERE peer_id=?", (peer_id,)).fetchone()
        return (r[0] or DEFAULT_WELCOME, r[1]) if r else (DEFAULT_WELCOME, '')

def set_welcome_message(peer_id, message, photo=''):
    ensure_chat(peer_id)
    with db_cursor(True) as (_, c): c.execute("UPDATE chat_settings SET welcome_message=?, welcome_photo=? WHERE peer_id=?", (message, photo, peer_id))

def get_broadcast_chats():
    with db_cursor() as (_, c): return [r[0] for r in c.execute("SELECT peer_id FROM chat_settings WHERE broadcast_enabled=1").fetchall()]

def get_chat_activity(peer_id):
    today = datetime.now().strftime("%Y-%m-%d")
    week_start = _week_start(datetime.now()).strftime("%Y-%m-%d")
    month_start = _month_start(datetime.now()).strftime("%Y-%m-%d")
    with db_cursor() as (_, c):
        def _sum(cond, params):
            r = c.execute(f"SELECT SUM(count) FROM chat_message_stats WHERE peer_id=? AND {cond}", (peer_id, *params)).fetchone()
            return r[0] if r and r[0] else 0
        return {'today': _sum("date = ?", (today,)), 'week': _sum("date >= ?", (week_start,)), 'month': _sum("date >= ?", (month_start,)), 'total': _sum("1=1", ())}

def get_messages_stats(user_id):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    week = _week_start(now).strftime("%Y-%m-%d")
    month = _month_start(now).strftime("%Y-%m-%d")
    with db_cursor() as (_, c):
        def _sum(cond, params):
            r = c.execute(f"SELECT SUM(count) FROM messages_stats WHERE user_id=? AND {cond}", (user_id, *params)).fetchone()
            return r[0] if r and r[0] else 0
        total = c.execute("SELECT messages_total FROM users WHERE user_id=?", (user_id,)).fetchone()
        return {'today': _sum("date = ?", (today,)), 'week': _sum("date >= ?", (week,)), 'month': _sum("date >= ?", (month,)), 'total': total[0] if total else 0}

def get_last_message_at(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT last_message_at FROM users WHERE user_id=?", (user_id,)).fetchone()
        return r[0] if r else None

def get_user_join_date(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT join_date FROM users WHERE user_id=?", (user_id,)).fetchone()
        return r[0] if r else None

def get_first_inviter(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT invited_by FROM chat_members WHERE user_id=? AND invited_by IS NOT NULL ORDER BY first_join_at ASC LIMIT 1", (user_id,)).fetchone()
        return r[0] if r else None

def record_chat_join(peer_id, user_id, invited_by=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c):
        c.execute("INSERT INTO chat_members(peer_id,user_id,first_join_at,invited_by) VALUES(?,?,?,?) ON CONFLICT(peer_id,user_id) DO UPDATE SET invited_by=COALESCE(chat_members.invited_by, excluded.invited_by)", (peer_id, user_id, now, invited_by))

def get_chat_join_date(peer_id, user_id):
    if not peer_id or peer_id <= 2000000000: return None
    with db_cursor() as (_, c):
        r = c.execute("SELECT first_join_at FROM chat_members WHERE peer_id=? AND user_id=?", (peer_id, user_id)).fetchone()
        return r[0] if r else None

def find_chats_by_number(vk, number):
    import re as _re
    chats = get_all_chats()
    if not chats: return []
    ids = [p for p, _ in chats]
    names = {}
    try:
        data = vk.messages.getConversationsById(peer_ids=','.join(map(str, ids))).get('items', [])
        for x in data:
            pid = int(x.get('peer', {}).get('id'))
            names[pid] = (x.get('chat_settings', {}).get('title') or '').strip()
    except: return []
    result = []
    target = str(number).strip().lower()
    for pid, title in names.items():
        m = _re.match(r'^(.*?)\s*(\S+)\s*$', title)
        if not m: continue
        if m.group(2).strip().lower() == target: result.append(pid)
    return result

def add_to_admin_blacklist(user_id, added_by):
    with db_cursor(True) as (_, c): c.execute("INSERT INTO admin_blacklist(user_id, added_by, added_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET added_by=excluded.added_by, added_at=excluded.added_at", (user_id, added_by))

def remove_from_admin_blacklist(user_id):
    with db_cursor(True) as (_, c): c.execute("DELETE FROM admin_blacklist WHERE user_id=?", (user_id,))

def is_in_admin_blacklist(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT 1 FROM admin_blacklist WHERE user_id=?", (user_id,)).fetchone()
        return r is not None

def _week_key_moscow():
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo('Europe/Moscow'))
    return (now.date() - timedelta(days=now.weekday())).isoformat()

def add_admin_stat(user_id, field, amount=1):
    if field not in ('messages', 'invites', 'reports', 'gems_awarded'): return
    week = _week_key_moscow()
    with db_cursor(True) as (_, c):
        c.execute(f"INSERT INTO admin_weekly_stats(user_id, week_key, {field}) VALUES(?,?,?) ON CONFLICT(user_id, week_key) DO UPDATE SET {field} = {field} + excluded.{field}", (user_id, week, amount))

def get_admin_week_stats(user_id):
    week = _week_key_moscow()
    with db_cursor() as (_, c):
        r = c.execute("SELECT messages, invites, reports, gems_awarded FROM admin_weekly_stats WHERE user_id=? AND week_key=?", (user_id, week)).fetchone()
        return {'messages': r[0], 'invites': r[1], 'reports': r[2], 'gems_awarded': r[3]} if r else {'messages': 0, 'invites': 0, 'reports': 0, 'gems_awarded': 0}

def get_all_admin_week_stats():
    week = _week_key_moscow()
    with db_cursor() as (_, c): return c.execute("SELECT user_id, messages, invites, reports, gems_awarded FROM admin_weekly_stats WHERE week_key=?", (week,)).fetchall()

def reset_admin_week_stats():
    week = _week_key_moscow()
    with db_cursor(True) as (_, c): c.execute("DELETE FROM admin_weekly_stats WHERE week_key < ?", (week,))

def get_owner(twink_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT owner_id FROM twinks WHERE twink_id=?", (twink_id,)).fetchone()
        return r[0] if r else None

def add_twink(owner_id, twink_id):
    if owner_id == twink_id: return False
    with db_cursor(True) as (_, c):
        r = c.execute("SELECT owner_id FROM twinks WHERE twink_id=?", (twink_id,)).fetchone()
        if r: return False
        c.execute("INSERT INTO twinks(twink_id, owner_id, added_at) VALUES(?,?,CURRENT_TIMESTAMP)", (twink_id, owner_id))
        return True

def remove_twink(twink_id):
    with db_cursor(True) as (_, c): c.execute("DELETE FROM twinks WHERE twink_id=?", (twink_id,))

def get_twinks(owner_id):
    with db_cursor() as (_, c):
        c.execute("SELECT twink_id FROM twinks WHERE owner_id=? ORDER BY added_at", (owner_id,))
        return [r[0] for r in c.fetchall()]

def is_twink(twink_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT 1 FROM twinks WHERE twink_id=?", (twink_id,)).fetchone()
        return r is not None

def is_chat_hidden(peer_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT 1 FROM hidden_chats WHERE peer_id=?", (peer_id,)).fetchone()
        return r is not None

def get_chat_pin(peer_id):
    with db_cursor() as (_, c): return c.execute("SELECT conversation_message_id, message_id, updated_at FROM chat_pins WHERE peer_id=?", (peer_id,)).fetchone()

def set_chat_pin(peer_id, conversation_message_id=None, message_id=None):
    with db_cursor(True) as (_, c):
        c.execute("INSERT INTO chat_pins(peer_id, conversation_message_id, message_id, updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(peer_id) DO UPDATE SET conversation_message_id=COALESCE(excluded.conversation_message_id, chat_pins.conversation_message_id), message_id=COALESCE(excluded.message_id, chat_pins.message_id), updated_at=CURRENT_TIMESTAMP", (peer_id, conversation_message_id, message_id))

def reset_chat_pin_cmid(peer_id):
    with db_cursor(True) as (_, c): c.execute("UPDATE chat_pins SET conversation_message_id=NULL WHERE peer_id=?", (peer_id,))

def get_application(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT user_id, state, current_step, answers, review_peer_id, review_msg_id, created_at, updated_at FROM applications WHERE user_id=?", (user_id,)).fetchone()
        if not r: return None
        return {'user_id': r[0], 'state': r[1], 'current_step': r[2], 'answers': json.loads(r[3] or '[]'), 'review_peer_id': r[4], 'review_msg_id': r[5], 'created_at': r[6], 'updated_at': r[7]}

def upsert_application(user_id, state, current_step=0, answers=None, review_peer_id=None, review_msg_id=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c):
        c.execute("INSERT INTO applications(user_id, state, current_step, answers, review_peer_id, review_msg_id, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, current_step=excluded.current_step, answers=excluded.answers, review_peer_id=excluded.review_peer_id, review_msg_id=excluded.review_msg_id, updated_at=excluded.updated_at", (user_id, state, current_step, json.dumps(answers or [], ensure_ascii=False), review_peer_id, review_msg_id, now, now))

def delete_application(user_id):
    with db_cursor(True) as (_, c): c.execute("DELETE FROM applications WHERE user_id=?", (user_id,))

def set_application_cooldown(user_id, days=3):
    until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c): c.execute("INSERT INTO application_cooldowns(user_id, until_ts) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET until_ts=excluded.until_ts", (user_id, until))

def get_application_cooldown(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT until_ts FROM application_cooldowns WHERE user_id=?", (user_id,)).fetchone()
        if not r: return None
        try: until = datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S")
        except Exception: return None
        return until if until > datetime.now() else None

def create_duel(challenger_id, opponent_id, peer_id, message_id):
    with db_cursor(True) as (_, c):
        c.execute("INSERT INTO duels(opponent_id, challenger_id, peer_id, message_id, created_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(opponent_id) DO UPDATE SET challenger_id=excluded.challenger_id, peer_id=excluded.peer_id, message_id=excluded.message_id, created_at=excluded.created_at", (opponent_id, challenger_id, peer_id, message_id))

def get_duel_for_opponent(opponent_id):
    with db_cursor() as (_, c): return c.execute("SELECT challenger_id, opponent_id, peer_id, message_id FROM duels WHERE opponent_id=?", (opponent_id,)).fetchone()

def delete_duel(opponent_id):
    with db_cursor(True) as (_, c): c.execute("DELETE FROM duels WHERE opponent_id=?", (opponent_id,))

def has_active_duel(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT 1 FROM duels WHERE challenger_id=? OR opponent_id=? LIMIT 1", (user_id, user_id)).fetchone()
        return r is not None

def get_chat_user_week_messages(peer_id, user_id, start_date, end_date):
    with db_cursor() as (_, c):
        r = c.execute("SELECT SUM(count) FROM chat_message_stats WHERE peer_id=? AND user_id=? AND date >= ? AND date <= ?", (peer_id, user_id, start_date, end_date)).fetchone()
        return r[0] if r and r[0] else 0

def replace_rp_photos(command, photos):
    """Atomically replace the cached photo list for one RP command."""
    normalized = []
    for attachment, photo_id, owner_id in photos:
        if not attachment or photo_id is None or owner_id is None:
            continue
        normalized.append((str(command), str(attachment), int(photo_id), int(owner_id)))

    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM rp_photos WHERE command=?", (command,))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.executemany(
            """INSERT OR IGNORE INTO rp_photos
               (command, attachment, photo_id, owner_id, synced_at)
               VALUES (?, ?, ?, ?, ?)""",
            [(cmd, attachment, photo_id, owner_id, now)
             for cmd, attachment, photo_id, owner_id in normalized],
        )


def get_random_rp_photo(command):
    with db_cursor() as (_, c):
        row = c.execute(
            "SELECT attachment FROM rp_photos WHERE command=? ORDER BY RANDOM() LIMIT 1",
            (command,),
        ).fetchone()
        return row[0] if row else None


def get_rp_photo_count(command):
    with db_cursor() as (_, c):
        row = c.execute(
            "SELECT COUNT(*) FROM rp_photos WHERE command=?",
            (command,),
        ).fetchone()
        return int(row[0] if row else 0)


# Relationship, marriage, and family proposal persistence.
def create_relationship_proposal(target_id, proposer_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c):
        c.execute(
            """INSERT INTO relationship_proposals(target_id, proposer_id, created_at)
               VALUES(?, ?, ?)
               ON CONFLICT(target_id) DO UPDATE SET
                   proposer_id=excluded.proposer_id,
                   created_at=excluded.created_at""",
            (int(target_id), int(proposer_id), now),
        )


def get_relationship_proposal(target_id):
    with db_cursor() as (_, c):
        return c.execute(
            "SELECT proposer_id, created_at FROM relationship_proposals WHERE target_id=?",
            (int(target_id),),
        ).fetchone()


def delete_relationship_proposal(target_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM relationship_proposals WHERE target_id=?", (int(target_id),))


def create_marriage_proposal(target_id, proposer_id, surname):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c):
        c.execute(
            """INSERT INTO marriage_proposals(target_id, proposer_id, surname, created_at)
               VALUES(?, ?, ?, ?)
               ON CONFLICT(target_id) DO UPDATE SET
                   proposer_id=excluded.proposer_id,
                   surname=excluded.surname,
                   created_at=excluded.created_at""",
            (int(target_id), int(proposer_id), str(surname), now),
        )


def get_marriage_proposal(target_id):
    with db_cursor() as (_, c):
        return c.execute(
            "SELECT proposer_id, surname, created_at FROM marriage_proposals WHERE target_id=?",
            (int(target_id),),
        ).fetchone()


def delete_marriage_proposal(target_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM marriage_proposals WHERE target_id=?", (int(target_id),))


def create_family_proposal(target_id, proposer_id, relation_type):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c):
        c.execute(
            """INSERT INTO family_proposals(target_id, proposer_id, relation_type, created_at)
               VALUES(?, ?, ?, ?)
               ON CONFLICT(target_id) DO UPDATE SET
                   proposer_id=excluded.proposer_id,
                   relation_type=excluded.relation_type,
                   created_at=excluded.created_at""",
            (int(target_id), int(proposer_id), str(relation_type), now),
        )


def get_family_proposal(target_id):
    with db_cursor() as (_, c):
        return c.execute(
            "SELECT proposer_id, relation_type, created_at FROM family_proposals WHERE target_id=?",
            (int(target_id),),
        ).fetchone()


def delete_family_proposal(target_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM family_proposals WHERE target_id=?", (int(target_id),))


# Weekly tasks persistence.
def get_weekly_tasks(user_id):
    with db_cursor() as (_, c):
        row = c.execute(
            """SELECT week_key, task1_json, task2_json, completed1, completed2
               FROM weekly_tasks WHERE user_id=?""",
            (int(user_id),),
        ).fetchone()
    if not row:
        return None
    try:
        tasks = [json.loads(row[1]), json.loads(row[2])]
    except (TypeError, json.JSONDecodeError):
        return None
    return {
        'user_id': int(user_id),
        'week_key': row[0],
        'tasks': tasks,
        'completed': [bool(row[3]), bool(row[4])],
    }


def save_weekly_tasks(user_id, week_key, task1, task2):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c):
        c.execute(
            """INSERT INTO weekly_tasks
               (user_id, week_key, task1_json, task2_json, completed1, completed2, updated_at)
               VALUES (?, ?, ?, ?, 0, 0, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   week_key=excluded.week_key,
                   task1_json=excluded.task1_json,
                   task2_json=excluded.task2_json,
                   completed1=0,
                   completed2=0,
                   updated_at=excluded.updated_at""",
            (
                int(user_id),
                str(week_key),
                json.dumps(task1, ensure_ascii=False),
                json.dumps(task2, ensure_ascii=False),
                now,
            ),
        )


def weekly_task_is_completed(user_id, slot):
    data = get_weekly_tasks(user_id)
    return bool(data and 0 <= int(slot) < len(data['completed']) and data['completed'][int(slot)])


def complete_weekly_task(user_id, slot):
    slot = int(slot)
    if slot not in (0, 1):
        raise ValueError("slot must be 0 or 1")
    column = "completed1" if slot == 0 else "completed2"
    with db_cursor(True) as (_, c):
        c.execute(
            f"UPDATE weekly_tasks SET {column}=1, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (int(user_id),),
        )


def get_task_progress(user_id, week_key, task_id):
    with db_cursor() as (_, c):
        row = c.execute(
            "SELECT progress FROM task_progress WHERE user_id=? AND week_key=? AND task_id=?",
            (int(user_id), str(week_key), str(task_id)),
        ).fetchone()
        return int(row[0]) if row else 0


def set_task_progress(user_id, week_key, task_id, progress):
    with db_cursor(True) as (_, c):
        c.execute(
            """INSERT INTO task_progress(user_id, week_key, task_id, progress)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, week_key, task_id) DO UPDATE SET
                   progress=excluded.progress""",
            (int(user_id), str(week_key), str(task_id), max(0, int(progress))),
        )


def get_admin_chat_stats(peer_id, user_id):
    """Message and invite counts for an admin within one conversation."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    week = _week_start(now).strftime("%Y-%m-%d")
    month = _month_start(now).strftime("%Y-%m-%d")
    with db_cursor() as (_, c):
        def count_messages(cond, params=()):
            row = c.execute(
                f"SELECT COALESCE(SUM(count), 0) FROM chat_message_stats WHERE peer_id=? AND user_id=? AND {cond}",
                (int(peer_id), int(user_id), *params),
            ).fetchone()
            return int(row[0] or 0)
        def count_invites(cond, params=()):
            row = c.execute(
                f"SELECT COUNT(*) FROM chat_members WHERE peer_id=? AND invited_by=? AND substr(first_join_at,1,10) {cond}",
                (int(peer_id), int(user_id), *params),
            ).fetchone()
            return int(row[0] or 0)
        return {
            'messages': {
                'today': count_messages('date = ?', (today,)),
                'week': count_messages('date >= ?', (week,)),
                'month': count_messages('date >= ?', (month,)),
                'total': count_messages('1=1'),
            },
            'invites': {
                'today': count_invites('= ?', (today,)),
                'week': count_invites('>= ?', (week,)),
                'month': count_invites('>= ?', (month,)),
                'total': count_invites('IS NOT NULL'),
            },
        }
