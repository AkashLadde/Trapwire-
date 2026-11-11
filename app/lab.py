"""
TRAPWIRE — Phase 2: Real-Attack Honeypot Lab (app/lab.py)
==========================================================

WHY THIS MODULE EXISTS
----------------------
In the original TRAPWIRE, SQL injection / XSS / path-traversal "attacks"
were only *announced* by the attacker console through
POST /api/attacker-session-event — the attacker told the server an attack
had happened, and the server believed it. A real attacker never does that.

This module replaces that self-report model for six attack classes with
REAL, working (but safely contained) vulnerable endpoints plus
SERVER-SIDE detection:

  1. SQL Injection      GET  /lab/shop/product?id=1
                        GET  /lab/shop/search?q=
  2. Stored XSS         POST /lab/shop/review   -> rendered raw on
                        GET  /lab/shop/product-page/{id}
  3. Reflected XSS      GET  /lab/shop/search-page?q=
  4. IDOR / BOLA        GET  /lab/api/customers/{id}   (no auth check)
  5. LFI / Traversal    GET  /lab/files/download?name=
  6. SSRF               GET  /lab/fetch?url=  (+ decoy /lab/internal/metadata)

SAFETY CONTAINMENT (read before demo)
-------------------------------------
* Every vulnerable query runs ONLY against `honeypot_lab.db`, a separate
  throwaway SQLite file whose tables contain 100% synthetic decoy data.
  The real TRAPWIRE database is never touched by lab queries.
* File traversal is clamped to the `lab_sandbox/` folder, which contains
  only decoy files (including a fake .env full of honeytokens). Escaping
  to real system files is blocked and logged.
* SSRF only ever fetches an allow-listed internal decoy endpoint on this
  same server (127.0.0.1 + /lab/internal/*). Cloud metadata IPs and any
  other target are blocked and logged. The fetch runs in a worker thread
  (asyncio.to_thread) so the server cannot deadlock against itself.
* There is deliberately NO command-execution endpoint. Real RCE does not
  belong on a student laptop; the report's future-scope Docker idea stays
  the correct answer for RCE.
* The whole lab can be switched off with TRAPWIRE_LAB_MODE=0.
  It is ON by default so the viva demo works out of the box; the defender
  server only ever binds 127.0.0.1 (see run_servers.py).

DETECTION MODEL
---------------
Two levels, both computed on the server from the REAL request — the
attacker console is not involved at all (curl / Burp / sqlmap / ZAP all
work as "attackers"):

  PROBE    — an attack signature is seen in a real request
             (warning alert, throttled per IP+type).
  CONFIRMED— the payload actually succeeded against the decoy layer
             (UNION extraction returned decoy user rows, a stored XSS
             payload was planted, ID enumeration crossed the threshold,
             a decoy secret file was served, the server fetched the
             internal decoy metadata). Critical alert + the existing
             TRAPWIRE auto-report pipeline files a DPDP-style report.

Alerts reuse the defender's own machinery: lab.configure() is called by
app/main.py with the real broadcast_alert / auto_submit_report functions,
so lab detections appear on the same SOC dashboard, trigger the same
ESP32/SMS fan-out, and produce the same acknowledgement flow.
"""

import asyncio
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from app import state

# --------------------------------------------------------------------------
# Configuration & paths
# --------------------------------------------------------------------------

LAB_ENABLED = os.getenv("TRAPWIRE_LAB_MODE", "1") != "0"

BASE_DIR = Path(__file__).resolve().parent.parent
LAB_DB_PATH = Path(os.getenv("TRAPWIRE_LAB_DB", str(BASE_DIR / "honeypot_lab.db")))
SANDBOX_ROOT = BASE_DIR / "lab_sandbox"
SANDBOX_PUBLIC = SANDBOX_ROOT / "public"
SANDBOX_SECRETS = SANDBOX_ROOT / "secrets"

# [SYNTHETIC DECOY LAB DATA] Obvious decoys. If this exact string ever shows up
# in a request, someone read the decoy .env — that is the honeytoken tripwire.
DECOY_API_KEY = "TRAPWIRE-DECOY-API-KEY-DO-NOT-USE"
DECOY_AWS_KEY = "DECOY_AWS_KEY_0000"

router = APIRouter()

# Sinks wired by app/main.py (broadcast_alert, auto_submit_report).
_ALERT_SINK = None
_REPORT_SINK = None


def configure(alert_sink=None, report_sink=None):
    """Called by app.main once its alert/report pipeline exists."""
    global _ALERT_SINK, _REPORT_SINK
    _ALERT_SINK = alert_sink
    _REPORT_SINK = report_sink


# --------------------------------------------------------------------------
# Decoy data (100% synthetic — no real person, no real credential)
# --------------------------------------------------------------------------

DECOY_PRODUCTS = [
    (1, "Wireless Earbuds Pro", 2999, "Active Noise Cancelling Bluetooth 5.3 Earbuds with 40h Battery"),
    (2, "Apex Running Shoes X1", 1999, "Lightweight breathable mesh athletic running shoes"),
    (3, "Pulse Smart Watch Fit", 4999, "1.43-inch AMOLED Display Heart Rate & SpO2 Fitness Tracker"),
    (4, "Urban Laptop Backpack", 1499, "Water-resistant 15.6-inch padded compartment commuter pack"),
    (5, "BassBoom Bluetooth Speaker", 2499, "24W Portable Stereo Sound with IPX7 Waterproofing"),
    (6, "Classic Cotton Kurta Set", 1299, "Premium pure cotton traditional formal ethnic wear"),
]

# These are the rows a successful SQLi UNION extraction will dump.
DECOY_USERS = [
    (1, "sys_admin", "DECOY-vault-root-9821a", "admin"),
    (2, "database_mgr", "DECOY-prod-db-token-551x", "manager"),
    (3, "api_service", "DECOY-service-mesh-442p", "service"),
    (4, "compliance_lead", "DECOY-dpdp-auditor-110z", "auditor"),
]

DECOY_CUSTOMERS = [
    (1, "Aarav Sharma", "aarav.sharma@trapwire.co.in", "+91 98201 54321", "XXXX-XXXX-1001"),
    (2, "Meera Iyer", "meera.iyer@trapwire.co.in", "+91 98450 67890", "XXXX-XXXX-1002"),
    (3, "Rohan Patil", "rohan.patil@trapwire.co.in", "+91 97690 12345", "XXXX-XXXX-1003"),
    (4, "Sanya Khan", "sanya.khan@trapwire.co.in", "+91 98190 23456", "XXXX-XXXX-1004"),
    (5, "Kabir Rao", "kabir.rao@trapwire.co.in", "+91 98920 34567", "XXXX-XXXX-1005"),
    (6, "Diya Nair", "diya.nair@trapwire.co.in", "+91 98330 45678", "XXXX-XXXX-1006"),
]

DECOY_ENV = f"""# TRAPWIRE SECURE CREDENTIAL VAULT (HONEYTOKEN MONITOR)
APP_ENV=production
DATABASE_URL=sqlite:///enterprise_vault.db
AWS_ACCESS_KEY_ID={DECOY_AWS_KEY}
AWS_SECRET_ACCESS_KEY=DECOY-aws-secret-vault-token
TRAPWIRE_API_KEY={DECOY_API_KEY}
ADMIN_BACKUP_KEY=DECOY-adm-master-sec
"""

DECOY_PASSWD = """# TRAPWIRE Server Authentication Shadow Map
root:x:0:0:System Administrator:/root:/bin/bash
sys_admin:x:1000:1000:System Admin:/home/sysadmin:/bin/bash
www-data:x:33:33:Web Service Worker:/var/www:/usr/sbin/nologin
"""

DECOY_README = (
    "TRAPWIRE Secure Asset Repository v2.4 (Encrypted & Monitored Access)\n"
    "Notice: All access attempts to this directory are audited under statutory compliance guidelines. "
    "All assets in this zone operate as monitored decoy storage.\n"
)


def _lab_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(LAB_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_lab_db():
    """Create (idempotently) the decoy-only lab database and sandbox files."""
    conn = _lab_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lab_products(
                id INTEGER PRIMARY KEY, name TEXT, price INTEGER, description TEXT);
            CREATE TABLE IF NOT EXISTS lab_users(
                id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT);
            CREATE TABLE IF NOT EXISTS lab_customers(
                id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT, aadhaar_masked TEXT);
            CREATE TABLE IF NOT EXISTS lab_reviews(
                id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER,
                author TEXT, comment TEXT, created_at REAL);
            """
        )
        if conn.execute("SELECT COUNT(*) AS c FROM lab_products").fetchone()["c"] == 0:
            conn.executemany("INSERT INTO lab_products VALUES (?,?,?,?)", DECOY_PRODUCTS)
        if conn.execute("SELECT COUNT(*) AS c FROM lab_users").fetchone()["c"] == 0:
            conn.executemany("INSERT INTO lab_users VALUES (?,?,?,?)", DECOY_USERS)
        if conn.execute("SELECT COUNT(*) AS c FROM lab_customers").fetchone()["c"] == 0:
            conn.executemany("INSERT INTO lab_customers VALUES (?,?,?,?,?)", DECOY_CUSTOMERS)
        if conn.execute("SELECT COUNT(*) AS c FROM lab_reviews").fetchone()["c"] == 0:
            conn.execute(
                "INSERT INTO lab_reviews(product_id, author, comment, created_at) VALUES (1, 'Kavya Sharma', 'Great sound quality and prompt shipping. Very impressed with the build.', ?)",
                (time.time(),),
            )
        conn.commit()
    finally:
        conn.close()

    SANDBOX_PUBLIC.mkdir(parents=True, exist_ok=True)
    SANDBOX_SECRETS.mkdir(parents=True, exist_ok=True)
    (SANDBOX_PUBLIC / "readme.txt").write_text(DECOY_README)
    (SANDBOX_SECRETS / ".env").write_text(DECOY_ENV)
    (SANDBOX_SECRETS / "passwd").write_text(DECOY_PASSWD)


# --------------------------------------------------------------------------
# Detection engine (server-side; no attacker cooperation needed)
# --------------------------------------------------------------------------

PATTERNS: dict[str, list[re.Pattern]] = {
    "sql_injection": [
        re.compile(r"union\s+(all\s+)?select", re.I),
        re.compile(r"'\s*or\s*'?\d+'?\s*=\s*'?\d+", re.I),
        re.compile(r'"\s*or\s*"?\d"?\s*=\s*"?\d+', re.I),
        re.compile(r"\bselect\b.+\bfrom\b.+\b(lab_users|users|information_schema)", re.I | re.S),
        re.compile(r"\b(sleep|benchmark)\s*\(", re.I),
        re.compile(r"(--|#)\s*$", re.M),
        re.compile(r";\s*(drop|delete|update|insert)\b", re.I),
        re.compile(r"\bor\s+1\s*=\s*1\b", re.I),
    ],
    "xss": [
        re.compile(r"<\s*script", re.I),
        re.compile(r"javascript\s*:", re.I),
        re.compile(r"<\s*iframe", re.I),
        re.compile(r"\bon(error|load|click|mouseover)\s*=", re.I),
        re.compile(r"<\s*(img|svg|body|details)[^>]*\bon\w+\s*=", re.I | re.S),
        re.compile(r"document\s*\.\s*cookie", re.I),
        re.compile(r"alert\s*\(", re.I),
    ],
    "path_traversal": [
        re.compile(r"\.\./|\.\.\\"),
        re.compile(r"%2e%2e", re.I),
        re.compile(r"/etc/(passwd|shadow)", re.I),
        re.compile(r"\.env\b", re.I),
    ],
    "ssrf": [
        re.compile(r"169\.254\.169\.254"),
        re.compile(r"metadata", re.I),
        re.compile(r"://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])", re.I),
    ],
}

LABELS = {
    "sql_injection": ("SQL INJECTION", "💉"),
    "xss": ("CROSS-SITE SCRIPTING (XSS)", "⚡"),
    "path_traversal": ("PATH TRAVERSAL / LFI", "📂"),
    "idor": ("IDOR / BROKEN ACCESS CONTROL", "🔓"),
    "ssrf": ("SSRF", "🛰️"),
    "honeytoken": ("HONEYTOKEN USE", "🍯"),
}

# throttle: (ip, attack_type, confirmed) -> last alert timestamp
_last_alert: dict[tuple, float] = {}
ALERT_THROTTLE_SECONDS = 2
# report filing throttle per attack type (sqlmap fires hundreds of probes)
_last_report: dict[str, float] = {}
REPORT_THROTTLE_SECONDS = 60

# counters for /lab/detection-stats and the viva ("kitne probes aaye")
STATS: dict[str, dict[str, int]] = {}
# IDOR enumeration tracking: ip -> {customer_id: first_seen_ts}
_idor_seen: dict[str, dict[int, float]] = {}

# Defender dashboard / polling / static / lab endpoints that must never be
# misclassified by the passive middleware inspector.
_SKIP_INSPECT_PREFIXES = (
    "/static",
    "/lab",
    "/ws",
    "/api/hardware",
    "/api/alerts",
    "/api/submitted-reports",
    "/api/orders",
    "/api/users",
    "/api/projects",
    "/api/report",
    "/api/reset-demo",
    "/api/logout",
    "/company",
    "/dpb",
    "/favicon.ico",
)


def reset_detection_state():
    """Clear lab in-memory counters, IDOR tracking, and throttle caches."""
    STATS.clear()
    _idor_seen.clear()
    _last_alert.clear()
    _last_report.clear()


def _bump(attack_type: str, confirmed: bool):
    s = STATS.setdefault(attack_type, {"probes": 0, "confirmed": 0})
    s["confirmed" if confirmed else "probes"] += 1


def inspect_text(text: str) -> list[str]:
    """Return attack types whose signatures appear in `text` (already decoded)."""
    if not text:
        return []
    found = []
    for attack_type, regexes in PATTERNS.items():
        if any(r.search(text) for r in regexes):
            found.append(attack_type)
    return found


async def emit(attack_type: str, ip: str, endpoint: str, payload: str = "",
               confirmed: bool = False, detail: str = ""):
    """Create + broadcast a lab detection alert; file a report when confirmed.

    Throttled so a sqlmap run (hundreds of requests) produces a readable
    alert stream instead of flooding the SOC dashboard.
    """
    _bump(attack_type, confirmed)
    now = time.time()
    key = (ip, attack_type, confirmed)
    if now - _last_alert.get(key, 0) < ALERT_THROTTLE_SECONDS:
        return None
    _last_alert[key] = now

    label, icon = LABELS.get(attack_type, (attack_type.upper(), "🛡️"))
    snippet = (payload or "")[:120]
    if confirmed:
        msg = (f"{icon} {label} CONFIRMED (server-side): payload succeeded against the "
               f"DECOY lab layer at {endpoint} from {ip}. {detail} "
               f"Payload: `{snippet}` — incident auto-reported.")
        level = "critical"
    else:
        msg = (f"{icon} {label} PROBE DETECTED (server-side): suspicious payload from "
               f"{ip} at {endpoint}: `{snippet}` — request served by decoy lab layer, "
               f"real data untouched.")
        level = "warning"

    alert = state.new_alert(msg, level=level, meta={
        "source": "trapwire-lab",
        "detection": "server-side",
        "attack_type": attack_type,
        "confirmed": confirmed,
        "ip": ip,
        "endpoint": endpoint,
        "payload": snippet,
        "timestamp": now,
        "suppress_sms": not confirmed,  # probes don't spam the admin phone
    })

    if _ALERT_SINK is not None:
        try:
            await _ALERT_SINK(alert)
        except Exception as e:
            print(f"[LAB ALERT SINK ERROR] {e}")

    if confirmed and _REPORT_SINK is not None:
        if now - _last_report.get(attack_type, 0) >= REPORT_THROTTLE_SECONDS:
            _last_report[attack_type] = now
            if not state.BREACH.get("incident_id"):
                state.BREACH.update({
                    "incident_id": "INC-" + uuid.uuid4().hex[:8].upper(),
                    "detected_at": now,
                    "attacker_ip": ip,
                })
            try:
                await _REPORT_SINK(
                    stage="preliminary",
                    reason=f"{label} confirmed against decoy lab layer at {endpoint} from {ip}",
                )
            except Exception as e:
                print(f"[LAB REPORT SINK ERROR] {e}")
    return alert


async def inspect_http_request(request: Request):
    """Middleware hook (wired in app.main): inspect attacker-facing requests
    (path + query string). Skips defender polling, static assets, and
    authenticated non-suspicious admin sessions to prevent false positives."""
    try:
        path = request.url.path
        if path == "/" or path.startswith(_SKIP_INSPECT_PREFIXES):
            return
        try:
            sess = request.session
            if sess.get("authenticated") and not sess.get("suspicious"):
                return
        except Exception:
            pass
        raw = unquote(str(request.url.query or ""))
        haystack = unquote(path) + "?" + raw
        ip = _client_ip(request)

        # Honeytoken tripwire: the planted decoy key appearing anywhere.
        auth = request.headers.get("authorization", "")
        if DECOY_API_KEY in haystack or DECOY_API_KEY in auth:
            await emit("honeytoken", ip, path, payload=DECOY_API_KEY,
                       confirmed=True,
                       detail="The planted decoy API key from the lab .env was used.")
            return

        for attack_type in inspect_text(haystack):
            await emit(attack_type, ip, path, payload=raw, confirmed=False)
    except Exception as e:
        print(f"[LAB INSPECT ERROR] {e}")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "127.0.0.1"


# --------------------------------------------------------------------------
# Lab pages & endpoints  (the deliberately-vulnerable DECOY shop)
# --------------------------------------------------------------------------

_PAGE_HEAD = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>TRAPWIRE Lab Shop (Decoy)</title></head>
<body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;">
<p style="background:#7f1d1d;padding:8px;border-radius:6px;">
⚠️ TRAPWIRE LAB — deliberately vulnerable DECOY shop. All data is synthetic.
Localhost training use only.</p>
"""


@router.get("/lab/", response_class=HTMLResponse)
@router.get("/lab", response_class=HTMLResponse)
def lab_index():
    return _PAGE_HEAD + """
<h1>TRAPWIRE Lab Shop — Attack Surface</h1>
<ul>
  <li>SQL Injection: <code>GET /lab/shop/product?id=1</code> ·
      <code>GET /lab/shop/search?q=earbuds</code></li>
  <li>Stored XSS: <code>POST /lab/shop/review</code> → open
      <code>/lab/shop/product-page/1</code></li>
  <li>Reflected XSS: <code>GET /lab/shop/search-page?q=test</code></li>
  <li>IDOR: <code>GET /lab/api/customers/1</code> (change the id!)</li>
  <li>LFI / Traversal: <code>GET /lab/files/download?name=readme.txt</code></li>
  <li>SSRF: <code>GET /lab/fetch?url=...</code></li>
  <li>Detection statistics: <code>GET /lab/detection-stats</code></li>
</ul>
<p>Every attack above is detected <b>on the server</b> and appears on the
TRAPWIRE SOC dashboard — try it with curl, Burp Suite or sqlmap,
no attacker console needed.</p>
</body></html>"""


# --------------------------------------------------------------- SQLi -----

@router.get("/lab/shop/product")
async def lab_product_by_id(request: Request, id: str = "1"):
    """DELIBERATELY VULNERABLE: `id` is concatenated straight into SQL.
    Runs ONLY against honeypot_lab.db (decoy data)."""
    ip = _client_ip(request)
    query = ("SELECT id, name, price, description FROM lab_products "
             f"WHERE id = {id}")  # <-- the vulnerability (decoy DB only)
    conn = _lab_conn()
    try:
        rows = [dict(r) for r in conn.execute(query).fetchall()]
        error = None
    except Exception as e:
        rows, error = [], str(e)
    finally:
        conn.close()
    # CONFIRMED when a UNION payload actually pulled decoy user rows out;
    # otherwise emit a single probe alert if SQLi patterns matched.
    if "union" in id.lower() and rows and any("DECOY-" in str(r) for r in rows):
        await emit("sql_injection", ip, "/lab/shop/product", payload=id,
                   confirmed=True,
                   detail="UNION extraction returned decoy lab_users rows.")
    elif "sql_injection" in inspect_text(id):
        await emit("sql_injection", ip, "/lab/shop/product", payload=id, confirmed=False)
    return JSONResponse({"executed_query": query, "results": rows, "error": error})


@router.get("/lab/shop/search")
async def lab_search(request: Request, q: str = ""):
    """DELIBERATELY VULNERABLE: `q` is concatenated into a LIKE query."""
    ip = _client_ip(request)
    query = ("SELECT id, name, price, description FROM lab_products "
             f"WHERE name LIKE '%{q}%'")  # <-- the vulnerability (decoy DB only)
    conn = _lab_conn()
    try:
        rows = [dict(r) for r in conn.execute(query).fetchall()]
        error = None
    except Exception as e:
        rows, error = [], str(e)
    finally:
        conn.close()
    if "union" in q.lower() and rows and any("DECOY-" in str(r) for r in rows):
        await emit("sql_injection", ip, "/lab/shop/search", payload=q,
                   confirmed=True,
                   detail="UNION extraction returned decoy lab_users rows.")
    elif "sql_injection" in inspect_text(q):
        await emit("sql_injection", ip, "/lab/shop/search", payload=q, confirmed=False)
    return JSONResponse({"executed_query": query, "results": rows, "error": error})


# ---------------------------------------------------------------- XSS -----

@router.post("/lab/shop/review")
async def lab_add_review(request: Request):
    """Stores a product review EXACTLY as submitted (no encoding) — the
    stored-XSS vulnerability. Reviews live only in the decoy lab DB."""
    try:
        body = await request.json()
        if not isinstance(body, dict):
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    except Exception:
        form = await request.form()
        body = dict(form)
    try:
        product_id = int(body.get("product_id", 1))
    except (TypeError, ValueError):
        return JSONResponse({"error": "product_id must be an integer"}, status_code=400)
    author = str(body.get("author", "anonymous"))
    comment = str(body.get("comment", ""))
    ip = _client_ip(request)

    conn = _lab_conn()
    try:
        conn.execute(
            "INSERT INTO lab_reviews(product_id, author, comment, created_at) VALUES (?,?,?,?)",
            (product_id, author, comment, time.time()),
        )
        conn.commit()
    finally:
        conn.close()

    planted = "xss" in inspect_text(author + " " + comment)
    if planted:
        await emit("xss", ip, "/lab/shop/review", payload=comment, confirmed=True,
                   detail="Stored-XSS payload planted in a decoy product review; "
                          "it will execute in the browser of anyone opening the product page.")
    return JSONResponse({"ok": True, "stored": True,
                         "view_at": f"/lab/shop/product-page/{product_id}"})


@router.get("/lab/shop/product-page/{product_id}", response_class=HTMLResponse)
async def lab_product_page(product_id: int):
    """Renders reviews WITHOUT output encoding — stored payloads execute
    here in the viewer's browser. That is the vulnerability being taught."""
    conn = _lab_conn()
    try:
        product = conn.execute(
            "SELECT * FROM lab_products WHERE id = ?", (product_id,)).fetchone()
        reviews = conn.execute(
            "SELECT author, comment FROM lab_reviews WHERE product_id = ? ORDER BY id",
            (product_id,)).fetchall()
    finally:
        conn.close()
    if product is None:
        return HTMLResponse(_PAGE_HEAD + "<h1>Product not found</h1></body></html>",
                            status_code=404)
    items = "".join(
        f"<li><b>{r['author']}</b>: {r['comment']}</li>" for r in reviews)  # raw on purpose
    return (_PAGE_HEAD +
            f"<h1>{product['name']} — ₹{product['price']}</h1>"
            f"<p>{product['description']}</p><h2>Reviews</h2><ul>{items}</ul>"
            "</body></html>")


@router.get("/lab/shop/search-page", response_class=HTMLResponse)
async def lab_search_page(request: Request, q: str = ""):
    """Reflects `q` into the page WITHOUT encoding — reflected XSS."""
    ip = _client_ip(request)
    if "xss" in inspect_text(q):
        await emit("xss", ip, "/lab/shop/search-page", payload=q, confirmed=False,
                   detail="Reflected-XSS payload reflected by the decoy search page.")
    conn = _lab_conn()
    try:
        rows = conn.execute(
            "SELECT name FROM lab_products WHERE name LIKE ?", (f"%{q}%",)).fetchall()
    finally:
        conn.close()
    names = "".join(f"<li>{r['name']}</li>" for r in rows)
    return (_PAGE_HEAD +
            f"<h1>Search results for: {q}</h1><ul>{names}</ul></body></html>")  # q raw on purpose


# --------------------------------------------------------------- IDOR -----

@router.get("/lab/api/customers/{customer_id}")
async def lab_customer(request: Request, customer_id: int):
    """DELIBERATELY VULNERABLE: no authentication or ownership check at all.
    Changing the id returns somebody else's (decoy) record — classic IDOR.
    Enumeration of several ids from one IP is flagged as confirmed."""
    ip = _client_ip(request)
    now = time.time()
    seen = _idor_seen.setdefault(ip, {})
    seen = {k: v for k, v in seen.items() if now - v < 60}
    seen[customer_id] = now
    _idor_seen[ip] = seen

    if len(seen) >= 3:
        await emit("idor", ip, "/lab/api/customers/{id}",
                   payload=f"ids enumerated: {sorted(seen)}", confirmed=True,
                   detail="One source enumerated multiple decoy customer records "
                          "with no authorisation check (IDOR/BOLA).")
    else:
        await emit("idor", ip, "/lab/api/customers/{id}",
                   payload=f"unauthenticated access to customer {customer_id}")

    conn = _lab_conn()
    try:
        row = conn.execute(
            "SELECT * FROM lab_customers WHERE id = ?", (customer_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return JSONResponse({"error": "customer not found"}, status_code=404)
    return JSONResponse(dict(row))


# ---------------------------------------------------------------- LFI -----

@router.get("/lab/files/download")
async def lab_download(request: Request, name: str = "readme.txt"):
    """DELIBERATELY VULNERABLE join of `name` onto the public folder, so
    ../ really traverses — but the result is CLAMPED to lab_sandbox/:
    only decoy files can ever be served; escaping the lab is blocked."""
    ip = _client_ip(request)
    decoded = unquote(name)
    target = Path(os.path.normpath(os.path.join(str(SANDBOX_PUBLIC), decoded)))
    root = SANDBOX_ROOT.resolve()
    traversal_hint = "path_traversal" in inspect_text(decoded) or ".." in decoded

    try:
        target.resolve().relative_to(root)
    except ValueError:
        await emit("path_traversal", ip, "/lab/files/download", payload=name,
                   confirmed=True,
                   detail="Traversal tried to escape the decoy lab sandbox and was blocked.")
        return JSONResponse({"error": "blocked: outside the decoy lab sandbox"},
                            status_code=403)

    if not target.is_file():
        if traversal_hint:
            await emit("path_traversal", ip, "/lab/files/download", payload=name, confirmed=False)
        return JSONResponse({"error": "file not found in decoy lab"}, status_code=404)

    content = target.read_text(errors="replace")
    if SANDBOX_SECRETS in target.resolve().parents or target.parent == SANDBOX_SECRETS.resolve():
        await emit("path_traversal", ip, "/lab/files/download", payload=name,
                   confirmed=True,
                   detail="Decoy secret file served via traversal; it contains only "
                          "planted honeytokens, which are now burned.")
    elif traversal_hint:
        await emit("path_traversal", ip, "/lab/files/download", payload=name, confirmed=False)
    return PlainTextResponse(content)


# --------------------------------------------------------------- SSRF -----

@router.get("/lab/internal/metadata")
def lab_internal_metadata():
    """Decoy 'cloud metadata' — meant to be reachable only server-side.
    Contains honeytoken credentials, nothing real."""
    return JSONResponse({
        "instance": "trapwire-decoy-instance",
        "region": "ap-south-1-decoy",
        "iam_credentials": {
            "access_key_id": DECOY_AWS_KEY,
            "secret_access_key": "DECOY-aws-secret-do-not-use-anywhere",
            "token": DECOY_API_KEY,
        },
        "note": "DECOY metadata served by the TRAPWIRE lab. No real cloud account exists.",
    })


@router.get("/lab/fetch")
async def lab_fetch(request: Request, url: str = ""):
    """DELIBERATELY VULNERABLE idea (server fetches an attacker-chosen URL)
    with a hard allow-list seat-belt: only this server's own /lab/internal/*
    endpoints on 127.0.0.1 may actually be fetched. Everything else is
    blocked and logged — including real cloud-metadata addresses."""
    ip = _client_ip(request)
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    own_port = request.url.port or 8080

    suspicious = bool(inspect_text(url)) and (
        "169.254" in url or "metadata" in url.lower()
        or host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"))

    allowed = (
        parsed.scheme == "http"
        and host in ("127.0.0.1", "localhost")
        and (parsed.port in (None, own_port))
        and parsed.path.startswith("/lab/internal/")
    )
    if not allowed:
        if suspicious:
            await emit("ssrf", ip, "/lab/fetch", payload=url, confirmed=False)
        return JSONResponse({
            "error": "blocked by lab SSRF allow-list",
            "allowed_targets": f"http://127.0.0.1:{own_port}/lab/internal/* only",
            "you_sent": url,
        }, status_code=403)

    # Fetch in a worker thread: a blocking call here would freeze the event
    # loop and the server could never answer its own internal request.
    try:
        resp = await asyncio.to_thread(requests.get, url, timeout=3)
        body = resp.json()
    except Exception as e:
        return JSONResponse({"error": f"fetch failed: {e}"}, status_code=502)

    await emit("ssrf", ip, "/lab/fetch", payload=url, confirmed=True,
               detail="Server was tricked into fetching its internal decoy "
                      "metadata endpoint; only decoy credentials were returned.")
    return JSONResponse({"fetched_url": url, "status": resp.status_code, "body": body})


# ------------------------------------------------------- stats / reset ----

@router.get("/lab/detection-stats")
def lab_stats():
    return JSONResponse({
        "lab_enabled": LAB_ENABLED,
        "detection": "server-side (works with curl / Burp / sqlmap / ZAP — no attacker console needed)",
        "stats": STATS,
        "note": "probes = signature seen in a real request; confirmed = payload actually succeeded against the decoy layer",
    })


@router.post("/lab/reset")
def lab_reset():
    """Restore the lab to a clean demo state."""
    reset_detection_state()
    if LAB_DB_PATH.exists():
        LAB_DB_PATH.unlink()
    init_lab_db()
    return JSONResponse({"ok": True, "message": "Lab decoy DB and detection stats reset."})
