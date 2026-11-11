"""
TRAPWIRE — Audit & Cleanup Verification Suite
Tests fixes from Parts 1 & 2 against a live server on http://127.0.0.1:8080
plus targeted unit tests (MySQL DictCursor row mapping & salted SHA-256).
"""
import os
import re
import sys
from contextlib import contextmanager
import requests

from app import data, database

BASE = "http://127.0.0.1:8080"
ADMIN_USER = os.getenv("TRAPWIRE_ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("TRAPWIRE_ADMIN_PASS", "Admin@2026!")

ok = 0
fail = 0


def check(name: str, cond: bool, extra: str = ""):
    global ok, fail
    if cond:
        ok += 1
        print(f"PASS: {name}" + (f" ({extra})" if extra else ""))
    else:
        fail += 1
        print(f"FAIL: {name}" + (f" ({extra})" if extra else ""))


# ------------------------------------------------------------------
# 1. Unit tests (salted SHA-256, MySQL DictCursor row mapping)
# ------------------------------------------------------------------
print("=== 1. Unit Tests: Salted SHA-256 & MySQL DictCursor Mapping ===")
h1 = data.salted_sha256("Aarav Sharma", salt="salt-a")
h2 = data.salted_sha256("Aarav Sharma", salt="salt-b")
check("A1 salted_sha256 is 64-hex and salt-dependent", bool(re.match(r"^[0-9a-f]{64}$", h1)) and h1 != h2)
check(
    "A2 salted_sha256 empty value produces salted 64-hex digest",
    bool(re.match(r"^[0-9a-f]{64}$", data.salted_sha256("", salt="salt-a")))
    and data.salted_sha256("", salt="salt-a") != data.salted_sha256("", salt="salt-b"),
)
check("A3 build_hashed_export empty DB returns []", data.build_hashed_export(BASE, "tok", source_records=[]) == [])


class _FakeDictCursor:
    def execute(self, sql, params=()):
        self.last_sql = sql

    def fetchall(self):
        return [{
            "order_id": "ORD-MYSQL-1",
            "customer_name": "Test Customer",
            "phone": "+91 00000 00001",
            "email": "test@example.test",
            "aadhaar": "1234-5678-9012",
            "pan": "ABCDE1234F",
            "card_last4": "9999",
            "address": "Test City",
            "item": "Token",
            "order_value": 1500.0,
            "status": "Delivered",
        }]


@contextmanager
def _fake_mysql_ctx(commit=False):
    yield "mysql", _FakeDictCursor()


orig_ctx = database._db_cursor
database._db_cursor = _fake_mysql_ctx
try:
    mysql_rows = database.db_get_orders()
finally:
    database._db_cursor = orig_ctx

check(
    "A4 db_get_orders maps PyMySQL DictCursor keys cleanly",
    len(mysql_rows) == 1 and mysql_rows[0]["order_id"] == "ORD-MYSQL-1" and mysql_rows[0]["order_value"] == 1500.0,
    str(mysql_rows),
)

# ------------------------------------------------------------------
# 2. Live HTTP API Audit Checks
# ------------------------------------------------------------------
print("=== 2. Live Server Audit Checks ===")
requests.get(f"{BASE}/api/reset-demo")
requests.post(f"{BASE}/lab/reset")

admin = requests.Session()
r_login = admin.post(f"{BASE}/api/login", data={"username": ADMIN_USER, "password": ADMIN_PASS})
check("A5 admin login succeeds", r_login.status_code == 200 and r_login.json().get("ok") is True and r_login.json().get("suspicious") is False)

# Snapshot existing orders and verify polling produces 0 false positives
before_alerts = requests.get(f"{BASE}/api/alerts").json()
before_warn_crit = [a for a in before_alerts if a.get("level") in ("warning", "critical")]
for _ in range(3):
    assert admin.get(f"{BASE}/company/dashboard").status_code == 200
    assert admin.get(f"{BASE}/api/hardware/status").status_code == 200
    assert admin.get(f"{BASE}/api/alerts").status_code == 200
    assert admin.get(f"{BASE}/api/orders").status_code == 200
    assert admin.get(f"{BASE}/api/submitted-reports").status_code == 200
    assert admin.get(f"{BASE}/api/users").status_code == 200
    assert admin.get(f"{BASE}/api/projects").status_code == 200

after_alerts = requests.get(f"{BASE}/api/alerts").json()
after_warn_crit = [a for a in after_alerts if a.get("level") in ("warning", "critical")]
check(
    "A6 dashboard/polling produces ZERO false-positive warning/critical alerts",
    len(after_warn_crit) == len(before_warn_crit),
    f"before={len(before_warn_crit)}, after={len(after_warn_crit)}",
)

# Hardware status: only real ESP32 node (no fabricated NODE-01/NODE-03)
hw_status = requests.get(f"{BASE}/api/hardware/status").json()
node_ids = [n.get("id") for n in hw_status.get("nodes", [])]
check("A7 /api/hardware/status excludes fake NODE-01/NODE-03", node_ids == ["NODE-ESP32"], f"nodes={node_ids}")

# Unauthenticated /api/orders must never return plaintext aadhaar/pan/card_last4
r_pub_orders = requests.get(f"{BASE}/api/orders")
pub_text = r_pub_orders.text
check(
    "A8 unauthenticated /api/orders exposes masked displays only",
    '"aadhaar":' not in pub_text and '"pan":' not in pub_text and '"card_last4":' not in pub_text,
)

# Empty orders export check verified via TestClient against isolated empty db_get_orders
os.environ.setdefault("TRAPWIRE_HW", "off")
from starlette.testclient import TestClient
from app.main import app as _tw_app

_orig_get_orders = database.db_get_orders
database.db_get_orders = lambda: []
try:
    _tc = TestClient(_tw_app)
    r_empty_exp = _tc.get("/api/export?source=attacker")
finally:
    database.db_get_orders = _orig_get_orders

check(
    "A9 empty orders /api/export returns [] with X-Canary-Tracking-Url",
    r_empty_exp.status_code == 200 and r_empty_exp.json() == [] and bool(r_empty_exp.headers.get("X-Canary-Tracking-Url")),
    f"body={r_empty_exp.text}",
)

# Status codes & input validation
r_del_missing = admin.delete(f"{BASE}/api/orders/DOES-NOT-EXIST-999")
check("A10 DELETE nonexistent order returns 404", r_del_missing.status_code == 404, f"status={r_del_missing.status_code}")

r_bad_review = requests.post(f"{BASE}/lab/shop/review", json={"product_id": "invalid", "comment": "ok"})
check("A11 POST /lab/shop/review invalid product_id returns 400", r_bad_review.status_code == 400, f"status={r_bad_review.status_code}")

r_bad_canary = requests.post(f"{BASE}/api/canary-details/tok-test", data="not-json", headers={"Content-Type": "application/json"})
check("A12 POST /api/canary-details invalid JSON returns 400", r_bad_canary.status_code == 400, f"status={r_bad_canary.status_code}")

r_trav_rep = requests.get(f"{BASE}/api/submitted-reports/..%2Fmain.py")
check("A13 path traversal on /api/submitted-reports blocked (404)", r_trav_rep.status_code == 404, f"status={r_trav_rep.status_code}")

# Live Users & Projects CRUD
u_email = "audit.user@example.test"
r_u_add = admin.post(f"{BASE}/api/users", json={"name": "Audit Tester", "email": u_email, "role": "Analyst", "dept": "SOC"})
r_u_list = admin.get(f"{BASE}/api/users").json().get("users", [])
r_u_del = admin.delete(f"{BASE}/api/users/{u_email}")
r_u_del2 = admin.delete(f"{BASE}/api/users/{u_email}")
check(
    "A14 /api/users CRUD + 404 on missing",
    r_u_add.status_code == 200 and any(u["email"] == u_email for u in r_u_list) and r_u_del.status_code == 200 and r_u_del2.status_code == 404,
)

r_p_add = admin.post(f"{BASE}/api/projects", json={"name": "Audit Project", "owner": "Tester", "budget": 5000, "progress": 25})
pid = r_p_add.json().get("project", {}).get("id", "")
r_p_list = admin.get(f"{BASE}/api/projects").json().get("projects", [])
r_p_del = admin.delete(f"{BASE}/api/projects/{pid}")
r_p_del2 = admin.delete(f"{BASE}/api/projects/{pid}")
check(
    "A15 /api/projects CRUD + 404 on missing",
    r_p_add.status_code == 200 and bool(pid) and any(p["id"] == pid for p in r_p_list) and r_p_del.status_code == 200 and r_p_del2.status_code == 404,
)

# Clean up test alerts
requests.get(f"{BASE}/api/reset-demo")
requests.post(f"{BASE}/lab/reset")

print(f"\n==== AUDIT RESULT: {ok} passed, {fail} failed ====")
sys.exit(1 if fail else 0)
