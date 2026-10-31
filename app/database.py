"""
TRAPWIRE — MySQL Database Engine with Intelligent SQLite Fallback
Provides full relational storage for Orders, Security Alerts, Incidents,
Canary Telemetry, DPDP Reports, Team Users, and SMS Notifications.
"""

import os
import time
import json
import sqlite3
import uuid
from typing import List, Dict, Any, Optional

try:
    import pymysql
    import pymysql.cursors
    HAVE_PYMYSQL = True
except ImportError:
    HAVE_PYMYSQL = False

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "trapwire_db")

DB_ENGINE = "uninitialized"  # "mysql" | "sqlite"
_sqlite_conn = None


def get_mysql_connection():
    if not HAVE_PYMYSQL:
        return None
    try:
        # First connect without database to ensure DB exists
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=2
        )
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.select_db(MYSQL_DATABASE)
        return conn
    except Exception as e:
        # MySQL not reachable or credentials invalid
        return None


def get_sqlite_connection():
    global _sqlite_conn
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trapwire.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    global DB_ENGINE
    mysql_conn = get_mysql_connection()
    if mysql_conn:
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
                    `user_agent` TEXT,
                    `triggered_at` DOUBLE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `submitted_reports` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `incident_id` VARCHAR(32) NOT NULL,
                    `stage` VARCHAR(32) NOT NULL,
                    `filename` VARCHAR(255) NOT NULL,
                    `ack_number` VARCHAR(64) NOT NULL,
                    `ack_status` VARCHAR(32) NOT NULL,
                    `submitted_at` DOUBLE NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS `users` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `name` VARCHAR(128) NOT NULL,
                    `email` VARCHAR(128) NOT NULL UNIQUE,
                    `role` VARCHAR(64) DEFAULT 'Analyst',
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

            mysql_conn.commit()
            mysql_conn.close()
        except Exception as e:
            print(f"[DATABASE ERROR] Failed initializing MySQL tables: {e}")
    else:
        DB_ENGINE = "sqlite"
        print(f"[DATABASE] MySQL server not reachable on {MYSQL_HOST}:{MYSQL_PORT}. Falling back to persistent SQLite Engine (trapwire.db).")
        conn = get_sqlite_connection()
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
            user_agent TEXT,
            triggered_at REAL
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS submitted_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            filename TEXT NOT NULL,
            ack_number TEXT NOT NULL,
            ack_status TEXT NOT NULL,
            submitted_at REAL NOT NULL
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT DEFAULT 'Analyst',
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
        conn.commit()


# Database helper methods
def db_save_alert(alert: Dict[str, Any]):
    if DB_ENGINE == "mysql":
        conn = get_mysql_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO alerts (id, message, level, timestamp, meta_json) VALUES (%s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE message=%s, level=%s",
                    (alert["id"], alert["message"], alert["level"], alert["timestamp"], json.dumps(alert.get("meta", {})),
                     alert["message"], alert["level"])
                )
            conn.commit()
            conn.close()
            return
    conn = get_sqlite_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO alerts (id, message, level, timestamp, meta_json) VALUES (?, ?, ?, ?, ?)",
        (alert["id"], alert["message"], alert["level"], alert["timestamp"], json.dumps(alert.get("meta", {})))
    )
    conn.commit()


def db_save_sms(recipient: str, message: str, status: str = "DISPATCHED"):
    sent_at = time.time()
    if DB_ENGINE == "mysql":
        conn = get_mysql_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sms_audit (recipient, message, status, sent_at) VALUES (%s, %s, %s, %s)",
                    (recipient, message, status, sent_at)
                )
            conn.commit()
            conn.close()
            return
    conn = get_sqlite_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sms_audit (recipient, message, status, sent_at) VALUES (?, ?, ?, ?)",
        (recipient, message, status, sent_at)
    )
    conn.commit()
