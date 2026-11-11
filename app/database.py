"""
TRAPWIRE — MySQL Database Engine with Automatic SQLite Fallback
Provides relational persistence for Orders, Security Alerts, Incidents,
Canary Telemetry, DPDP Reports, Team Users, Projects, and Audit Logs.
"""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pymysql
    import pymysql.cursors
    HAVE_PYMYSQL = True
except ImportError:
    HAVE_PYMYSQL = False


def _load_dotenv() -> None:
    """Load key=value pairs from .env if present without overriding existing env vars."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, val)
    except OSError:
        pass


_load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "trapwire_db")

DB_PATH = str(Path(__file__).resolve().parent.parent / "trapwire.db")
DB_ENGINE = "uninitialized"  # "mysql" | "sqlite"


def get_mysql_connection():
    """Return a PyMySQL DictCursor connection to trapwire_db, or None if unreachable."""
    if not HAVE_PYMYSQL:
        return None
    conn = None
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=2,
        )
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.select_db(MYSQL_DATABASE)
        return conn
    except Exception:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        return None


def get_sqlite_connection() -> sqlite3.Connection:
    """Return a short-lived SQLite connection with Row factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _db_cursor(commit: bool = False):
    """Yield (engine, cursor) using MySQL when active/reachable, else SQLite, always closing."""
    global DB_ENGINE
    if DB_ENGINE == "mysql":
        conn = get_mysql_connection()
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    yield "mysql", cur
                if commit:
                    conn.commit()
                return
            finally:
                conn.close()

    conn = get_sqlite_connection()
    try:
        cur = conn.cursor()
        yield "sqlite", cur
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Initialize tables in MySQL if reachable, else fall back to SQLite."""
    global DB_ENGINE
    mysql_conn = get_mysql_connection()
    if mysql_conn is not None:
        DB_ENGINE = "mysql"
        print(f"[DATABASE] Connected to MySQL Server at {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
        try:
            with mysql_conn.cursor() as cursor:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `orders` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `order_id` VARCHAR(32) NOT NULL UNIQUE,
                    `customer_name` VARCHAR(128) NOT NULL,
                    `phone` VARCHAR(32),
                    `email` VARCHAR(128),
                    `aadhaar` VARCHAR(32),
                    `pan` VARCHAR(32),
                    `address` TEXT,
                    `card_last4` VARCHAR(16),
                    `item` VARCHAR(128),
                    `order_value` DECIMAL(10, 2),
                    `status` VARCHAR(32) DEFAULT 'Pending',
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `alerts` (
                    `id` VARCHAR(32) PRIMARY KEY,
                    `message` TEXT NOT NULL,
                    `level` VARCHAR(16) NOT NULL,
                    `timestamp` DOUBLE NOT NULL,
                    `meta_json` TEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `incidents` (
                    `incident_id` VARCHAR(32) PRIMARY KEY,
                    `attacker_ip` VARCHAR(64),
                    `attacker_isp` VARCHAR(128),
                    `attacker_location` VARCHAR(128),
                    `detected_at` DOUBLE,
                    `status` VARCHAR(32),
                    `stage` VARCHAR(32),
                    `ack_number` VARCHAR(64)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `canary_hits` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `token` VARCHAR(64) NOT NULL,
                    `ip` VARCHAR(64),
                    `isp` VARCHAR(128),
                    `city` VARCHAR(64),
                    `country` VARCHAR(64),
                    `user_agent` TEXT,
                    `screen` VARCHAR(32),
                    `timezone` VARCHAR(64),
                    `language` VARCHAR(32),
                    `platform` VARCHAR(64),
                    `cores` VARCHAR(32),
                    `triggered_at` DOUBLE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `submitted_reports` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `incident_id` VARCHAR(32) NOT NULL,
                    `stage` VARCHAR(32) NOT NULL,
                    `filename` VARCHAR(255) NOT NULL,
                    `ack_number` VARCHAR(64) NOT NULL UNIQUE,
                    `ack_status` VARCHAR(32) NOT NULL,
                    `attacker_ip` VARCHAR(64),
                    `attacker_isp` VARCHAR(128),
                    `detected_at` DOUBLE,
                    `submitted_at` DOUBLE NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `users` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `name` VARCHAR(128) NOT NULL,
                    `email` VARCHAR(128) NOT NULL UNIQUE,
                    `role` VARCHAR(64) DEFAULT 'Analyst',
                    `status` VARCHAR(32) DEFAULT 'Active',
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `projects` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `name` VARCHAR(128) NOT NULL,
                    `client` VARCHAR(128) NOT NULL,
                    `owner` VARCHAR(128) NOT NULL,
                    `deadline` VARCHAR(32),
                    `budget` DECIMAL(12, 2) DEFAULT 0,
                    `progress` INT DEFAULT 0,
                    `status` VARCHAR(32) DEFAULT 'Planning',
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `sms_audit` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `recipient` VARCHAR(32) NOT NULL,
                    `message` TEXT NOT NULL,
                    `status` VARCHAR(32) DEFAULT 'DISPATCHED',
                    `sent_at` DOUBLE NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                _migrate_schema(cursor, "mysql")
            mysql_conn.commit()
            return
        except Exception as e:
            print(f"[DATABASE ERROR] Failed initializing MySQL tables, falling back to SQLite: {e}")
        finally:
            mysql_conn.close()

    DB_ENGINE = "sqlite"
    print(
        f"[DATABASE] MySQL server not reachable on {MYSQL_HOST}:{MYSQL_PORT}. "
        "Falling back to persistent SQLite Engine (trapwire.db)."
    )
    conn = get_sqlite_connection()
    try:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            aadhaar TEXT,
            pan TEXT,
            address TEXT,
            card_last4 TEXT,
            item TEXT,
            order_value REAL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            message TEXT NOT NULL,
            level TEXT NOT NULL,
            timestamp REAL NOT NULL,
            meta_json TEXT
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY,
            attacker_ip TEXT,
            attacker_isp TEXT,
            attacker_location TEXT,
            detected_at REAL,
            status TEXT,
            stage TEXT,
            ack_number TEXT
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS canary_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            ip TEXT,
            isp TEXT,
            city TEXT,
            country TEXT,
            user_agent TEXT,
            screen TEXT,
            timezone TEXT,
            language TEXT,
            platform TEXT,
            cores TEXT,
            triggered_at REAL
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS submitted_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            filename TEXT NOT NULL,
            ack_number TEXT NOT NULL UNIQUE,
            ack_status TEXT NOT NULL,
            attacker_ip TEXT,
            attacker_isp TEXT,
            detected_at REAL,
            submitted_at REAL NOT NULL
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT DEFAULT 'Analyst',
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            client TEXT NOT NULL,
            owner TEXT NOT NULL,
            deadline TEXT,
            budget REAL DEFAULT 0,
            progress INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Planning',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS sms_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'DISPATCHED',
            sent_at REAL NOT NULL
        );
        """)
        _migrate_schema(c, "sqlite")
        conn.commit()
    finally:
        conn.close()


_SCHEMA_ADDITIONS = {
    "users": [
        ("role", "VARCHAR(64) DEFAULT 'Analyst'", "TEXT DEFAULT 'Analyst'"),
        ("status", "VARCHAR(32) DEFAULT 'Active'", "TEXT DEFAULT 'Active'"),
    ],
    "alerts": [
        ("meta_json", "TEXT", "TEXT"),
    ],
    "incidents": [
        ("attacker_isp", "VARCHAR(128)", "TEXT"),
        ("attacker_location", "VARCHAR(128)", "TEXT"),
        ("status", "VARCHAR(32)", "TEXT"),
        ("stage", "VARCHAR(32)", "TEXT"),
        ("ack_number", "VARCHAR(64)", "TEXT"),
    ],
    "canary_hits": [
        ("city", "VARCHAR(64)", "TEXT"),
        ("country", "VARCHAR(64)", "TEXT"),
        ("screen", "VARCHAR(32)", "TEXT"),
        ("timezone", "VARCHAR(64)", "TEXT"),
        ("language", "VARCHAR(32)", "TEXT"),
        ("platform", "VARCHAR(64)", "TEXT"),
        ("cores", "VARCHAR(32)", "TEXT"),
    ],
    "submitted_reports": [
        ("attacker_ip", "VARCHAR(64)", "TEXT"),
        ("attacker_isp", "VARCHAR(128)", "TEXT"),
        ("detected_at", "DOUBLE", "REAL"),
    ],
}


def _migrate_schema(cur, engine: str) -> None:
    """Safely add newly introduced columns to pre-existing tables."""
    for table, cols in _SCHEMA_ADDITIONS.items():
        if engine == "mysql":
            cur.execute(f"SHOW COLUMNS FROM `{table}`")
            existing = {r["Field"] for r in cur.fetchall()}
            for col, mysql_def, _sqlite_def in cols:
                if col not in existing:
                    cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {mysql_def}")
        else:
            cur.execute(f"PRAGMA table_info({table})")
            existing = {r["name"] for r in cur.fetchall()}
            for col, _mysql_def, sqlite_def in cols:
                if col not in existing:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {sqlite_def}")


# ------------------------------------------------------------------ alerts --
def db_save_alert(alert: Dict[str, Any]) -> None:
    meta_json = json.dumps(alert.get("meta", {}))
    with _db_cursor(commit=True) as (eng, cur):
        if eng == "mysql":
            cur.execute(
                "INSERT INTO alerts (id, message, level, timestamp, meta_json) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE message=%s, level=%s, meta_json=%s",
                (
                    alert["id"], alert["message"], alert["level"],
                    alert["timestamp"], meta_json,
                    alert["message"], alert["level"], meta_json,
                ),
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO alerts (id, message, level, timestamp, meta_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (alert["id"], alert["message"], alert["level"], alert["timestamp"], meta_json),
            )


def db_get_alerts(limit: int = 100) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with _db_cursor(commit=False) as (eng, cur):
            ph = "%s" if eng == "mysql" else "?"
            cur.execute(
                f"SELECT id, message, level, timestamp, meta_json FROM alerts "
                f"ORDER BY timestamp ASC LIMIT {ph}",
                (limit,),
            )
            for r in cur.fetchall():
                try:
                    meta = json.loads(r["meta_json"] or "{}")
                except Exception:
                    meta = {}
                rows.append({
                    "id": r["id"],
                    "message": r["message"],
                    "level": r["level"],
                    "timestamp": float(r["timestamp"]),
                    "meta": meta,
                })
    except Exception as e:
        print(f"[DB] Error loading alerts: {e}")
    return rows


# --------------------------------------------------------------- incidents --
def db_save_incident(breach: Dict[str, Any], stage: str = "preliminary", ack_number: str = "") -> None:
    inc_id = breach.get("incident_id")
    if not inc_id:
        return
    ip = breach.get("download_ip") or breach.get("attacker_ip") or ""
    isp = breach.get("download_isp") or breach.get("attacker_isp") or ""
    loc = breach.get("attacker_location") or ""
    detected_at = float(breach.get("detected_at") or time.time())
    with _db_cursor(commit=True) as (eng, cur):
        if eng == "mysql":
            cur.execute(
                "INSERT INTO incidents (incident_id, attacker_ip, attacker_isp, attacker_location, "
                "detected_at, status, stage, ack_number) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE attacker_ip=%s, attacker_isp=%s, attacker_location=%s, "
                "status=%s, stage=%s, ack_number=%s",
                (
                    inc_id, ip, isp, loc, detected_at, "OPEN", stage, ack_number,
                    ip, isp, loc, "OPEN", stage, ack_number,
                ),
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO incidents (incident_id, attacker_ip, attacker_isp, "
                "attacker_location, detected_at, status, stage, ack_number) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (inc_id, ip, isp, loc, detected_at, "OPEN", stage, ack_number),
            )


def db_get_latest_incident() -> Dict[str, Any]:
    try:
        with _db_cursor(commit=False) as (_eng, cur):
            cur.execute(
                "SELECT incident_id, attacker_ip, attacker_isp, attacker_location, "
                "detected_at, status, stage, ack_number FROM incidents "
                "ORDER BY detected_at DESC LIMIT 1"
            )
            r = cur.fetchone()
            if r:
                return dict(r)
    except Exception as e:
        print(f"[DB] Error loading latest incident: {e}")
    return {}


# ------------------------------------------------------------- canary_hits --
def db_save_canary_hit(hit: Dict[str, Any]) -> None:
    with _db_cursor(commit=True) as (eng, cur):
        ph = ", ".join(["%s"] * 12) if eng == "mysql" else ", ".join(["?"] * 12)
        cur.execute(
            f"INSERT INTO canary_hits (token, ip, isp, city, country, user_agent, "
            f"screen, timezone, language, platform, cores, triggered_at) VALUES ({ph})",
            (
                hit.get("token", ""),
                hit.get("ip", ""),
                hit.get("isp", ""),
                hit.get("city", ""),
                hit.get("country", ""),
                hit.get("user_agent", ""),
                str(hit.get("screen") or ""),
                str(hit.get("timezone") or ""),
                str(hit.get("language") or ""),
                str(hit.get("platform") or ""),
                str(hit.get("cores") or ""),
                float(hit.get("timestamp") or time.time()),
            ),
        )


def db_update_canary_hit(hit: Dict[str, Any]) -> None:
    with _db_cursor(commit=True) as (eng, cur):
        ph = "%s" if eng == "mysql" else "?"
        cur.execute(
            f"UPDATE canary_hits SET screen={ph}, timezone={ph}, language={ph}, "
            f"platform={ph}, cores={ph} WHERE token={ph}",
            (
                str(hit.get("screen") or ""),
                str(hit.get("timezone") or ""),
                str(hit.get("language") or ""),
                str(hit.get("platform") or ""),
                str(hit.get("cores") or ""),
                hit.get("token", ""),
            ),
        )


def db_get_canary_hits(limit: int = 50) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with _db_cursor(commit=False) as (eng, cur):
            ph = "%s" if eng == "mysql" else "?"
            cur.execute(
                f"SELECT token, ip, isp, city, country, user_agent, screen, timezone, "
                f"language, platform, cores, triggered_at FROM canary_hits "
                f"ORDER BY triggered_at ASC LIMIT {ph}",
                (limit,),
            )
            for r in cur.fetchall():
                rows.append({
                    "token": r["token"],
                    "ip": r["ip"],
                    "isp": r["isp"],
                    "city": r["city"],
                    "country": r["country"],
                    "user_agent": r["user_agent"],
                    "screen": r["screen"] or None,
                    "timezone": r["timezone"] or None,
                    "language": r["language"] or None,
                    "platform": r["platform"] or None,
                    "cores": r["cores"] or None,
                    "timestamp": float(r["triggered_at"] or 0),
                })
    except Exception as e:
        print(f"[DB] Error loading canary hits: {e}")
    return rows


# ------------------------------------------------------- submitted_reports --
def db_save_submitted_report(record: Dict[str, Any]) -> None:
    with _db_cursor(commit=True) as (eng, cur):
        if eng == "mysql":
            cur.execute(
                "INSERT INTO submitted_reports (incident_id, stage, filename, ack_number, "
                "ack_status, attacker_ip, attacker_isp, detected_at, submitted_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE ack_status=%s",
                (
                    record["incident_id"], record["stage"], record["filename"],
                    record["ack_number"], record.get("ack_status", "ACKNOWLEDGED"),
                    record.get("attacker_ip", ""), record.get("attacker_isp", ""),
                    record.get("detected_at"), record["submitted_at"],
                    record.get("ack_status", "ACKNOWLEDGED"),
                ),
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO submitted_reports (incident_id, stage, filename, "
                "ack_number, ack_status, attacker_ip, attacker_isp, detected_at, submitted_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["incident_id"], record["stage"], record["filename"],
                    record["ack_number"], record.get("ack_status", "ACKNOWLEDGED"),
                    record.get("attacker_ip", ""), record.get("attacker_isp", ""),
                    record.get("detected_at"), record["submitted_at"],
                ),
            )


def db_get_submitted_reports(limit: int = 50) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with _db_cursor(commit=False) as (eng, cur):
            ph = "%s" if eng == "mysql" else "?"
            cur.execute(
                f"SELECT incident_id, stage, filename, ack_number, ack_status, "
                f"attacker_ip, attacker_isp, detected_at, submitted_at "
                f"FROM submitted_reports ORDER BY submitted_at ASC LIMIT {ph}",
                (limit,),
            )
            for r in cur.fetchall():
                ack = r["ack_number"]
                fn = r["filename"]
                rows.append({
                    "incident_id": r["incident_id"],
                    "stage": r["stage"],
                    "filename": fn,
                    "ack_number": ack,
                    "ack_status": r["ack_status"],
                    "status": r["ack_status"],
                    "company_name": "TrapWire Pvt Ltd",
                    "attacker_ip": r["attacker_ip"] or None,
                    "attacker_isp": r["attacker_isp"] or None,
                    "detected_at": r["detected_at"],
                    "submitted_at": float(r["submitted_at"]),
                    "received_at": float(r["submitted_at"]),
                    "download_url": f"/api/submitted-reports/{fn}",
                    "dpb_url": f"/dpb/submission/{ack}",
                })
    except Exception as e:
        print(f"[DB] Error loading submitted reports: {e}")
    return rows


# ------------------------------------------------------------------ orders --
def db_save_order(order: Dict[str, Any]) -> None:
    order_val = float(order.get("order_value") or 0.0)
    with _db_cursor(commit=True) as (eng, cur):
        if eng == "mysql":
            cur.execute(
                """INSERT INTO orders
                (order_id, customer_name, phone, email, aadhaar, pan, address, card_last4, item, order_value, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                customer_name=%s, phone=%s, email=%s, aadhaar=%s, pan=%s, address=%s,
                card_last4=%s, item=%s, order_value=%s, status=%s""",
                (
                    order["order_id"], order.get("customer_name", ""), order.get("phone", ""),
                    order.get("email", ""), order.get("aadhaar", ""), order.get("pan", ""),
                    order.get("address", ""), order.get("card_last4", ""), order.get("item", ""),
                    order_val, order.get("status", "Pending"),
                    order.get("customer_name", ""), order.get("phone", ""),
                    order.get("email", ""), order.get("aadhaar", ""), order.get("pan", ""),
                    order.get("address", ""), order.get("card_last4", ""), order.get("item", ""),
                    order_val, order.get("status", "Pending"),
                ),
            )
        else:
            cur.execute(
                """INSERT OR REPLACE INTO orders
                (order_id, customer_name, phone, email, aadhaar, pan, address, card_last4, item, order_value, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order["order_id"], order.get("customer_name", ""), order.get("phone", ""),
                    order.get("email", ""), order.get("aadhaar", ""), order.get("pan", ""),
                    order.get("address", ""), order.get("card_last4", ""), order.get("item", ""),
                    order_val, order.get("status", "Pending"),
                ),
            )


def db_delete_order(order_id: str) -> bool:
    with _db_cursor(commit=True) as (eng, cur):
        ph = "%s" if eng == "mysql" else "?"
        cur.execute(f"DELETE FROM orders WHERE order_id = {ph}", (order_id,))
        return (cur.rowcount or 0) > 0


def db_get_orders() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with _db_cursor(commit=False) as (_eng, cur):
            cur.execute(
                "SELECT order_id, customer_name, phone, email, aadhaar, pan, "
                "address, card_last4, item, order_value, status "
                "FROM orders ORDER BY id DESC"
            )
            for r in cur.fetchall():
                rows.append({
                    "order_id": r["order_id"],
                    "customer_name": r["customer_name"],
                    "phone": r["phone"] or "",
                    "email": r["email"] or "",
                    "aadhaar": r["aadhaar"] or "",
                    "pan": r["pan"] or "",
                    "address": r["address"] or "",
                    "card_last4": r["card_last4"] or "",
                    "item": r["item"] or "",
                    "order_value": float(r["order_value"] or 0),
                    "status": r["status"] or "Processing",
                })
    except Exception as e:
        print(f"[DB] Error loading orders: {e}")
    return rows


# ------------------------------------------------------------------- users --
def db_get_users() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with _db_cursor(commit=False) as (_eng, cur):
            cur.execute("SELECT id, name, email, role, status FROM users ORDER BY id DESC")
            for r in cur.fetchall():
                rows.append({
                    "id": r["id"],
                    "name": r["name"],
                    "email": r["email"],
                    "role": r["role"] or "Analyst",
                    "status": r["status"] or "Active",
                })
    except Exception as e:
        print(f"[DB] Error loading users: {e}")
    return rows


def db_save_user(user: Dict[str, Any]) -> Dict[str, Any]:
    with _db_cursor(commit=True) as (eng, cur):
        if eng == "mysql":
            cur.execute(
                "INSERT INTO users (name, email, role, status) VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE name=%s, role=%s, status=%s",
                (
                    user["name"], user["email"], user.get("role", "Analyst"),
                    user.get("status", "Invited"),
                    user["name"], user.get("role", "Analyst"), user.get("status", "Invited"),
                ),
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO users (name, email, role, status) VALUES (?, ?, ?, ?)",
                (user["name"], user["email"], user.get("role", "Analyst"), user.get("status", "Invited")),
            )
    return user


def db_delete_user(email: str) -> bool:
    with _db_cursor(commit=True) as (eng, cur):
        ph = "%s" if eng == "mysql" else "?"
        cur.execute(f"DELETE FROM users WHERE email = {ph}", (email,))
        return (cur.rowcount or 0) > 0


# ---------------------------------------------------------------- projects --
def db_get_projects() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with _db_cursor(commit=False) as (_eng, cur):
            cur.execute(
                "SELECT id, name, client, owner, deadline, budget, progress, status "
                "FROM projects ORDER BY id DESC"
            )
            for r in cur.fetchall():
                rows.append({
                    "id": r["id"],
                    "name": r["name"],
                    "client": r["client"],
                    "owner": r["owner"],
                    "deadline": r["deadline"] or "",
                    "budget": float(r["budget"] or 0),
                    "progress": int(r["progress"] or 0),
                    "status": r["status"] or "Planning",
                })
    except Exception as e:
        print(f"[DB] Error loading projects: {e}")
    return rows


def db_save_project(proj: Dict[str, Any]) -> Dict[str, Any]:
    with _db_cursor(commit=True) as (eng, cur):
        ph = ", ".join(["%s"] * 7) if eng == "mysql" else ", ".join(["?"] * 7)
        cur.execute(
            f"INSERT INTO projects (name, client, owner, deadline, budget, progress, status) "
            f"VALUES ({ph})",
            (
                proj["name"],
                proj["client"],
                proj["owner"],
                proj.get("deadline", ""),
                float(proj.get("budget") or 0),
                int(proj.get("progress") or 0),
                proj.get("status", "Planning"),
            ),
        )
        proj["id"] = cur.lastrowid
    return proj


def db_delete_project(project_id: int) -> bool:
    with _db_cursor(commit=True) as (eng, cur):
        ph = "%s" if eng == "mysql" else "?"
        cur.execute(f"DELETE FROM projects WHERE id = {ph}", (project_id,))
        return (cur.rowcount or 0) > 0


# --------------------------------------------------------------- audit/sms --
def db_save_sms(recipient: str, message: str, status: str = "DISPATCHED") -> None:
    sent_at = time.time()
    with _db_cursor(commit=True) as (eng, cur):
        ph = ", ".join(["%s"] * 4) if eng == "mysql" else ", ".join(["?"] * 4)
        cur.execute(
            f"INSERT INTO sms_audit (recipient, message, status, sent_at) VALUES ({ph})",
            (recipient, message, status, sent_at),
        )


def db_reset_runtime_telemetry() -> None:
    """Clear runtime incident/alert telemetry while preserving orders, users, and projects."""
    with _db_cursor(commit=True) as (_eng, cur):
        for tbl in ("alerts", "incidents", "canary_hits", "submitted_reports"):
            cur.execute(f"DELETE FROM {tbl}")
