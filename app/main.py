"""
TRAPWIRE — Main Enterprise Defender Server & DPDP Compliance Engine (Server 1)
Runs on http://127.0.0.1:8080
Manages Admin SOC Dashboard, Honeypot Deception Engine, Canary Token Tracking,
DPB Statutory Compliance Reporting, Real-Time WebSocket Alerts, and MySQL Storage.
"""

import asyncio
from contextlib import asynccontextmanager
import threading
import time
import uuid
import os
import requests
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import (HTMLResponse, JSONResponse, RedirectResponse,
                                 StreamingResponse)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app import state, data, reports, dpb, database, lab, hardware

# Initialize Database (MySQL with SQLite automatic fallback)
database.init_db()
lab.init_lab_db()  # Phase 2: decoy-only honeypot lab database (honeypot_lab.db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hydrate runtime state from database and start ESP32 hardware bridge."""
    try:
        alerts = database.db_get_alerts(limit=100)
        if alerts:
            state.ALERTS.clear()
            state.ALERTS.extend(alerts)
        hits = database.db_get_canary_hits(limit=50)
        if hits:
            state.CANARY_HITS.clear()
            state.CANARY_HITS.extend(hits)
        saved_reports = database.db_get_submitted_reports(limit=50)
        if saved_reports:
            state.SUBMITTED_REPORTS.clear()
            state.SUBMITTED_REPORTS.extend(saved_reports)
        latest_inc = database.db_get_latest_incident()
        if latest_inc:
            state.BREACH.clear()
            state.BREACH.update(latest_inc)
        dpb.load_from_db()
    except Exception as e:
        print(f"[STARTUP HYDRATION WARNING] {e}")

    hardware.start(
        asyncio.get_running_loop(),
        alert_sink=broadcast_alert,
        geo_resolver=resolve_ip_geolocation,
    )
    _start_network_intel_warmup()
    yield


app = FastAPI(
    title="TRAPWIRE Defender & DPDP Compliance Engine",
    lifespan=lifespan,
)


@app.middleware("http")
async def trapwire_lab_detection_middleware(request, call_next):
    """Server-side inspection of incoming attacker-facing requests (path + query).

    Registered before SessionMiddleware and CORSMiddleware so `request.session`
    is already populated when this runs, letting authenticated admin sessions
    and dashboard polling run without false-positive alerts.
    """
    if lab.LAB_ENABLED:
        await lab.inspect_http_request(request)
    return await call_next(request)


app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("TRAPWIRE_SECRET", "trapwire-capstone-demo-secret-change-me"),
)

# Enable CORS so the independent Attacker Portal (Port 9000) can interact with API endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Canary-Tracking-Url"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.include_router(dpb.router)
if lab.LAB_ENABLED:  # Phase 2: real-attack honeypot lab (TRAPWIRE_LAB_MODE=0 disables)
    app.include_router(lab.router)


# Global cache for host machine public network intelligence
REAL_PUBLIC_IP_CACHE: Optional[str] = None
REAL_PUBLIC_GEO_CACHE: Optional[dict] = None

_SIMULATED_PREFIXES = ("192.0.2.", "198.51.100.", "203.0.113.")
_PRIVATE_PREFIXES = ("10.", "192.168.")


def _is_private_or_loopback(ip: str) -> bool:
    if ip in ("127.0.0.1", "localhost", "::1", "unknown", ""):
        return True
    if ip.startswith(_PRIVATE_PREFIXES):
        return True
    if ip.startswith("172."):
        parts = ip.split(".")
        if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return True
    return False


_OFFLINE_GEO = {
    "isp": "Localhost / Offline Network",
    "city": "Local",
    "country": "Internal",
    "region": "",
    "org": "Local Loopback",
    "as": "",
    "timezone": "UTC",
}
_GEO_CACHE: dict[str, dict] = {}
_INTEL_WARM_STARTED = False


def _warm_network_intel_worker() -> None:
    """Resolve host public IP & ISP in the background so requests never block."""
    global REAL_PUBLIC_IP_CACHE, REAL_PUBLIC_GEO_CACHE
    try:
        resp = requests.get(
            "http://ip-api.com/json/?fields=status,message,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as,query",
            timeout=1.5,
        )
        if resp.ok:
            geo_data = resp.json()
            if geo_data.get("status") == "success":
                REAL_PUBLIC_IP_CACHE = geo_data.get("query", "127.0.0.1")
                REAL_PUBLIC_GEO_CACHE = {
                    "isp": geo_data.get("isp", "Unknown ISP"),
                    "city": geo_data.get("city", "Unknown"),
                    "country": geo_data.get("country", "Unknown"),
                    "region": geo_data.get("regionName", ""),
                    "org": geo_data.get("org", geo_data.get("isp", "Unknown Org")),
                    "as": geo_data.get("as", ""),
                    "timezone": geo_data.get("timezone", "UTC"),
                }
                return
    except Exception:
        pass
    REAL_PUBLIC_IP_CACHE = REAL_PUBLIC_IP_CACHE or "127.0.0.1"
    REAL_PUBLIC_GEO_CACHE = REAL_PUBLIC_GEO_CACHE or dict(_OFFLINE_GEO)


def _start_network_intel_warmup() -> None:
    global _INTEL_WARM_STARTED
    if _INTEL_WARM_STARTED:
        return
    _INTEL_WARM_STARTED = True
    threading.Thread(target=_warm_network_intel_worker, daemon=True).start()


def get_real_network_intel() -> tuple[str, dict]:
    """Return cached public IP & ISP immediately without blocking request threads."""
    if REAL_PUBLIC_IP_CACHE and REAL_PUBLIC_GEO_CACHE:
        return REAL_PUBLIC_IP_CACHE, REAL_PUBLIC_GEO_CACHE
    _start_network_intel_warmup()
    return "127.0.0.1", dict(_OFFLINE_GEO)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    host = request.client.host if request.client else "127.0.0.1"
    if host in ("127.0.0.1", "localhost", "::1", "unknown"):
        pub_ip, _ = get_real_network_intel()
        return pub_ip
    return host


def resolve_ip_geolocation(ip: str) -> dict:
    """Real-time ISP & Geolocation intelligence lookup with caching and honest fallbacks."""
    clean = (ip or "").strip()
    if clean.startswith(_SIMULATED_PREFIXES):
        return {
            "isp": "Simulated Lab Network (RFC 5737)",
            "city": "Lab Subnet",
            "country": "Simulated",
            "org": "RFC 5737 TEST-NET",
            "region": "",
            "as": "",
        }
    pub_ip, pub_geo = get_real_network_intel()
    if clean == pub_ip and pub_ip != "127.0.0.1":
        return pub_geo
    if _is_private_or_loopback(clean):
        return {
            "isp": "Private / Local Network",
            "city": "Local",
            "country": "Internal",
            "org": "Local Network",
            "region": "",
            "as": "",
        }
    if clean in _GEO_CACHE:
        return _GEO_CACHE[clean]
    try:
        resp = requests.get(f"http://ip-api.com/json/{clean}", timeout=1.2)
        if resp.ok:
            j = resp.json()
            if j.get("status") == "success":
                result = {
                    "isp": j.get("isp", "Unknown ISP"),
                    "city": j.get("city", "Unknown"),
                    "country": j.get("country", "Unknown"),
                    "org": j.get("org", j.get("isp", "Unknown")),
                    "region": j.get("regionName", ""),
                    "as": j.get("as", ""),
                }
                _GEO_CACHE[clean] = result
                return result
    except Exception:
        pass
    fallback = {
        "isp": "Unresolved External IP (Offline)",
        "city": "Unknown",
        "country": "Unknown",
        "org": "Unresolved",
        "region": "",
        "as": "",
    }
    _GEO_CACHE[clean] = fallback
    return fallback


async def auto_submit_report(stage: str = "preliminary", reason: str = "Intrusion detected"):
    """
    Auto-generates statutory breach PDF report with full forensic metadata,
    submits it directly to the Data Protection Board (DPB) registry,
    and returns acknowledgement record to broadcast live.
    """
    if not state.BREACH.get("incident_id"):
        state.BREACH["incident_id"] = "INC-" + uuid.uuid4().hex[:8].upper()
    if not state.BREACH.get("detected_at"):
        state.BREACH["detected_at"] = time.time()
        
    pdf_bytes = reports.build_breach_report_pdf(state.BREACH, state.ALERTS, state.CANARY_HITS, stage=stage)
    filename = reports.save_submitted_report(pdf_bytes, state.BREACH["incident_id"], stage)

    ack = dpb.receive_submission(pdf_bytes, {
        "incident_id": state.BREACH["incident_id"],
        "stage": stage,
        "company_name": "TrapWire Pvt Ltd",
        "attacker_ip": state.BREACH.get("download_ip") or state.BREACH.get("attacker_ip"),
        "attacker_isp": state.BREACH.get("download_isp") or state.BREACH.get("attacker_isp"),
        "detected_at": state.BREACH.get("detected_at"),
        "reason": reason
    })

    record = {
        "incident_id": state.BREACH["incident_id"],
        "stage": stage,
        "filename": filename,
        "submitted_at": time.time(),
        "ack_number": ack["ack_number"],
        "ack_status": ack["status"],
        "download_url": f"/api/submitted-reports/{filename}",
        "dpb_url": f"/dpb/submission/{ack['ack_number']}",
        "attacker_ip": state.BREACH.get("attacker_ip"),
        "attacker_isp": state.BREACH.get("attacker_isp"),
    }
    state.SUBMITTED_REPORTS.append(record)
    database.db_save_submitted_report(record)
    database.db_save_incident(state.BREACH, stage=stage, ack_number=ack["ack_number"])
    label = "Preliminary" if stage == "preliminary" else "Final Statutory"
    
    alert = state.new_alert(
        f"📄 STATUTORY DPDP BREACH REPORT AUTO-SUBMITTED TO DATA PROTECTION BOARD ({label}). "
        f"Official Ack ID: {ack['ack_number']} — All evidence timestamped and sealed.",
        level="critical",
        meta=record,
    )
    await broadcast_alert(alert)
    return record


async def broadcast_alert(alert: dict):
    """Broadcasts alert to connected admin WebSockets and saves to database."""
    # 1. Save to Database
    try:
        database.db_save_alert(alert)
    except Exception as e:
        print(f"[DB LOG ERROR] {e}")

    # 2. Drive the physical ESP32 alert node (red LED + buzzer + OLED).
    #    Non-blocking: the alert is dropped on a queue. Safe when no board
    #    is attached (the dashboard still shows the virtual OLED mirror).
    try:
        hardware.notify(alert)
    except Exception as e:
        print(f"[HARDWARE NOTIFY ERROR] {e}")

    # 3. Push via WebSocket to active Admin consoles
    dead = []
    for ws in state.ADMIN_SOCKETS:
        try:
            await ws.send_json(alert)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in state.ADMIN_SOCKETS:
            state.ADMIN_SOCKETS.remove(ws)


# ------------------------------------------------- Phase 2: lab wiring --
# Give the lab module the REAL alert broadcast + auto-report pipeline, so a
# server-side lab detection lands on the same SOC dashboard, triggers the
# same ESP32/SMS fan-out and files the same DPDP-style report as any other
# TRAPWIRE incident — no separate plumbing, no attacker self-report needed.
lab.configure(alert_sink=broadcast_alert, report_sink=auto_submit_report)


# ---------------------------------------------------------------- landing --
@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    base = str(request.base_url).rstrip("/")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "company_url": f"{base}/company/login",
        "attacker_url": f"{base}/attacker/login"
    })


# --------------------------------------------------------------- company --
@app.get("/company/login", response_class=HTMLResponse)
def company_login_page(request: Request):
    return templates.TemplateResponse("company_login.html", {"request": request})


# -------------------------------------------------------------- attacker --
@app.get("/attacker/login", response_class=HTMLResponse)
def attacker_login_page(request: Request):
    base = str(request.base_url).rstrip("/")
    return templates.TemplateResponse("attacker_login.html", {
        "request": request,
        "target_api_base": base,
        "console_url": "/attacker/console",
        "target_username": "admin"
    })


@app.get("/attacker", response_class=HTMLResponse)
@app.get("/attacker/console", response_class=HTMLResponse)
def attacker_console_page(request: Request):
    base = str(request.base_url).rstrip("/")
    return templates.TemplateResponse("attacker_portal.html", {
        "request": request,
        "target_username": "admin",
        "wordlist": ["123456", "password", "admin123", "admin@123", "Welcome@123", "qwerty123", "Admin@2026!", "letmein123"],
        "target_api_base": base,
        "login_url": "/attacker/login",
    })


@app.post("/api/login")
async def api_login(request: Request):
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = (form.get("password") or "").strip()
    ip = client_ip(request)

    if username == state.ADMIN_USERNAME and password == state.ADMIN_PASSWORD:
        failed = state.LOGIN_ATTEMPTS.get(ip, 0)
        suspicious = failed >= 3
        request.session["authenticated"] = True
        request.session["suspicious"] = suspicious
        request.session["username"] = username
        state.LOGIN_ATTEMPTS[ip] = 0

        if suspicious:
            token = str(uuid.uuid4())
            request.session["canary_token"] = token
            incident_id = "INC-" + uuid.uuid4().hex[:8].upper()
            state.BREACH.update({
                "incident_id": incident_id,
                "detected_at": time.time(),
                "attacker_ip": ip,
            })
            database.db_save_incident(state.BREACH)
            alert = state.new_alert(
                f"🚨 INTRUSION CONFIRMED: Suspicious login succeeded after {failed} failed attempts "
                f"(Source IP: {ip}, Target: '{username}'). Deception engaged: session quarantined to honeypot decoy dataset.",
                level="critical",
                meta={"ip": ip, "incident_id": incident_id, "attempt": failed, "type": "suspicious_login"},
            )
            await broadcast_alert(alert)
        else:
            alert = state.new_alert(f"Admin '{username}' logged in normally from {ip}.", level="info", meta={"suppress_sms": True})
            await broadcast_alert(alert)

        return JSONResponse({"ok": True, "suspicious": suspicious, "incident_id": state.BREACH.get("incident_id")})

    failed = state.LOGIN_ATTEMPTS.get(ip, 0) + 1
    state.LOGIN_ATTEMPTS[ip] = failed
    level = "critical" if failed >= 3 else "warning"
    
    alert_msg = f"⚠️ INTRUSION ATTEMPT: Failed authentication #{failed} on user '{username}' from IP {ip}. Honeypot deception monitoring active."
    alert = state.new_alert(
        alert_msg,
        level=level,
        meta={"ip": ip, "target_user": username, "attempt": failed, "type": "failed_login", "timestamp": time.time()},
    )
    await broadcast_alert(alert)
    return JSONResponse({"ok": False, "attempts": failed, "suspicious": failed >= 3}, status_code=401)


def _format_order_display(r: dict) -> dict:
    """Attach masked PII display columns without mutating stored database fields."""
    rr = dict(r)
    rr["aadhaar_display"] = data.mask_aadhaar(rr.get("aadhaar", ""))
    rr["pan_display"] = data.mask_pan(rr.get("pan", ""))
    rr["card_display"] = data.mask_card(rr.get("card_last4", ""))
    rr["phone_display"] = rr.get("phone") or "—"
    rr["email_display"] = rr.get("email") or "—"
    return rr


def _safe_public_order_preview(r: dict) -> dict:
    """Return masked order summary when accessed from unauthenticated/suspicious sessions."""
    rr = _format_order_display(r)
    return {
        "order_id": rr.get("order_id", ""),
        "customer_name": rr.get("customer_name", ""),
        "item": rr.get("item", ""),
        "order_value": rr.get("order_value", 0),
        "status": rr.get("status", ""),
        "address": rr.get("address", ""),
        "aadhaar_display": rr["aadhaar_display"],
        "pan_display": rr["pan_display"],
        "card_display": rr["card_display"],
        "phone_display": rr["phone_display"],
        "email_display": rr["email_display"],
    }


@app.get("/company/dashboard", response_class=HTMLResponse)
def company_dashboard(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/company/login")

    suspicious = request.session.get("suspicious", False)
    orders = database.db_get_orders()
    records = [_format_order_display(r) for r in orders]

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "records": records,
        "suspicious": suspicious,
        "username": request.session.get("username", "admin")
    })


@app.get("/api/orders")
def api_get_orders(request: Request):
    """Retrieve live database orders (masked for unauthenticated/suspicious callers)."""
    orders = database.db_get_orders()
    if request.session.get("authenticated") and not request.session.get("suspicious"):
        formatted = [_format_order_display(r) for r in orders]
    else:
        formatted = [_safe_public_order_preview(r) for r in orders]
    return JSONResponse({"ok": True, "orders": formatted})


@app.post("/api/orders")
async def api_add_order(request: Request):
    """Admin privilege to add genuine customer orders to company dashboard."""
    if not request.session.get("authenticated"):
        return JSONResponse({"ok": False, "error": "Unauthorized: Administrator login required"}, status_code=401)

    try:
        data_body = await request.json()
    except Exception:
        form = await request.form()
        data_body = dict(form)

    customer_name = (data_body.get("customer_name") or "").strip()
    if not customer_name:
        return JSONResponse({"ok": False, "error": "Customer name is required"}, status_code=400)

    import random, string
    order_id = data_body.get("order_id") or ("ORD" + "".join(random.choices(string.digits, k=6)))
    email = (data_body.get("email") or "").strip()
    phone = (data_body.get("phone") or "").strip()
    aadhaar = (data_body.get("aadhaar") or "").strip()
    pan = (data_body.get("pan") or "").strip()
    card_last4 = (data_body.get("card_last4") or "").strip()
    address = (data_body.get("address") or "").strip()
    item = (data_body.get("item") or "General Merchandise").strip()
    try:
        order_value = float(data_body.get("order_value") or 0)
    except (ValueError, TypeError):
        order_value = 0.0
    status = (data_body.get("status") or "Processing").strip()

    record = {
        "order_id": order_id,
        "customer_name": customer_name,
        "phone": phone,
        "email": email,
        "aadhaar": aadhaar,
        "pan": pan,
        "card_last4": card_last4,
        "address": address,
        "item": item,
        "order_value": order_value,
        "status": status,
        "aadhaar_display": data.mask_aadhaar(aadhaar),
        "pan_display": data.mask_pan(pan),
        "card_display": data.mask_card(card_last4),
        "phone_display": phone or "—",
        "email_display": email or "—",
    }

    # Persist to database
    database.db_save_order(record)

    return JSONResponse({"ok": True, "record": record})


@app.delete("/api/orders/{order_id}")
async def api_delete_order(order_id: str, request: Request):
    """Admin privilege to remove an order record."""
    if not request.session.get("authenticated"):
        return JSONResponse({"ok": False, "error": "Unauthorized: Administrator login required"}, status_code=401)

    deleted = database.db_delete_order(order_id)
    if not deleted:
        return JSONResponse({"ok": False, "error": f"Order '{order_id}' not found"}, status_code=404)
    return JSONResponse({"ok": True, "order_id": order_id})


# ------------------------------------------------- Workspace Users & Projects --
@app.get("/api/users")
def api_get_users(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"ok": False, "error": "Unauthorized: Administrator login required"}, status_code=401)
    return JSONResponse({"ok": True, "users": database.db_get_users()})


@app.post("/api/users")
async def api_save_user(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"ok": False, "error": "Unauthorized: Administrator login required"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "JSON object expected"}, status_code=400)
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    if not name or not email:
        return JSONResponse({"ok": False, "error": "Name and email are required"}, status_code=400)
    saved = database.db_save_user({
        "name": name,
        "email": email,
        "role": (body.get("role") or "Member").strip(),
        "dept": (body.get("dept") or "Operations").strip(),
        "status": (body.get("status") or "Active").strip(),
    })
    return JSONResponse({"ok": True, "user": saved})


@app.delete("/api/users/{email}")
async def api_delete_user(email: str, request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"ok": False, "error": "Unauthorized: Administrator login required"}, status_code=401)
    deleted = database.db_delete_user(email)
    if not deleted:
        return JSONResponse({"ok": False, "error": "User not found"}, status_code=404)
    return JSONResponse({"ok": True, "email": email})


@app.get("/api/projects")
def api_get_projects(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"ok": False, "error": "Unauthorized: Administrator login required"}, status_code=401)
    return JSONResponse({"ok": True, "projects": database.db_get_projects()})


@app.post("/api/projects")
async def api_save_project(request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"ok": False, "error": "Unauthorized: Administrator login required"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "JSON object expected"}, status_code=400)
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"ok": False, "error": "Project name is required"}, status_code=400)
    saved = database.db_save_project({
        "name": name,
        "client": (body.get("client") or "Internal").strip(),
        "owner": (body.get("owner") or request.session.get("username", "Admin")).strip(),
        "deadline": (body.get("deadline") or "").strip(),
        "status": (body.get("status") or "Planning").strip(),
        "budget": float(body.get("budget") or 0),
        "progress": int(body.get("progress") or 0),
    })
    return JSONResponse({"ok": True, "project": saved})


@app.delete("/api/projects/{project_id}")
async def api_delete_project(project_id: int, request: Request):
    if not request.session.get("authenticated"):
        return JSONResponse({"ok": False, "error": "Unauthorized: Administrator login required"}, status_code=401)
    deleted = database.db_delete_project(project_id)
    if not deleted:
        return JSONResponse({"ok": False, "error": "Project not found"}, status_code=404)
    return JSONResponse({"ok": True, "project_id": project_id})


@app.get("/api/alerts")
@app.get("/api/alerts/recent")
def api_alerts(request: Request):
    alerts_list = list(reversed(state.ALERTS[-50:]))
    if request.url.path.endswith("/recent"):
        return JSONResponse({"alerts": alerts_list})
    return JSONResponse(alerts_list)


@app.post("/api/attacker-session-event")
async def attacker_session_event(request: Request):
    """
    Recognizes all attacker activities performed from Port 9000:
    - Attacker attempting to login
    - Attacker successfully logging in
    - Type of attack performed (Brute Force, SQL Injection, Recon, VPN Hop)
    - Data extracted by attacker (Honeypot Decoy exfiltration, Canary token hits)
    Collects real-time IP, ISP, Geo-location, logs threat intelligence,
    and automatically files statutory breach reports with the Data Protection Board.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "JSON object expected"}, status_code=400)

    event_type = body.get("event", "session_start")
    raw_ip = body.get("ip") or client_ip(request)
    # Clean simulated IP display strings if present
    clean_ip = raw_ip.split(" ")[0].strip()
    geo = resolve_ip_geolocation(clean_ip)
    
    user = body.get("user", "kali")
    tool = body.get("tool", "Kali Pentest Console")
    payload = body.get("payload", "")
    target = body.get("target", "/api/orders")
    
    # Update global breach forensic tracker with maximum attacker telemetry
    state.BREACH.update({
        "attacker_ip": clean_ip,
        "attacker_isp": geo["isp"],
        "attacker_location": f"{geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}",
        "user_agent": request.headers.get("user-agent", "Mozilla/5.0 (Kali Linux x86_64) OffSec/2026"),
        "last_activity": time.time(),
        "attack_type": event_type,
        "payload": payload,
        "target": target
    })
    
    ack_info = None

    if event_type in ("terminal_login_attempt", "login_attempt"):
        entered_pass = body.get("password_attempt", "******")
        msg = f"⚠️ ATTACKER LOGIN ATTEMPT: Operator '{user}' attempting authentication on Kali Console (Passkey: '{entered_pass}') from IP {clean_ip} [{geo['isp']}]."
        level = "warning"
        
    elif event_type in ("terminal_login_success", "terminal_login"):
        msg = f"🚨 HACKER WORKSTATION ACTIVE: Attacker '{user}' successfully logged in to OffSec Pentest Console from IP {clean_ip} [{geo['isp']}, {geo.get('city','')}] targeting TrapWire APIs."
        level = "critical"
        
    elif event_type in ("bruteforce_start", "brute_force"):
        msg = f"💥 BRUTE-FORCE INTRUSION DETECTED: Dictionary credential attack launched from {clean_ip} [{geo['isp']}] targeting Admin account."
        level = "critical"
        if not state.BREACH.get("incident_id"):
            state.BREACH["incident_id"] = "INC-" + uuid.uuid4().hex[:8].upper()
            state.BREACH["detected_at"] = time.time()
        ack_info = await auto_submit_report(stage="preliminary", reason=f"Brute-force credential attack from {clean_ip}")
        
    elif event_type in ("sqli_attack", "sql_injection"):
        payload_str = payload or "UNION SELECT username, password FROM users --"
        msg = f"💉 SQL INJECTION EXPLOIT DETECTED: Malicious payload `{payload_str}` executed against `{target}` from IP {clean_ip} [{geo['isp']}]. Deception quarantine engaged."
        level = "critical"
        if not state.BREACH.get("incident_id"):
            state.BREACH["incident_id"] = "INC-" + uuid.uuid4().hex[:8].upper()
            state.BREACH["detected_at"] = time.time()
        ack_info = await auto_submit_report(stage="preliminary", reason=f"SQL Injection payload '{payload_str}' from {clean_ip}")
        
    elif event_type in ("data_exfiltration", "export"):
        count = len(database.db_get_orders())
        default_files = f"customer_export.json ({count} hashed record{'s' if count != 1 else ''})"
        files = body.get("files") or default_files
        msg = f"🚨 DATA EXFILTRATION DETECTED: Attacker at {clean_ip} [{geo['isp']}] extracted `{files}`. Hashed honeypot export with active Canary tripwires served."
        level = "critical"
        state.BREACH.update({
            "download_ip": clean_ip,
            "download_isp": geo["isp"],
            "download_time": time.time(),
        })
        ack_info = await auto_submit_report(stage="preliminary", reason=f"Decoy customer database exfiltration by {clean_ip}")
        
    elif event_type in ("xss_attack", "xss_exploit"):
        xss_payload = payload or "<script>alert(document.cookie)</script>"
        msg = f"⚡ CROSS-SITE SCRIPTING (XSS) INTERCEPTED: Malicious payload `{xss_payload}` blocked from IP {clean_ip} [{geo['isp']}]."
        level = "warning"

    elif event_type in ("traversal_attack", "path_traversal"):
        trav_path = payload or "/etc/shadow"
        msg = f"📂 PATH TRAVERSAL PROBE: Unauthorized directory enumeration `{trav_path}` intercepted from IP {clean_ip} [{geo['isp']}]."
        level = "warning"

    elif event_type in ("vpn_hop", "vpn_switch"):
        new_node = body.get("node", "External Relay")
        msg = f"🌐 ATTACKER VPN SPOOFING: Adversary switched routing tunnel to `{new_node}` (Apparent IP: {clean_ip} [{geo['isp']}])."
        level = "warning"
        
    elif event_type in ("port_scan", "recon"):
        msg = f"🔍 PORT RECONNAISSANCE PROBE: Network port scan on ports 80/8080/443/2222 detected from IP {clean_ip} [{geo['isp']}]."
        level = "warning"
        
    elif event_type in ("malware_exec", "exploit_runner"):
        script = body.get("script", "payloads.sh")
        msg = f"🛡️ EXPLOIT EXECUTION ATTEMPT: Benign test script `{script}` neutralized by Honeypot Deception Sandbox from {clean_ip} [{geo['isp']}]."
        level = "warning"

    else:
        msg = f"🛡️ ATTACKER TELEMETRY EVENT: '{tool}' activity observed from {clean_ip} [{geo['isp']}]."
        level = "warning"
        
    alert_meta = {
        "ip": clean_ip,
        "isp": geo["isp"],
        "city": geo.get("city", ""),
        "country": geo.get("country", ""),
        "org": geo.get("org", geo["isp"]),
        "type": event_type,
        "user": user,
        "tool": tool,
        "payload": payload,
        "target": target,
        "timestamp": time.time()
    }
    if ack_info:
        alert_meta["ack_number"] = ack_info["ack_number"]
        alert_meta["download_url"] = ack_info["download_url"]
        alert_meta["dpb_url"] = ack_info["dpb_url"]

    alert = state.new_alert(msg, level=level, meta=alert_meta)
    await broadcast_alert(alert)
    return JSONResponse({
        "ok": True, 
        "alert_id": alert["id"], 
        "resolved_ip": clean_ip, 
        "resolved_isp": geo["isp"],
        "resolved_location": f"{geo.get('city', '')}, {geo.get('country', '')}",
        "dpb_ack": ack_info["ack_number"] if ack_info else None,
        "dpb_compliance": "AUTOMATED_REPORT_DISPATCHED" if ack_info else "STANDBY"
    })


@app.get("/api/export")
async def api_export(request: Request):
    orders = database.db_get_orders()
    force_attacker = (
        request.query_params.get("source") == "attacker"
        or request.headers.get("x-trapwire-console") == "attacker"
    )
    authenticated = bool(request.session.get("authenticated"))
    suspicious = True if (force_attacker or not authenticated) else bool(request.session.get("suspicious", False))
    extra_headers = {}
    if suspicious:
        token = request.session.get("canary_token") or str(uuid.uuid4())
        base = str(request.base_url).rstrip("/")
        payload = data.build_hashed_export(base, token, source_records=orders)
        extra_headers["X-Canary-Tracking-Url"] = f"{base}/canary/{token}"

        ip = client_ip(request)
        geo = resolve_ip_geolocation(ip)
        state.BREACH.update({
            "download_ip": ip,
            "download_isp": geo["isp"],
            "download_user_agent": request.headers.get("user-agent", "unknown"),
            "download_time": time.time(),
        })
        database.db_save_incident(state.BREACH)

        rec_count = len(orders)
        alert = state.new_alert(
            f"🚨 EXFILTRATION ATTEMPT DETECTED: Flagged session from IP {ip} ({geo['isp']}) downloaded customer dataset ({rec_count} record{'s' if rec_count != 1 else ''}). "
            f"All sensitive fields returned as one-way salted SHA-256 hashes with active canary tracking token.",
            level="critical",
            meta={"ip": ip, "isp": geo["isp"], "token": token, "type": "data_exfiltration", "count": rec_count}
        )
        await broadcast_alert(alert)

        # Automatically generate + submit the preliminary breach report
        await auto_submit_report(stage="preliminary")
    else:
        payload = [_safe_public_order_preview(r) for r in orders]

    filename = "customer_export.json"
    return JSONResponse(payload, headers={
        "Content-Disposition": f"attachment; filename={filename}",
        **extra_headers,
    })


@app.get("/canary/{token}")
async def canary_hit(token: str, request: Request):
    """Canary tracking link phone-home beacon."""
    ip = client_ip(request)
    geo = resolve_ip_geolocation(ip)
    hit = {
        "token": token,
        "ip": ip,
        "isp": geo["isp"],
        "city": geo["city"],
        "country": geo["country"],
        "user_agent": request.headers.get("user-agent", "unknown"),
        "timestamp": time.time(),
        "screen": None, "timezone": None, "language": None,
        "platform": None, "cores": None,
    }
    state.CANARY_HITS.append(hit)
    database.db_save_canary_hit(hit)

    alert = state.new_alert(
        f"🎯 CANARY TOKEN TRIGGERED: Attacker de-anonymized! Source IP: {ip}, ISP: {geo['isp']}, Location: {geo['city']}, {geo['country']}. Gathering forensic device telemetry...",
        level="critical",
        meta=hit,
    )
    await broadcast_alert(alert)

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Loading document…</title></head>
<body style="font-family:sans-serif;color:#94a3b8;background:#0f172a;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
<p>Preparing document preview…</p>
<script>
  const info = {{
    screen: screen.width + 'x' + screen.height,
    color_depth: screen.colorDepth,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
    platform: navigator.platform || navigator.userAgentData?.platform || 'unknown',
    cores: navigator.hardwareConcurrency || 'unknown'
  }};
  fetch("/api/canary-details/{token}", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(info)
  }});
</script>
</body></html>"""
    return HTMLResponse(content=html)


@app.post("/api/canary-details/{token}")
async def canary_details(token: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "JSON object expected"}, status_code=400)
    hit = next((h for h in reversed(state.CANARY_HITS) if h["token"] == token), None)
    if hit:
        hit.update({
            "screen": body.get("screen"),
            "color_depth": body.get("color_depth"),
            "timezone": body.get("timezone"),
            "language": body.get("language"),
            "platform": body.get("platform"),
            "cores": body.get("cores"),
        })
        database.db_update_canary_hit(hit)
        alert = state.new_alert(
            f"📱 FORENSIC ATTRIBUTION COMPLETE: Device fingerprint captured -> Screen {hit['screen']}, Timezone {hit['timezone']}, OS {hit['platform']}, CPU Cores: {hit['cores']}.",
            level="critical",
            meta=hit,
        )
        await broadcast_alert(alert)

    await auto_submit_report(stage="final")
    return JSONResponse({"ok": True})


@app.post("/api/report")
def api_report(request: Request):
    breach_snapshot = state.BREACH if state.BREACH else {
        "incident_id": "NONE (No active incident)",
        "detected_at": time.time(),
        "attacker_ip": None,
        "download_ip": None,
        "download_isp": None,
        "download_user_agent": None,
        "download_time": None,
    }
    pdf_bytes = reports.build_breach_report_pdf(breach_snapshot, state.ALERTS, state.CANARY_HITS)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=DPDP_Breach_Report.pdf"},
    )


@app.get("/api/submitted-reports")
def api_submitted_reports(request: Request):
    return JSONResponse(list(reversed(state.SUBMITTED_REPORTS)))


@app.get("/api/submitted-reports/{filename}")
def download_submitted_report(filename: str, request: Request):
    root = reports.SUBMITTED_REPORTS_DIR.resolve()
    path = (root / filename).resolve()
    if path.parent != root or not path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return StreamingResponse(
        iter([path.read_bytes()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={path.name}"},
    )


# ------------------------------------------------------------- hardware --
@app.get("/api/hardware/status")
def hardware_status():
    """Live status of the physical ESP32 alert node + the virtual OLED mirror."""
    hw = hardware.status()
    esp_connected = bool(hw.get("connected"))
    esp_fw_ok = bool(hw.get("firmware_ok"))
    if not hw.get("enabled"):
        esp_state = "DISABLED"
    elif esp_connected and esp_fw_ok:
        esp_state = "CONNECTED"
    elif esp_connected:
        esp_state = "LINK_OPEN"
    else:
        esp_state = "WAITING"
    mirror_frame = (hw.get("mirror") or {}).get("frame") or {}
    return JSONResponse({
        "status": "ONLINE",
        "hardware": hw,
        "ws_clients": len(state.ADMIN_SOCKETS),
        "nodes": [
            {
                "id": "NODE-ESP32",
                "name": "ESP32 Threat Strobe, Buzzer & OLED Controller",
                "type": "Physical LED + Buzzer + OLED Attacker Display",
                "port": (hw.get("url") or hw.get("port")
                         or f"auto-detect {('Wi-Fi' if hw.get('transport') == 'wifi' else 'USB 115200')}"),
                "transport": hw.get("transport"),
                "firmware": hw.get("firmware"),
                "frames_sent": hw.get("frames_sent"),
                "attack_count": hw.get("attack_count"),
                "alarm_active": hw.get("alarm_active"),
                "muted": hw.get("muted"),
                "status": esp_state,
                "last_error": hw.get("last_error"),
                "last_trigger": mirror_frame.get("type", "Standing by"),
            },
        ],
        "active_alarm": bool(hw.get("alarm_active")),
    })


@app.post("/api/hardware/trigger-test")
async def hardware_trigger_test():
    """Manual hardware test: fires the physical siren, buzzer, LED and OLED."""
    alert = state.new_alert(
        "⚡ HARDWARE INTEGRATION TEST: Physical ESP32 strobe, buzzer and OLED display activated & SOC alert broadcast.",
        level="warning",
        meta={"suppress_sms": True},
    )
    await broadcast_alert(alert)
    return JSONResponse({"ok": True, "message": "Hardware test triggered successfully.",
                         "hardware": hardware.status()})


@app.post("/api/hardware/silence")
async def hardware_silence():
    """Stop the buzzer + LED from the dashboard (same as the physical BOOT button)."""
    hardware.silence(by="dashboard")
    alert = state.new_alert(
        "🔕 ALARM SILENCED from SOC dashboard. Physical siren stopped; incident stays open.",
        level="info", meta={"source": "hardware", "suppress_sms": True},
    )
    await broadcast_alert(alert)
    return JSONResponse({"ok": True, "hardware": hardware.status()})


@app.post("/api/hardware/mute")
async def hardware_mute(request: Request):
    """Toggle/set buzzer mute (LED + OLED keep working)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    cur = hardware.status().get("muted", False)
    muted = bool(body.get("muted", not cur))
    hardware.set_mute(muted)
    return JSONResponse({"ok": True, "muted": muted, "hardware": hardware.status()})


@app.get("/api/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/company/login")


@app.websocket("/ws/alerts")
@app.websocket("/api/threat-stream")
@app.websocket("/ws/threat-stream")
async def ws_alerts(websocket: WebSocket):
    await websocket.accept()
    state.ADMIN_SOCKETS.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in state.ADMIN_SOCKETS:
            state.ADMIN_SOCKETS.remove(websocket)



@app.get("/api/reset-demo")
def reset_demo():
    state.reset_all()
    dpb.reset()
    hardware.reset()
    lab.reset_detection_state()
    database.db_reset_runtime_telemetry()
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    import uvicorn
    print("[COMPANY SERVER] Starting Defender Portal on http://127.0.0.1:8080 ...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=True)
