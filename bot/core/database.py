import logging
import sqlite3
import json
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Generator, Optional, Any
from bot.core.config import settings

logger = logging.getLogger(__name__)

def _connect() -> sqlite3.Connection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, detect_types=sqlite3.PARSE_DECLTYPES, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # DELETE mode более надёжен на некоторых FS, чем WAL
    try:
        conn.execute("PRAGMA journal_mode = DELETE")
    except Exception:
        pass
    return conn

@contextmanager
def db_cursor(commit: bool = False) -> Generator[tuple[sqlite3.Connection, sqlite3.Cursor], None, None]:
    conn = _connect()
    try:
        if commit: conn.execute("BEGIN")
        cur = conn.cursor()
        yield conn, cur
        if commit: conn.execute("COMMIT")
    except Exception:
        if commit:
            try: conn.execute("ROLLBACK")
            except Exception: pass
        raise
    finally: conn.close()

def get_db() -> sqlite3.Connection:
    return _connect()

def migrate_database():
    ensure_admin_appointed_column()
    _migrate_body()

def _migrate_body():
    with db_cursor(commit=True) as (_, cur):
        script = """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, name TEXT DEFAULT 'Участник', nickname TEXT DEFAULT '',
            coins INTEGER DEFAULT 0, soul_gems INTEGER DEFAULT 0, power INTEGER DEFAULT 0,
            job TEXT DEFAULT 'Отсутствует', job_level INTEGER DEFAULT 0, job_exp INTEGER DEFAULT 0,
            job_last_work TEXT, salary INTEGER DEFAULT 0, salary_multiplier REAL DEFAULT 1.0,
            housing TEXT DEFAULT 'Отсутствует', car TEXT DEFAULT 'Отсутствует', phone TEXT DEFAULT 'Отсутствует',
            warnings INTEGER DEFAULT 0, admin_warnings INTEGER DEFAULT 0, messages_total INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0, join_date TEXT DEFAULT (CURRENT_DATE), last_message_at TEXT,
            status TEXT DEFAULT '', profile_image TEXT DEFAULT '', gif_link TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS messages_stats (user_id INTEGER, date TEXT, count INTEGER DEFAULT 0, PRIMARY KEY(user_id, date));
        CREATE TABLE IF NOT EXISTS chat_message_stats (peer_id INTEGER, user_id INTEGER, date TEXT, count INTEGER DEFAULT 0, PRIMARY KEY(peer_id, user_id, date));
        CREATE TABLE IF NOT EXISTS chat_settings (peer_id INTEGER PRIMARY KEY, welcome_message TEXT DEFAULT '', welcome_photo TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS relationships (user_id INTEGER PRIMARY KEY, partner_id INTEGER, married INTEGER DEFAULT 0, family_surname TEXT DEFAULT '', relationship_since TEXT);
        CREATE TABLE IF NOT EXISTS warning_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, peer_id INTEGER, is_admin_warning INTEGER DEFAULT 0, created_at TEXT);
        CREATE TABLE IF NOT EXISTS kick_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, peer_id INTEGER, kicked_by INTEGER, created_at TEXT);
        CREATE TABLE IF NOT EXISTS admin_chat_rights (peer_id INTEGER, user_id INTEGER, level INTEGER, appointed_at TEXT, PRIMARY KEY (peer_id, user_id));
        CREATE TABLE IF NOT EXISTS global_roles (user_id INTEGER PRIMARY KEY, level INTEGER);
        CREATE TABLE IF NOT EXISTS chat_members (peer_id INTEGER, user_id INTEGER, first_join_at TEXT, invited_by INTEGER, PRIMARY KEY(peer_id, user_id));
        CREATE TABLE IF NOT EXISTS twinks (twink_id INTEGER PRIMARY KEY, owner_id INTEGER, added_at TEXT);
        CREATE TABLE IF NOT EXISTS duels (opponent_id INTEGER PRIMARY KEY, challenger_id INTEGER, peer_id INTEGER, message_id INTEGER, created_at TEXT);
        CREATE TABLE IF NOT EXISTS rp_photos (command TEXT, attachment TEXT, photo_id INTEGER, owner_id INTEGER, synced_at TEXT, PRIMARY KEY(command, photo_id, owner_id));
        CREATE TABLE IF NOT EXISTS recruit_settings (peer_id INTEGER, role_level INTEGER, is_open INTEGER DEFAULT 1, PRIMARY KEY(peer_id, role_level));
        CREATE TABLE IF NOT EXISTS norm_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, report_text TEXT, status TEXT DEFAULT 'pending', created_at TEXT, reviewed_by INTEGER, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS norm_photos (report_id INTEGER, attachment TEXT);
        CREATE TABLE IF NOT EXISTS admin_tags_stats (user_id INTEGER, peer_id INTEGER, tag_type TEXT, date TEXT, count INTEGER DEFAULT 0, PRIMARY KEY(user_id, peer_id, tag_type, date));
        CREATE TABLE IF NOT EXISTS family_children (id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER, child_id INTEGER, UNIQUE(parent_id, child_id));
        CREATE TABLE IF NOT EXISTS relationship_proposals (target_id INTEGER PRIMARY KEY, proposer_id INTEGER, created_at TEXT);
        CREATE TABLE IF NOT EXISTS marriage_proposals (target_id INTEGER PRIMARY KEY, proposer_id INTEGER, surname TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS family_proposals (target_id INTEGER PRIMARY KEY, proposer_id INTEGER, relation_type TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS applications (user_id INTEGER PRIMARY KEY, state TEXT, current_step INTEGER, answers TEXT, review_peer_id INTEGER, review_msg_id INTEGER, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS application_cooldowns (user_id INTEGER PRIMARY KEY, until_ts TEXT);
        CREATE TABLE IF NOT EXISTS chat_pins (peer_id INTEGER PRIMARY KEY, conversation_message_id INTEGER, message_id INTEGER, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS one_time_coin_grants (user_id INTEGER PRIMARY KEY, amount INTEGER, granted_at TEXT);
        CREATE TABLE IF NOT EXISTS coin_grant_scanned_chats (peer_id INTEGER PRIMARY KEY, scanned_at TEXT);

                CREATE TABLE IF NOT EXISTS internship_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, peer_id INTEGER, report_text TEXT, status TEXT DEFAULT 'pending', created_at TEXT, reviewed_by INTEGER, reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS admin_blacklist (user_id INTEGER PRIMARY KEY, added_by INTEGER, added_at TEXT);
        CREATE TABLE IF NOT EXISTS admin_weekly_stats (user_id INTEGER NOT NULL, week_key TEXT NOT NULL, messages INTEGER DEFAULT 0, invites INTEGER DEFAULT 0, reports INTEGER DEFAULT 0, gems_awarded INTEGER DEFAULT 0, PRIMARY KEY(user_id, week_key));
        CREATE TABLE IF NOT EXISTS power_message_rewards (user_id INTEGER PRIMARY KEY, claimed_thresholds INTEGER DEFAULT 0);
        """
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    logger.warning("Миграция: пропуск statement: %s (%s)", stmt[:60], e)


# --- Пользователи и ресурсы ---
def user_exists(user_id: int) -> bool:
    with db_cursor() as (_, cur):
        cur.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone() is not None

def create_user(user_id: int, name: str = "Участник"):
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT OR IGNORE INTO users (user_id, name, join_date) VALUES (?, ?, ?)", (user_id, name, date.today().isoformat()))
        cur.execute("INSERT OR IGNORE INTO relationships (user_id) VALUES (?)", (user_id,))

def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return cur.fetchone()

def update_coins(user_id: int, delta: int) -> bool:
    with db_cursor(commit=True) as (_, cur):
        if delta < 0:
            cur.execute("UPDATE users SET coins=coins+? WHERE user_id=? AND coins>=?", (delta, user_id, -delta))
            return cur.rowcount == 1
        cur.execute("UPDATE users SET coins=COALESCE(coins,0)+? WHERE user_id=?", (delta, user_id))
        return True

def update_power(user_id: int, delta: int):
    with db_cursor(commit=True) as (_, cur): cur.execute("UPDATE users SET power=COALESCE(power,0)+? WHERE user_id=?", (delta, user_id))

def update_gems(user_id: int, delta: int):
    with db_cursor(commit=True) as (_, cur): cur.execute("UPDATE users SET soul_gems=COALESCE(soul_gems,0)+? WHERE user_id=?", (delta, user_id))

def update_user_field(user_id: int, field: str, value: Any):
    allowed = {"nickname", "job", "job_level", "job_exp", "job_last_work", "salary", "salary_multiplier", "housing", "car", "phone", "profile_image", "status", "gif_link", "banned"}
    if field not in allowed: raise ValueError(f"Поле {field} нельзя обновлять")
    with db_cursor(commit=True) as (_, cur): cur.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))

def is_banned(user_id: int) -> bool:
    with db_cursor() as (_, cur):
        cur.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        return bool(row and row["banned"])

# --- Админка ---
def get_admin_level_for_chat(peer_id: int, user_id: int) -> int:
    with db_cursor() as (_, cur):
        cur.execute("SELECT level FROM admin_chat_rights WHERE peer_id=? AND user_id=?", (peer_id, user_id))
        row = cur.fetchone()
        return int(row["level"]) if row else 0

def set_admin_level(peer_id: int, user_id: int, level: int):
    with db_cursor(commit=True) as (_, cur):
        if level <= 0:
            cur.execute("DELETE FROM admin_chat_rights WHERE peer_id=? AND user_id=?", (peer_id, user_id))
        else:
            now = datetime.now().isoformat()
            # appointed_at обновляем только если роли не было или level изменился
            cur.execute(
                "INSERT INTO admin_chat_rights (peer_id, user_id, level, appointed_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(peer_id, user_id) DO UPDATE SET "
                "appointed_at=CASE WHEN admin_chat_rights.level!=excluded.level OR admin_chat_rights.appointed_at IS NULL "
                "THEN excluded.appointed_at ELSE admin_chat_rights.appointed_at END, "
                "level=excluded.level",
                (peer_id, user_id, level, now),
            )

def get_global_role(user_id: int) -> int:
    with db_cursor() as (_, cur):
        cur.execute("SELECT level FROM global_roles WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        return int(row["level"]) if row else 0

def set_global_role(user_id: int, level: int):
    with db_cursor(commit=True) as (_, cur):
        if level <= 0: cur.execute("DELETE FROM global_roles WHERE user_id=?", (user_id,))
        else: cur.execute("INSERT INTO global_roles (user_id, level) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET level=excluded.level", (user_id, level))

def get_all_global_roles():
    with db_cursor() as (_, cur):
        cur.execute("SELECT user_id, level FROM global_roles WHERE level>0")
        return cur.fetchall()

def get_admins_for_chat(peer_id: int):
    with db_cursor() as (_, cur):
        cur.execute("SELECT user_id, level FROM admin_chat_rights WHERE peer_id=? AND level>0", (peer_id,))
        return cur.fetchall()

def add_warning(user_id: int, peer_id: int, is_admin: bool = True) -> int:
    flag = 1 if is_admin else 0
    field = "admin_warnings" if is_admin else "warnings"
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT INTO warning_events (user_id, peer_id, is_admin_warning, created_at) VALUES (?, ?, ?, ?)", (user_id, peer_id, flag, datetime.now().isoformat()))
        cur.execute(f"UPDATE users SET {field}=COALESCE({field},0)+1 WHERE user_id=?", (user_id,))
        cur.execute(f"SELECT {field} FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        return int(row[0]) if row else 0

def remove_warning(user_id: int, peer_id: int, is_admin: bool = True) -> int:
    flag = 1 if is_admin else 0
    field = "admin_warnings" if is_admin else "warnings"
    with db_cursor(commit=True) as (_, cur):
        cur.execute("SELECT id FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=? ORDER BY id DESC LIMIT 1", (user_id, peer_id, flag))
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM warning_events WHERE id=?", (row["id"],))
            cur.execute(f"UPDATE users SET {field}=MAX(0, COALESCE({field},0)-1) WHERE user_id=?", (user_id,))
        cur.execute(f"SELECT {field} FROM users WHERE user_id=?", (user_id,))
        res = cur.fetchone()
        return int(res[0]) if res else 0

def clear_warnings(user_id: int, peer_id: int, is_admin: bool = True):
    flag = 1 if is_admin else 0
    field = "admin_warnings" if is_admin else "warnings"
    with db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=?", (user_id, peer_id, flag))
        cur.execute(f"UPDATE users SET {field}=0 WHERE user_id=?", (user_id,))

def add_kick_event(user_id: int, peer_id: int, kicked_by: int):
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT INTO kick_events (user_id, peer_id, kicked_by, created_at) VALUES (?, ?, ?, ?)", (user_id, peer_id, kicked_by, datetime.now().isoformat()))

def get_twinks(owner_id: int) -> list[int]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT twink_id FROM twinks WHERE owner_id=?", (owner_id,))
        return [r[0] for r in cur.fetchall()]

def add_twink(owner_id: int, twink_id: int):
    with db_cursor(commit=True) as (_, cur): cur.execute("INSERT OR IGNORE INTO twinks (twink_id, owner_id, added_at) VALUES (?, ?, ?)", (twink_id, owner_id, datetime.now().isoformat()))

def is_twink(user_id: int) -> bool:
    with db_cursor() as (_, cur):
        cur.execute("SELECT 1 FROM twinks WHERE twink_id=?", (user_id,))
        return cur.fetchone() is not None

# --- Активность ---
def add_message_count(user_id: int, peer_id: int):
    today = date.today().isoformat()
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT INTO messages_stats (user_id, date, count) VALUES (?, ?, 1) ON CONFLICT(user_id, date) DO UPDATE SET count=count+1", (user_id, today))
        cur.execute("INSERT INTO chat_message_stats (peer_id, user_id, date, count) VALUES (?, ?, ?, 1) ON CONFLICT(peer_id, user_id, date) DO UPDATE SET count=count+1", (peer_id, user_id, today))
        cur.execute("UPDATE users SET messages_total=COALESCE(messages_total,0)+1, last_message_at=? WHERE user_id=?", (datetime.now().isoformat(timespec="seconds"), user_id))

def get_messages_stats(user_id: int) -> dict:
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    month_start = today.replace(day=1).isoformat()
    with db_cursor() as (_, cur):
        def _sum(cond, params):
            cur.execute(f"SELECT SUM(count) FROM messages_stats WHERE user_id=? AND {cond}", (user_id, *params))
            res = cur.fetchone()
            return int(res[0]) if res and res[0] else 0
        cur.execute("SELECT messages_total FROM users WHERE user_id=?", (user_id,))
        total_row = cur.fetchone()
        total = int(total_row[0]) if total_row and total_row[0] else 0
        return {"today": _sum("date=?", (today.isoformat(),)), "week": _sum("date>=?", (week_start,)), "month": _sum("date>=?", (month_start,)), "total": total}

# --- Отчеты ---
def create_norm_report(user_id: int, text: str) -> int:
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT INTO norm_reports (user_id, report_text, created_at) VALUES (?, ?, ?)", (user_id, text, datetime.now().isoformat()))
        return cur.lastrowid or 0

def get_norm_report(report_id: int) -> Optional[sqlite3.Row]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT id, user_id, report_text, status, reviewed_by, reviewed_at, created_at FROM norm_reports WHERE id=?", (report_id,))
        return cur.fetchone()

def update_norm_status(report_id: int, status: str, reviewer_id: int):
    with db_cursor(commit=True) as (_, cur):
        cur.execute("UPDATE norm_reports SET status=?, reviewed_by=?, reviewed_at=? WHERE id=?", (status, reviewer_id, datetime.now().isoformat(), report_id))

# --- Чистка и беседы ---
def get_chat_user_week_messages(peer_id: int, user_id: int, start_date: str, end_date: str) -> int:
    with db_cursor() as (_, cur):
        cur.execute("SELECT SUM(count) FROM chat_message_stats WHERE peer_id=? AND user_id=? AND date>=? AND date<=?", (peer_id, user_id, start_date, end_date))
        res = cur.fetchone()
        return int(res[0]) if res and res[0] else 0

def get_chat_join_date(peer_id: int, user_id: int) -> Optional[str]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT first_join_at FROM chat_members WHERE peer_id=? AND user_id=?", (peer_id, user_id))
        row = cur.fetchone()
        return str(row["first_join_at"]) if row and row["first_join_at"] else None

def record_chat_join(peer_id: int, user_id: int, invited_by: Optional[int] = None):
    now = datetime.now().isoformat()
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT INTO chat_members (peer_id, user_id, first_join_at, invited_by) VALUES (?, ?, ?, ?) ON CONFLICT(peer_id, user_id) DO UPDATE SET invited_by=COALESCE(chat_members.invited_by, excluded.invited_by)", (peer_id, user_id, now, invited_by))

def get_all_chats():
    with db_cursor() as (_, cur):
        cur.execute("SELECT peer_id FROM chat_settings")
        return [r[0] for r in cur.fetchall()]

# --- Прочее ---
def ensure_chat(peer_id: int):
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT OR IGNORE INTO chat_settings (peer_id) VALUES (?)", (peer_id,))

def get_welcome_data(peer_id: int) -> tuple[str, str]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT welcome_message, welcome_photo FROM chat_settings WHERE peer_id=?", (peer_id,))
        row = cur.fetchone()
        return (str(row["welcome_message"]), str(row["welcome_photo"])) if row else ("", "")

def grant_one_time_coins(user_id: int, amount: int) -> bool:
    with db_cursor(commit=True) as (_, cur):
        try:
            cur.execute("INSERT INTO one_time_coin_grants (user_id, amount) VALUES (?, ?)", (user_id, amount))
        except sqlite3.IntegrityError:
            return False
        cur.execute("UPDATE users SET coins=COALESCE(coins,0)+? WHERE user_id=?", (amount, user_id))
        return True

def coin_grant_chat_scanned(peer_id: int) -> bool:
    with db_cursor() as (_, cur):
        cur.execute("SELECT 1 FROM coin_grant_scanned_chats WHERE peer_id=?", (peer_id,))
        return cur.fetchone() is not None

def mark_coin_grant_chat_scanned(peer_id: int):
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT OR IGNORE INTO coin_grant_scanned_chats (peer_id) VALUES (?)", (peer_id,))

# --- ЗАЯВКИ ---
def get_application(user_id: int) -> Optional[sqlite3.Row]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT * FROM applications WHERE user_id=?", (user_id,))
        return cur.fetchone()

def set_application(user_id: int, state: str, step: int, answers: list, review_peer_id: Optional[int] = None, review_msg_id: Optional[int] = None):
    now = datetime.now().isoformat()
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT INTO applications (user_id, state, current_step, answers, review_peer_id, review_msg_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, current_step=excluded.current_step, answers=excluded.answers, review_peer_id=excluded.review_peer_id, review_msg_id=excluded.review_msg_id, updated_at=excluded.updated_at", (user_id, state, step, json.dumps(answers, ensure_ascii=False), review_peer_id, review_msg_id, now, now))

def delete_application(user_id: int):
    with db_cursor(commit=True) as (_, cur): cur.execute("DELETE FROM applications WHERE user_id=?", (user_id,))

# --- ЗАКРЕПЫ ---
def get_chat_pin(peer_id: int) -> Optional[sqlite3.Row]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT conversation_message_id, message_id FROM chat_pins WHERE peer_id=?", (peer_id,))
        return cur.fetchone()

def set_chat_pin(peer_id: int, cmid: Optional[int], mid: Optional[int]):
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT INTO chat_pins (peer_id, conversation_message_id, message_id, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(peer_id) DO UPDATE SET conversation_message_id=COALESCE(excluded.conversation_message_id, chat_pins.conversation_message_id), message_id=COALESCE(excluded.message_id, chat_pins.message_id), updated_at=excluded.updated_at", (peer_id, cmid, mid, datetime.now().isoformat()))

# --- РП ФОТО ---
def get_random_rp_photo(command: str) -> Optional[str]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT attachment FROM rp_photos WHERE command=? ORDER BY RANDOM() LIMIT 1", (command,))
        row = cur.fetchone()
        return str(row[0]) if row else None

def replace_rp_photos(command: str, photos: list[tuple[str, int, int]]):
    with db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM rp_photos WHERE command=?", (command,))
        now = datetime.now().isoformat()
        for att, pid, oid in photos:
            cur.execute("INSERT OR IGNORE INTO rp_photos (command, attachment, photo_id, owner_id, synced_at) VALUES (?, ?, ?, ?, ?)", (command, att, pid, oid, now))


# --- Дополнения из старого бота ---

def annul_warnings(user_id: int, peer_id: int):
    clear_warnings(user_id, peer_id, True)

def get_warning_stats(user_id: int, is_admin: bool = False) -> dict:
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    month_start = today.replace(day=1).isoformat()
    flag = 1 if is_admin else 0
    with db_cursor() as (_, cur):
        def _c(cond, params):
            cur.execute(
                f"SELECT COUNT(*) FROM warning_events WHERE user_id=? AND is_admin_warning=? AND {cond}",
                (user_id, flag, *params),
            )
            r = cur.fetchone()
            return int(r[0]) if r and r[0] else 0
        total = _c("1=1", ())
        week = _c("date(created_at)>=?", (week_start,))
        month = _c("date(created_at)>=?", (month_start,))
        return {"today": 0, "week": week, "month": month, "total": total}

def get_kick_stats(user_id: int) -> dict:
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    month_start = today.replace(day=1).isoformat()
    with db_cursor() as (_, cur):
        def _c(cond, params):
            cur.execute(f"SELECT COUNT(*) FROM kick_events WHERE user_id=? AND {cond}", (user_id, *params))
            r = cur.fetchone()
            return int(r[0]) if r and r[0] else 0
        return {
            "week": _c("date(created_at)>=?", (week_start,)),
            "month": _c("date(created_at)>=?", (month_start,)),
            "total": _c("1=1", ()),
        }

def ban_user(user_id: int):
    update_user_field(user_id, "banned", 1)

def unban_user(user_id: int):
    update_user_field(user_id, "banned", 0)

def get_banned_users() -> list:
    with db_cursor() as (_, cur):
        cur.execute("SELECT user_id FROM users WHERE banned=1")
        return [int(r["user_id"]) for r in cur.fetchall()]

def set_welcome_message(peer_id: int, message: str, photo: str = ""):
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT INTO chat_settings (peer_id, welcome_message, welcome_photo) VALUES (?,?,?) "
            "ON CONFLICT(peer_id) DO UPDATE SET welcome_message=excluded.welcome_message, welcome_photo=excluded.welcome_photo",
            (peer_id, message, photo),
        )

def get_first_inviter(user_id: int):
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT invited_by FROM chat_members WHERE user_id=? AND invited_by IS NOT NULL ORDER BY first_join_at LIMIT 1",
            (user_id,),
        )
        r = cur.fetchone()
        return int(r["invited_by"]) if r and r["invited_by"] else None

def get_last_message_at(user_id: int):
    with db_cursor() as (_, cur):
        cur.execute("SELECT last_message_at FROM users WHERE user_id=?", (user_id,))
        r = cur.fetchone()
        return r["last_message_at"] if r else None

def add_to_admin_blacklist(user_id: int, added_by: int):
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT INTO admin_blacklist(user_id, added_by, added_at) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET added_by=excluded.added_by, added_at=excluded.added_at",
            (user_id, added_by, datetime.now().isoformat()),
        )

def remove_from_admin_blacklist(user_id: int):
    with db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM admin_blacklist WHERE user_id=?", (user_id,))

def is_in_admin_blacklist(user_id: int) -> bool:
    with db_cursor() as (_, cur):
        cur.execute("SELECT 1 FROM admin_blacklist WHERE user_id=?", (user_id,))
        return cur.fetchone() is not None

def set_profile_image(user_id: int, attachment: str):
    update_user_field(user_id, "profile_image", attachment)

def set_gif_link(user_id: int, link: str):
    update_user_field(user_id, "gif_link", link)

def set_status(user_id: int, status: str):
    update_user_field(user_id, "status", status)

def get_warning_count(user_id: int, peer_id: int) -> int:
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT COUNT(*) FROM warning_events WHERE user_id=? AND peer_id=? AND is_admin_warning=1",
            (user_id, peer_id),
        )
        r = cur.fetchone()
        return int(r[0]) if r and r[0] else 0

def get_owner(twink_id: int):
    with db_cursor() as (_, cur):
        cur.execute("SELECT owner_id FROM twinks WHERE twink_id=?", (twink_id,))
        r = cur.fetchone()
        return int(r["owner_id"]) if r else None

def remove_twink(twink_id: int):
    with db_cursor(commit=True) as (_, cur):
        cur.execute("DELETE FROM twinks WHERE twink_id=?", (twink_id,))

def get_rp_photo_count(command: str = None) -> int:
    with db_cursor() as (_, cur):
        if command:
            cur.execute("SELECT COUNT(*) FROM rp_photos WHERE command=?", (command,))
        else:
            cur.execute("SELECT COUNT(*) FROM rp_photos")
        r = cur.fetchone()
        return int(r[0]) if r and r[0] else 0

def _week_key() -> str:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    return start.isoformat()

def add_admin_stat(user_id: int, field: str, amount: int = 1):
    allowed = {"messages", "invites", "reports", "gems_awarded"}
    if field not in allowed:
        return
    wk = _week_key()
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            f"INSERT INTO admin_weekly_stats (user_id, week_key, {field}) VALUES (?,?,?) "
            f"ON CONFLICT(user_id, week_key) DO UPDATE SET {field}=COALESCE(admin_weekly_stats.{field},0)+?",
            (user_id, wk, amount, amount),
        )

def get_admin_week_stats(user_id: int) -> dict:
    wk = _week_key()
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT messages, invites, reports, gems_awarded FROM admin_weekly_stats WHERE user_id=? AND week_key=?",
            (user_id, wk),
        )
        r = cur.fetchone()
        if not r:
            return {"messages": 0, "invites": 0, "reports": 0, "gems_awarded": 0}
        return {k: int(r[k] or 0) for k in ("messages", "invites", "reports", "gems_awarded")}

def get_all_admin_week_stats() -> list:
    wk = _week_key()
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT user_id, messages, invites, reports, gems_awarded FROM admin_weekly_stats WHERE week_key=?",
            (wk,),
        )
        return cur.fetchall()

def toggle_recruit_role(peer_id: int, role_level: int) -> bool:
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "SELECT is_open FROM recruit_settings WHERE peer_id=? AND role_level=?",
            (peer_id, role_level),
        )
        r = cur.fetchone()
        if r:
            new_val = 0 if r["is_open"] else 1
            cur.execute(
                "UPDATE recruit_settings SET is_open=? WHERE peer_id=? AND role_level=?",
                (new_val, peer_id, role_level),
            )
            return bool(new_val)
        cur.execute(
            "INSERT INTO recruit_settings (peer_id, role_level, is_open) VALUES (?,?,1)",
            (peer_id, role_level),
        )
        return True

def get_recruit_settings(peer_id: int) -> dict:
    with db_cursor() as (_, cur):
        cur.execute("SELECT role_level, is_open FROM recruit_settings WHERE peer_id=?", (peer_id,))
        rows = cur.fetchall()
        return {int(r["role_level"]): bool(r["is_open"]) for r in rows}


def add_norm_photo(report_id: int, attachment: str) -> None:
    with db_cursor(commit=True) as (_, cur):
        cur.execute("INSERT INTO norm_photos (report_id, attachment) VALUES (?, ?)", (report_id, attachment))

def get_norm_photos(report_id: int) -> list[str]:
    with db_cursor() as (_, cur):
        cur.execute("SELECT attachment FROM norm_photos WHERE report_id=?", (report_id,))
        return [str(r["attachment"]) for r in cur.fetchall() if r["attachment"]]

def get_admin_tags_stats(user_id: int, week_start: str) -> dict:
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT tag_type, SUM(count) as c FROM admin_tags_stats "
            "WHERE user_id=? AND date>=? GROUP BY tag_type",
            (user_id, week_start),
        )
        rows = cur.fetchall()
        return {str(r["tag_type"]): int(r["c"] or 0) for r in rows}

def get_user_admin_chats(user_id: int) -> list[tuple[int, int]]:
    """Список (peer_id, level) где у пользователя есть локальные права."""
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT peer_id, level FROM admin_chat_rights WHERE user_id=? AND level>0",
            (user_id,),
        )
        return [(int(r["peer_id"]), int(r["level"])) for r in cur.fetchall()]


def create_internship_report(user_id: int, peer_id: int, text: str) -> int:
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "INSERT INTO internship_reports (user_id, peer_id, report_text, created_at) VALUES (?,?,?,?)",
            (user_id, peer_id, text, datetime.now().isoformat()),
        )
        return cur.lastrowid or 0

def get_internship_report(report_id: int):
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT id, user_id, peer_id, report_text, status, reviewed_by, reviewed_at FROM internship_reports WHERE id=?",
            (report_id,),
        )
        return cur.fetchone()

def update_internship_status(report_id: int, status: str, reviewer_id: int):
    with db_cursor(commit=True) as (_, cur):
        cur.execute(
            "UPDATE internship_reports SET status=?, reviewed_by=?, reviewed_at=? WHERE id=?",
            (status, reviewer_id, datetime.now().isoformat(), report_id),
        )


def get_admin_appointed_at(peer_id: int, user_id: int) -> Optional[str]:
    with db_cursor() as (_, cur):
        try:
            cur.execute(
                "SELECT appointed_at FROM admin_chat_rights WHERE peer_id=? AND user_id=?",
                (peer_id, user_id),
            )
            r = cur.fetchone()
            return r["appointed_at"] if r and r["appointed_at"] else None
        except Exception:
            return None

def ensure_admin_appointed_column():
    """Мягкая миграция appointed_at для старых БД."""
    with db_cursor(commit=True) as (_, cur):
        try:
            cur.execute("ALTER TABLE admin_chat_rights ADD COLUMN appointed_at TEXT")
        except Exception:
            pass
