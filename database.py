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
        if commit:
            cur.execute("BEGIN IMMEDIATE")
        yield conn, cur
        if commit:
            conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    return _connect()


def migrate_database():
    with db_cursor(True) as (_, c):
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            nickname TEXT DEFAULT '',
            soul_gems INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 100,
            job TEXT DEFAULT 'Безработный',
            salary INTEGER DEFAULT 0,
            work_days INTEGER DEFAULT 0,
            housing TEXT DEFAULT 'Отсутствует',
            car TEXT DEFAULT 'Отсутствует',
            phone TEXT DEFAULT 'Отсутствует',
            role TEXT DEFAULT 'Участник',
            rights TEXT DEFAULT 'Участник',
            warnings INTEGER DEFAULT 0,
            admin_warnings INTEGER DEFAULT 0,
            join_date TEXT DEFAULT (CURRENT_DATE),
            messages_total INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            job_level INTEGER DEFAULT 0,
            job_exp INTEGER DEFAULT 0,
            job_last_work TEXT,
            family_surname TEXT DEFAULT '',
            profile_image TEXT DEFAULT '',
            custom_role TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS messages_stats (
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, date)
        );

        CREATE TABLE IF NOT EXISTS chat_message_stats (
            peer_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY(peer_id, user_id, date)
        );

        CREATE TABLE IF NOT EXISTS chat_settings (
            peer_id INTEGER PRIMARY KEY,
            welcome_message TEXT DEFAULT '',
            welcome_photo TEXT DEFAULT '',
            cleanup_enabled INTEGER DEFAULT 0,
            casino_enabled INTEGER DEFAULT 1,
            mute_enabled INTEGER DEFAULT 0,
            duel_enabled INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS relationships (
            user_id INTEGER PRIMARY KEY,
            partner_id INTEGER,
            married INTEGER DEFAULT 0,
            family_surname TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS marriage_proposals (
            target_id INTEGER PRIMARY KEY,
            proposer_id INTEGER NOT NULL,
            surname TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS relationship_proposals (
            target_id INTEGER PRIMARY KEY,
            proposer_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS family_proposals (
            target_id INTEGER PRIMARY KEY,
            proposer_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS family_children (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            UNIQUE(parent_id, child_id)
        );

        CREATE TABLE IF NOT EXISTS warning_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            is_admin_warning INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admin_chat_rights (
            peer_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            level INTEGER NOT NULL,
            PRIMARY KEY(peer_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS chat_weekly_message_totals (
            peer_id INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY(peer_id, week_start, user_id)
        );

        CREATE TABLE IF NOT EXISTS chat_members (
            peer_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            first_join_at TEXT NOT NULL,
            PRIMARY KEY(peer_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS global_roles (
            user_id INTEGER PRIMARY KEY,
            level INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS duels (
            opponent_id INTEGER PRIMARY KEY,
            challenger_id INTEGER NOT NULL,
            peer_id INTEGER NOT NULL,
            message_id INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS power_message_rewards (
            user_id INTEGER PRIMARY KEY,
            claimed_thresholds INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS hidden_chats (
            peer_id INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS admin_blacklist (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER NOT NULL,
            added_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS applications (
            user_id INTEGER PRIMARY KEY,
            state TEXT NOT NULL,
            current_step INTEGER DEFAULT 0,
            answers TEXT DEFAULT '[]',
            review_peer_id INTEGER,
            review_msg_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS application_cooldowns (
            user_id INTEGER PRIMARY KEY,
            until_ts TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_pins (
            peer_id INTEGER PRIMARY KEY,
            conversation_message_id INTEGER,
            message_id INTEGER,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_warning_events_user_date
            ON warning_events(user_id, created_at);
        """)

        cols = {row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()}
        if "admin_warnings" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN admin_warnings INTEGER DEFAULT 0")
        wcols = {row[1] for row in c.execute("PRAGMA table_info(warning_events)").fetchall()}
        if "peer_id" not in wcols:
            c.execute("ALTER TABLE warning_events ADD COLUMN peer_id INTEGER")
        scols = {row[1] for row in c.execute("PRAGMA table_info(chat_settings)").fetchall()}
        if "duel_enabled" not in scols:
            c.execute("ALTER TABLE chat_settings ADD COLUMN duel_enabled INTEGER DEFAULT 1")
        pcols = {row[1] for row in c.execute("PRAGMA table_info(chat_pins)").fetchall()}
        if "message_id" not in pcols:
            c.execute("ALTER TABLE chat_pins ADD COLUMN message_id INTEGER")


def create_user(user_id, name):
    with db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO users(user_id,name,join_date) VALUES(?,?,CURRENT_DATE)
            ON CONFLICT(user_id) DO UPDATE SET name=excluded.name
        """, (user_id, name))
        c.execute(
            "INSERT INTO relationships(user_id) VALUES(?) ON CONFLICT(user_id) DO NOTHING",
            (user_id,)
        )


def user_exists(user_id):
    with db_cursor() as (_, c):
        c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        return c.fetchone() is not None


def get_user(user_id):
    with db_cursor() as (_, c):
        c.execute("""
            SELECT user_id,name,nickname,soul_gems,coins,job,salary,work_days,
                   housing,car,phone,role,rights,warnings,join_date,messages_total,
                   banned,job_level,job_exp,job_last_work,family_surname,
                   profile_image,custom_role,admin_warnings
            FROM users WHERE user_id=?
        """, (user_id,))
        r = c.fetchone()
        if not r:
            return None
        return tuple(r)


def set_global_role(user_id, level):
    with db_cursor(True) as (_, c):
        if level <= 0:
            c.execute("DELETE FROM global_roles WHERE user_id=?", (user_id,))
        else:
            c.execute(
                "INSERT INTO global_roles(user_id,level) VALUES(?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET level=excluded.level",
                (user_id, level)
            )


def get_global_role(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT level FROM global_roles WHERE user_id=?", (user_id,)).fetchone()
        return int(r[0]) if r else 0


def get_all_global_roles():
    with db_cursor() as (_, c):
        c.execute("SELECT user_id, level FROM global_roles WHERE level>0 ORDER BY level DESC")
        return c.fetchall()


def get_admins_for_chat(peer_id):
    with db_cursor() as (_, c):
        c.execute(
            "SELECT user_id, level FROM admin_chat_rights WHERE peer_id=? AND level>0 ORDER BY level DESC",
            (peer_id,)
        )
        return c.fetchall()


def record_chat_join(peer_id, user_id, only_if_missing=True):
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c):
        c.execute(
            "INSERT INTO chat_members(peer_id,user_id,first_join_at) VALUES(?,?,?) "
            "ON CONFLICT(peer_id,user_id) DO NOTHING",
            (peer_id, user_id, now)
        )


def get_chat_join_date(peer_id, user_id):
    if not peer_id or peer_id <= 2000000000:
        return None
    with db_cursor() as (_, c):
        r = c.execute(
            "SELECT first_join_at FROM chat_members WHERE peer_id=? AND user_id=?",
            (peer_id, user_id)
        ).fetchone()
        return r[0] if r else None


def set_profile_image(user_id, attachment):
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET profile_image=? WHERE user_id=?", (attachment or '', user_id))


def update_user_rights(user_id, rights, peer_id=None, level=None):
    with db_cursor(True) as (_, c):
        if peer_id is None:
            c.execute(
                "UPDATE users SET rights=?,role=? WHERE user_id=?",
                (rights, rights, user_id)
            )
        else:
            c.execute("""
                INSERT INTO admin_chat_rights(peer_id,user_id,level)
                VALUES(?,?,?)
                ON CONFLICT(peer_id,user_id) DO UPDATE SET level=excluded.level
            """, (peer_id, user_id, level))


def set_admin_level(peer_id, user_id, level, role_name):
    with db_cursor(True) as (_, c):
        if level <= 0:
            c.execute(
                "DELETE FROM admin_chat_rights WHERE peer_id=? AND user_id=?",
                (peer_id, user_id)
            )
        else:
            c.execute("""
                INSERT INTO admin_chat_rights(peer_id,user_id,level)
                VALUES(?,?,?)
                ON CONFLICT(peer_id,user_id) DO UPDATE SET level=excluded.level
            """, (peer_id, user_id, level))


def get_admin_level_for_chat(peer_id, user_id):
    with db_cursor() as (_, c):
        c.execute(
            "SELECT level FROM admin_chat_rights WHERE peer_id=? AND user_id=?",
            (peer_id, user_id)
        )
        r = c.fetchone()
        return int(r[0]) if r else 0


def update_coins(user_id, amount):
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, user_id))


def transfer_coins(sender, target, amount):
    if amount <= 0 or sender == target:
        return False
    with db_cursor(True) as (_, c):
        c.execute(
            "UPDATE users SET coins=coins-? WHERE user_id=? AND coins>=?",
            (amount, sender, amount)
        )
        if c.rowcount != 1:
            return False
        c.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, target))
        return c.rowcount == 1


def add_message_count(user_id, peer_id=None):
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo('Europe/Moscow')).date().isoformat()

    with db_cursor(True) as (_, c):
        c.execute(
            "UPDATE users SET messages_total=messages_total+1 WHERE user_id=?",
            (user_id,)
        )
        c.execute("""
            INSERT INTO messages_stats(user_id,date,count) VALUES(?,?,1)
            ON CONFLICT(user_id,date) DO UPDATE SET count=messages_stats.count+1
        """, (user_id, today))

        if peer_id and peer_id > 2000000000:
            c.execute("""
                INSERT INTO chat_message_stats(peer_id,user_id,date,count)
                VALUES(?,?,?,1)
                ON CONFLICT(peer_id,user_id,date)
                DO UPDATE SET count=chat_message_stats.count+1
            """, (peer_id, user_id, today))
            ensure_chat_settings(c, peer_id)


def _sum(c, table, where, args):
    c.execute(f"SELECT COALESCE(SUM(count),0) FROM {table} WHERE {where}", args)
    return int(c.fetchone()[0])


def get_messages_stats(user_id):
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo('Europe/Moscow')).date()
    week = today - timedelta(days=6)
    month = today - timedelta(days=29)

    with db_cursor() as (_, c):
        c.execute("SELECT COALESCE(messages_total,0) FROM users WHERE user_id=?", (user_id,))
        total = c.fetchone()
        return {
            'today': _sum(c, 'messages_stats', 'user_id=? AND date=?',
                           (user_id, today.isoformat())),
            'week': _sum(c, 'messages_stats', 'user_id=? AND date>=?',
                         (user_id, week.isoformat())),
            'month': _sum(c, 'messages_stats', 'user_id=? AND date>=?',
                          (user_id, month.isoformat())),
            'total': int(total[0]) if total else 0
        }


def get_chat_activity(peer_id):
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo('Europe/Moscow')).date()
    week = today - timedelta(days=6)
    month = today - timedelta(days=29)

    with db_cursor() as (_, c):
        return {
            'today': _sum(c, 'chat_message_stats', 'peer_id=? AND date=?',
                          (peer_id, today.isoformat())),
            'week': _sum(c, 'chat_message_stats', 'peer_id=? AND date>=?',
                         (peer_id, week.isoformat())),
            'month': _sum(c, 'chat_message_stats', 'peer_id=? AND date>=?',
                          (peer_id, month.isoformat())),
            'total': _sum(c, 'chat_message_stats', 'peer_id=?', (peer_id,))
        }


def get_chat_user_week_messages(peer_id, user_id, start_date, end_date):
    with db_cursor() as (_, c):
        return _sum(
            c, 'chat_message_stats',
            'peer_id=? AND user_id=? AND date>=? AND date<=?',
            (peer_id, user_id, start_date, end_date)
        )


def get_all_chats():
    with db_cursor() as (_, c):
        c.execute("""
            SELECT peer_id, cleanup_enabled FROM chat_settings
            WHERE peer_id NOT IN (SELECT peer_id FROM hidden_chats)
            ORDER BY peer_id
        """)
        return c.fetchall()


def ensure_chat_settings(c, peer_id):
    c.execute("""
        INSERT INTO chat_settings(peer_id,welcome_message)
        VALUES(?,?)
        ON CONFLICT(peer_id) DO NOTHING
    """, (peer_id, DEFAULT_WELCOME))


def ensure_chat(peer_id):
    with db_cursor(True) as (_, c):
        ensure_chat_settings(c, peer_id)


def get_welcome_data(peer_id):
    with db_cursor(True) as (_, c):
        ensure_chat_settings(c, peer_id)
        c.execute(
            "SELECT welcome_message,welcome_photo FROM chat_settings WHERE peer_id=?",
            (peer_id,)
        )
        r = c.fetchone()
        return r or (DEFAULT_WELCOME, '')


def get_chat_settings(peer_id):
    return get_welcome_data(peer_id)[0]


def set_welcome_message(peer_id, message, photo=''):
    with db_cursor(True) as (_, c):
        ensure_chat_settings(c, peer_id)
        c.execute(
            "UPDATE chat_settings SET welcome_message=?,welcome_photo=? WHERE peer_id=?",
            (message, photo or '', peer_id)
        )


def is_cleanup_enabled(peer_id):
    with db_cursor() as (_, c):
        c.execute("SELECT cleanup_enabled FROM chat_settings WHERE peer_id=?", (peer_id,))
        r = c.fetchone()
        return bool(r and r[0])


def set_cleanup_enabled(peer_id, enabled):
    with db_cursor(True) as (_, c):
        ensure_chat_settings(c, peer_id)
        c.execute(
            "UPDATE chat_settings SET cleanup_enabled=? WHERE peer_id=?",
            (int(enabled), peer_id)
        )


def toggle_cleanup(peer_id):
    new = not is_cleanup_enabled(peer_id)
    set_cleanup_enabled(peer_id, new)
    return new


def set_feature(peer_id, feature, enabled):
    if feature == 'чистка':
        set_cleanup_enabled(peer_id, enabled)
        return
    col = {'казино': 'casino_enabled', 'мут': 'mute_enabled', 'дуэль': 'duel_enabled'}[feature]
    with db_cursor(True) as (_, c):
        ensure_chat_settings(c, peer_id)
        c.execute(f"UPDATE chat_settings SET {col}=? WHERE peer_id=?", (int(enabled), peer_id))


def get_feature(peer_id, feature):
    if feature == 'чистка':
        return is_cleanup_enabled(peer_id)
    col = {'казино': 'casino_enabled', 'мут': 'mute_enabled', 'дуэль': 'duel_enabled'}[feature]
    with db_cursor() as (_, c):
        c.execute(f"SELECT {col} FROM chat_settings WHERE peer_id=?", (peer_id,))
        r = c.fetchone()
        return bool(r and r[0])


def toggle_feature(peer_id, feature):
    new = not get_feature(peer_id, feature)
    set_feature(peer_id, feature, new)
    return new


def set_nickname(user_id, nickname):
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET nickname=? WHERE user_id=?", (nickname, user_id))


def get_nickname(user_id):
    with db_cursor() as (_, c):
        c.execute("SELECT nickname FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        return r[0] if r else ''


def add_warning(user_id, peer_id=None, is_admin_warning=False):
    with db_cursor(True) as (_, c):
        if peer_id:
            r = c.execute(
                "SELECT COUNT(*) FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=1",
                (user_id, peer_id)
            ).fetchone()
            current = int(r[0] or 0)
            if current >= 3:
                return 3
            c.execute(
                "INSERT INTO warning_events(user_id,peer_id,is_admin_warning,created_at) "
                "VALUES(?,?,1,CURRENT_TIMESTAMP)",
                (user_id, peer_id)
            )
            return current + 1

        c.execute("SELECT admin_warnings FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        current = int(r[0] or 0) if r else 0
        if current >= 3:
            return 3
        c.execute("UPDATE users SET admin_warnings=admin_warnings+1 WHERE user_id=?", (user_id,))
        c.execute(
            "INSERT INTO warning_events(user_id,peer_id,is_admin_warning,created_at) VALUES(?,?,1,CURRENT_TIMESTAMP)",
            (user_id, None)
        )
        return current + 1


def get_warning_count(user_id, peer_id=None):
    with db_cursor() as (_, c):
        if peer_id:
            r = c.execute(
                "SELECT COUNT(*) FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=1",
                (user_id, peer_id)
            ).fetchone()
            return min(int(r[0] or 0), 3)
        r = c.execute("SELECT admin_warnings FROM users WHERE user_id=?", (user_id,)).fetchone()
        return min(int(r[0] or 0), 3) if r else 0


def remove_warning(user_id, peer_id=None, is_admin_warning=True):
    with db_cursor(True) as (_, c):
        if peer_id:
            row = c.execute(
                "SELECT id FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=1 "
                "ORDER BY id DESC LIMIT 1",
                (user_id, peer_id)
            ).fetchone()
            if row:
                c.execute("DELETE FROM warning_events WHERE id=?", (row[0],))
            return get_warning_count(user_id, peer_id)
        c.execute("UPDATE users SET admin_warnings=MAX(admin_warnings-1,0) WHERE user_id=?", (user_id,))
        return get_warning_count(user_id)


def clear_warnings(user_id, peer_id=None, is_admin_warning=True):
    with db_cursor(True) as (_, c):
        if peer_id:
            c.execute(
                "DELETE FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=1",
                (user_id, peer_id)
            )
            return
        c.execute("UPDATE users SET admin_warnings=0 WHERE user_id=?", (user_id,))


def get_warning_stats(user_id, is_admin_warning=False, peer_id=None):
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo('Europe/Moscow')).date()
    week = today - timedelta(days=6)
    month = today - timedelta(days=29)

    with db_cursor() as (_, c):
        params = [user_id, int(is_admin_warning)]
        extra = ''
        if peer_id is not None:
            extra = ' AND peer_id=?'
            params.append(peer_id)
        dparams = params + [today.isoformat()]
        wparams = params + [week.isoformat()]
        mparams = params + [month.isoformat()]
        q = f"user_id=? AND is_admin_warning=?{extra}"
        d = c.execute(f"SELECT COUNT(*) FROM warning_events WHERE {q} AND date(created_at)=?", dparams).fetchone()[0]
        w = c.execute(f"SELECT COUNT(*) FROM warning_events WHERE {q} AND date(created_at)>=?", wparams).fetchone()[0]
        m = c.execute(f"SELECT COUNT(*) FROM warning_events WHERE {q} AND date(created_at)>=?", mparams).fetchone()[0]
        t = c.execute(f"SELECT COUNT(*) FROM warning_events WHERE {q}", params).fetchone()[0]
        return {'today': int(d), 'week': int(w), 'month': int(m), 'total': int(t)}


def is_banned(user_id):
    with db_cursor() as (_, c):
        c.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        return bool(r and r[0])


def get_banned_users():
    with db_cursor() as (_, c):
        c.execute("SELECT user_id,name FROM users WHERE banned=1 ORDER BY name")
        return c.fetchall()


def ban_user(user_id):
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))


def unban_user(user_id):
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))


def update_job_field(user_id, field, value):
    mapping = {'job_name': 'job', 'level': 'job_level', 'exp': 'job_exp', 'last_work': 'job_last_work'}
    if field not in mapping:
        return
    with db_cursor(True) as (_, c):
        c.execute(f"UPDATE users SET {mapping[field]}=? WHERE user_id=?", (value, user_id))


def purchase_property(user_id, category, item_name, price):
    field = {'housing': 'housing', 'car': 'car', 'phone': 'phone'}.get(category)
    if not field or price <= 0:
        return False
    with db_cursor(True) as (_, c):
        c.execute(f"""
            UPDATE users SET coins=coins-?,{field}=?
            WHERE user_id=? AND coins>=? AND {field}='Отсутствует'
        """, (price, item_name, user_id, price))
        return c.rowcount == 1


def create_marriage_proposal(target_id, proposer_id, surname):
    with db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO marriage_proposals(target_id,proposer_id,surname,created_at)
            VALUES(?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(target_id) DO UPDATE SET
                proposer_id=excluded.proposer_id,
                surname=excluded.surname,
                created_at=excluded.created_at
        """, (target_id, proposer_id, surname))


def get_marriage_proposal(target_id):
    with db_cursor() as (_, c):
        c.execute(
            "SELECT proposer_id,surname,created_at FROM marriage_proposals WHERE target_id=?",
            (target_id,)
        )
        return c.fetchone()


def delete_marriage_proposal(target_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM marriage_proposals WHERE target_id=?", (target_id,))


def create_relationship_proposal(target_id, proposer_id):
    with db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO relationship_proposals(target_id,proposer_id,created_at)
            VALUES(?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(target_id) DO UPDATE SET
                proposer_id=excluded.proposer_id,
                created_at=excluded.created_at
        """, (target_id, proposer_id))


def get_relationship_proposal(target_id):
    with db_cursor() as (_, c):
        c.execute(
            "SELECT proposer_id,created_at FROM relationship_proposals WHERE target_id=?",
            (target_id,)
        )
        return c.fetchone()


def delete_relationship_proposal(target_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM relationship_proposals WHERE target_id=?", (target_id,))


def create_family_proposal(target_id, proposer_id, relation_type):
    with db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO family_proposals(target_id,proposer_id,relation_type,created_at)
            VALUES(?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(target_id) DO UPDATE SET
                proposer_id=excluded.proposer_id,
                relation_type=excluded.relation_type,
                created_at=excluded.created_at
        """, (target_id, proposer_id, relation_type))


def get_family_proposal(target_id):
    with db_cursor() as (_, c):
        c.execute(
            "SELECT proposer_id,relation_type,created_at FROM family_proposals WHERE target_id=?",
            (target_id,)
        )
        return c.fetchone()


def delete_family_proposal(target_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM family_proposals WHERE target_id=?", (target_id,))


def get_property_value(user_id, category):
    field = {'housing': 'housing', 'car': 'car', 'phone': 'phone'}[category]
    with db_cursor() as (_, c):
        c.execute(f"SELECT {field} FROM users WHERE user_id=?", (user_id,))
        r = c.fetchone()
        return r[0] if r else 'Отсутствует'


def set_custom_role(user_id, value):
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET custom_role=? WHERE user_id=?", (value, user_id))


# ============ СИЛА ГИАСА ============

POWER_RANKS = [
    (0,     'Наблюдатель'),
    (100,   'Новичок'),
    (300,   'Стратег'),
    (700,   'Тактик'),
    (1500,  'Командир'),
    (3000,  'Лидер'),
    (6000,  'Властитель'),
    (10000, 'Претендент на Трон'),
    (20000, 'Королевская Особа'),
    (50000, 'Император'),
]

POWER_PER_THRESHOLD = 10
MESSAGES_PER_THRESHOLD = 250


def get_power_rank(power):
    name = POWER_RANKS[0][1]
    for threshold, rank in POWER_RANKS:
        if power >= threshold:
            name = rank
        else:
            break
    return name


def get_power(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT soul_gems FROM users WHERE user_id=?", (user_id,)).fetchone()
        return int(r[0]) if r else 0


def update_power(user_id, amount):
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET soul_gems=soul_gems+? WHERE user_id=?", (amount, user_id))


def debit_power(user_id, amount):
    if amount <= 0:
        return False
    with db_cursor(True) as (_, c):
        c.execute(
            "UPDATE users SET soul_gems=soul_gems-? WHERE user_id=? AND soul_gems>=?",
            (amount, user_id, amount)
        )
        return c.rowcount == 1


def transfer_power(sender, target, amount):
    if amount <= 0 or sender == target:
        return False
    with db_cursor(True) as (_, c):
        c.execute(
            "UPDATE users SET soul_gems=soul_gems-? WHERE user_id=? AND soul_gems>=?",
            (amount, sender, amount)
        )
        if c.rowcount != 1:
            return False
        c.execute("UPDATE users SET soul_gems=soul_gems+? WHERE user_id=?", (amount, target))
        return True


def claim_power_for_messages(user_id):
    with db_cursor(True) as (_, c):
        r = c.execute("SELECT messages_total FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not r:
            return 0
        total = int(r[0] or 0)
        current_thresholds = total // MESSAGES_PER_THRESHOLD

        r2 = c.execute(
            "SELECT claimed_thresholds FROM power_message_rewards WHERE user_id=?",
            (user_id,)
        ).fetchone()
        claimed = int(r2[0]) if r2 else 0

        if current_thresholds <= claimed:
            return 0

        new_thresholds = current_thresholds - claimed
        reward = new_thresholds * POWER_PER_THRESHOLD

        c.execute(
            "UPDATE users SET soul_gems=soul_gems+? WHERE user_id=?",
            (reward, user_id)
        )
        c.execute("""
            INSERT INTO power_message_rewards(user_id, claimed_thresholds) VALUES(?,?)
            ON CONFLICT(user_id) DO UPDATE SET claimed_thresholds=excluded.claimed_thresholds
        """, (user_id, current_thresholds))
        return reward


# ============ ДУЭЛИ ============

def create_duel(challenger_id, opponent_id, peer_id, message_id):
    with db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO duels(opponent_id, challenger_id, peer_id, message_id, created_at)
            VALUES(?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(opponent_id) DO UPDATE SET
                challenger_id=excluded.challenger_id,
                peer_id=excluded.peer_id,
                message_id=excluded.message_id,
                created_at=excluded.created_at
        """, (opponent_id, challenger_id, peer_id, message_id))


def get_duel_for_opponent(opponent_id):
    with db_cursor() as (_, c):
        return c.execute(
            "SELECT challenger_id, opponent_id, peer_id, message_id FROM duels WHERE opponent_id=?",
            (opponent_id,)
        ).fetchone()


def delete_duel(opponent_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM duels WHERE opponent_id=?", (opponent_id,))


def has_active_duel(user_id):
    with db_cursor() as (_, c):
        r = c.execute(
            "SELECT 1 FROM duels WHERE challenger_id=? OR opponent_id=? LIMIT 1",
            (user_id, user_id)
        ).fetchone()
        return r is not None


# ============ СКРЫТЫЕ БЕСЕДЫ ============

def hide_chat(peer_id):
    with db_cursor(True) as (_, c):
        c.execute("INSERT INTO hidden_chats(peer_id) VALUES(?) ON CONFLICT(peer_id) DO NOTHING", (peer_id,))


def unhide_chat(peer_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM hidden_chats WHERE peer_id=?", (peer_id,))


def is_chat_hidden(peer_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT 1 FROM hidden_chats WHERE peer_id=?", (peer_id,)).fetchone()
        return r is not None


# ============ ЧС АДМИНИСТРАЦИИ ============

def add_to_admin_blacklist(user_id, added_by):
    with db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO admin_blacklist(user_id, added_by, added_at)
            VALUES(?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                added_by=excluded.added_by,
                added_at=excluded.added_at
        """, (user_id, added_by))


def remove_from_admin_blacklist(user_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM admin_blacklist WHERE user_id=?", (user_id,))


def is_in_admin_blacklist(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT 1 FROM admin_blacklist WHERE user_id=?", (user_id,)).fetchone()
        return r is not None


def get_admin_blacklist():
    with db_cursor() as (_, c):
        c.execute("SELECT user_id FROM admin_blacklist ORDER BY added_at DESC")
        return [r[0] for r in c.fetchall()]


# ============ ЗАЯВКИ ============

def get_application(user_id):
    with db_cursor() as (_, c):
        r = c.execute(
            "SELECT user_id, state, current_step, answers, review_peer_id, review_msg_id, created_at, updated_at "
            "FROM applications WHERE user_id=?",
            (user_id,)
        ).fetchone()
        if not r:
            return None
        return {
            'user_id': r[0],
            'state': r[1],
            'current_step': r[2],
            'answers': json.loads(r[3] or '[]'),
            'review_peer_id': r[4],
            'review_msg_id': r[5],
            'created_at': r[6],
            'updated_at': r[7],
        }


def upsert_application(user_id, state, current_step=0, answers=None, review_peer_id=None, review_msg_id=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO applications(user_id, state, current_step, answers, review_peer_id, review_msg_id, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                state=excluded.state,
                current_step=excluded.current_step,
                answers=excluded.answers,
                review_peer_id=excluded.review_peer_id,
                review_msg_id=excluded.review_msg_id,
                updated_at=excluded.updated_at
        """, (
            user_id, state, current_step,
            json.dumps(answers or [], ensure_ascii=False),
            review_peer_id, review_msg_id,
            now, now
        ))


def delete_application(user_id):
    with db_cursor(True) as (_, c):
        c.execute("DELETE FROM applications WHERE user_id=?", (user_id,))


def set_application_cooldown(user_id, days=3):
    until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO application_cooldowns(user_id, until_ts) VALUES(?,?)
            ON CONFLICT(user_id) DO UPDATE SET until_ts=excluded.until_ts
        """, (user_id, until))


def get_application_cooldown(user_id):
    with db_cursor() as (_, c):
        r = c.execute("SELECT until_ts FROM application_cooldowns WHERE user_id=?", (user_id,)).fetchone()
        if not r:
            return None
        try:
            until = datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
        if until <= datetime.now():
            return None
        return until


# ============ ЗАКРЕПЫ ============

def get_chat_pin(peer_id):
    """Возвращает (conversation_message_id, message_id, updated_at) или None."""
    with db_cursor() as (_, c):
        r = c.execute(
            "SELECT conversation_message_id, message_id, updated_at FROM chat_pins WHERE peer_id=?",
            (peer_id,)
        ).fetchone()
        return r


def set_chat_pin(peer_id, conversation_message_id=None, message_id=None):
    with db_cursor(True) as (_, c):
        c.execute("""
            INSERT INTO chat_pins(peer_id, conversation_message_id, message_id, updated_at)
            VALUES(?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(peer_id) DO UPDATE SET
                conversation_message_id=COALESCE(excluded.conversation_message_id, chat_pins.conversation_message_id),
                message_id=COALESCE(excluded.message_id, chat_pins.message_id),
                updated_at=CURRENT_TIMESTAMP
        """, (peer_id, conversation_message_id, message_id))


# ============ РАБОТА ============

def set_salary(user_id, amount):
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET salary=? WHERE user_id=?", (amount, user_id))


def increment_work_days(user_id):
    with db_cursor(True) as (_, c):
        c.execute("UPDATE users SET work_days=work_days+1 WHERE user_id=?", (user_id,))