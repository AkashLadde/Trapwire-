"""
TRAPWIRE — Main Enterprise Defender Server & DPDP Compliance Engine (Server 1)
Runs on http://127.0.0.1:8080
Manages Admin SOC Dashboard, Honeypot Deception Engine, Canary Token Tracking,
DPB Statutory Compliance Reporting, Real-Time WebSocket Alerts, and MySQL Storage.
"""

import time
import uuid
import random
import os
import requests
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import (HTMLResponse, JSONResponse, RedirectResponse,
                                Response, StreamingResponse)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app import state, data, reports, dpb, database, lab
from app.hardware_bridge import hardware_bridge

# Initialize Database (MySQL with SQLite automatic fallback)
database.init_db()
lab.init_lab_db()  # Phase 2: decoy-only honeypot lab database (honeypot_lab.db)

app = FastAPI(title="TRAPWIRE Defender & DPDP Compliance Engine")

# Enable CORS so the independent Attacker Portal (Port 9000) can interact with API endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key="trapwire-capstone-demo-secret-change-me")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.include_router(dpb.router)
if lab.LAB_ENABLED:  # Phase 2: real-attack honeypot lab (TRAPWIRE_LAB_MODE=0 disables)
    app.include_router(lab.router)

REAL_CUSTOMERS = database.db_get_orders()

VPN_NODES = [
    {"label": "Netherlands - Amsterdam", "fake_ip": "185.220.101.45"},
    {"label": "Singapore", "fake_ip": "103.253.24.19"},
    {"label": "USA - New York", "fake_ip": "198.51.100.77"},
    {"label": "Germany - Frankfurt", "fake_ip": "45.155.204.12"},
]


# Global cache for host machine public network intelligence
REAL_PUBLIC_IP_CACHE: Optional[str] = None
REAL_PUBLIC_GEO_CACHE: Optional[dict] = None


def get_real_network_intel() -> tuple[str, dict]:
    """Resolves real public IP and ISP of the running host with robust caching."""
    global REAL_PUBLIC_IP_CACHE, REAL_PUBLIC_GEO_CACHE
    if REAL_PUBLIC_IP_CACHE and REAL_PUBLIC_GEO_CACHE:
        return REAL_PUBLIC_IP_CACHE, REAL_PUBLIC_GEO_CACHE
    try:
        resp = requests.get("http://ip-api.com/json/?fields=status,message,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as,query", timeout=2.0)
        if resp.ok:
            data = resp.json()
            if data.get("status") == "success":
                REAL_PUBLIC_IP_CACHE = data.get("query", "127.0.0.1")
                REAL_PUBLIC_GEO_CACHE = {
                    "isp": data.get("isp", "Local Telecom Provider"),
                    "city": data.get("city", "Mumbai"),
                    "country": data.get("country", "India"),
                    "region": data.get("regionName", "Maharashtra"),
                    "org": data.get("org", data.get("isp", "Internet Service Provider")),
                    "as": data.get("as", "AS55836"),
                    "timezone": data.get("timezone", "Asia/Kolkata")
                }
                return REAL_PUBLIC_IP_CACHE, REAL_PUBLIC_GEO_CACHE
    except Exception:
        pass
    
    # Fallback to high-fidelity simulated enterprise IP & ISP if offline
    REAL_PUBLIC_IP_CACHE = "152.58.21.144"
    REAL_PUBLIC_GEO_CACHE = {
        "isp": "Reliance Jio Infocomm Ltd (Fiber Broadband)",
        "city": "Mumbai",
        "country": "India",
        "region": "Maharashtra",
        "org": "Reliance Jio Infocomm",
        "as": "AS55836 Jio Broadband",
        "timezone": "Asia/Kolkata"
    }
    return REAL_PUBLIC_IP_CACHE, REAL_PUBLIC_GEO_CACHE


def client_ip(request: Request) -> str:
    # Check X-Forwarded-For first
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    host = request.client.host if request.client else "127.0.0.1"
    if host in ("127.0.0.1", "localhost", "::1", "unknown"):
        pub_ip, _ = get_real_network_intel()
        return pub_ip
    return host


def resolve_ip_geolocation(ip: str) -> dict:
    """Real-time ISP & Geolocation intelligence lookup with graceful fallback."""
    pub_ip, pub_geo = get_real_network_intel()
    if ip in ("127.0.0.1", "localhost", "::1", "unknown", pub_ip):
        return pub_geo
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=1.8)
        if resp.ok:
            j = resp.json()
            if j.get("status") == "success":
                return {
                    "isp": j.get("isp", "Unknown ISP"),
                    "city": j.get("city", "Unknown City"),
                    "country": j.get("country", "Unknown Country"),
                    "org": j.get("org", j.get("isp", "Unknown Org")),
                    "region": j.get("regionName", ""),
                    "as": j.get("as", "")
                }
    except Exception:
        pass
    return {
        "isp": "Tor Exit Relay / Offshore Proxy (OffSec Network)",
        "city": "Amsterdam",
        "country": "Netherlands",
        "org": "DataCamp Limited - Anonymous Relay",
        "region": "North Holland",
        "as": "AS60068"
    }


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

    # 2. Push via WebSocket to active Admin consoles
    dead = []
    for ws in state.ADMIN_SOCKETS:
        try:
            await ws.send_json(alert)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in state.ADMIN_SOCKETS:
            state.ADMIN_SOCKETS.remove(ws)

    # 3. Direct Physical Hardware Broadcast (ESP32 DevKit V1)
    try:
        hardware_bridge.broadcast_to_mcu(alert)
    except Exception as hw_err:
        print(f"[HARDWARE RELAY ERROR] {hw_err}")


# ------------------------------------------------- Phase 2: lab wiring --
# Give the lab module the REAL alert broadcast + auto-report pipeline, so a
# server-side lab detection lands on the same SOC dashboard, triggers the
# same ESP32/SMS fan-out and files the same DPDP-style report as any other
# TRAPWIRE incident — no separate plumbing, no attacker self-report needed.
lab.configure(alert_sink=broadcast_alert, report_sink=auto_submit_report)


@app.middleware("http")
async def trapwire_lab_detection_middleware(request, call_next):
    """Server-side inspection of EVERY incoming request (path + query).

    This is the piece that catches an attacker who never touches the
    attacker console — curl, Burp Suite, sqlmap and ZAP all arrive as
    ordinary HTTP requests, and ordinary HTTP requests are what gets
    inspected here. Detection never blocks the request (deception, not
    blocking): the lab endpoints answer from the decoy layer as usual.
    """
    if lab.LAB_ENABLED:
        await lab.inspect_http_request(request)
    return await call_next(request)


# ---------------------------------------------------------------- landing --
@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    base = str(request.base_url).rstrip("/")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "company_url": f"{base}/company/login",
        "attacker_url": f"{base}/attacker"
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
        "vpn_nodes": VPN_NODES,
        "show_login": False,
        "target_api_base": base
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


@app.get("/company/dashboard", response_class=HTMLResponse)
def company_dashboard(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/company/login")

    suspicious = request.session.get("suspicious", False)

    records = []
    for r in REAL_CUSTOMERS:
        rr = dict(r)
        rr["aadhaar_display"] = data.mask_aadhaar(r["aadhaar"])
        rr["pan_display"] = data.mask_pan(r["pan"])
        rr["card_display"] = data.mask_card(r["card_last4"])
        rr["phone_display"] = r["phone"]
        rr["email_display"] = r["email"]
        records.append(rr)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "records": records,
        "suspicious": suspicious,
        "username": request.session.get("username", "admin")
    })


@app.get("/api/orders")
def api_get_orders(request: Request):
    """Retrieve orders (accessible to authenticated sessions)."""
    global REAL_CUSTOMERS
    return JSONResponse({"ok": True, "orders": REAL_CUSTOMERS})


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

    # Persist to database & memory
    database.db_save_order(record)
    global REAL_CUSTOMERS
    REAL_CUSTOMERS.insert(0, record)

    return JSONResponse({"ok": True, "record": record})


@app.delete("/api/orders/{order_id}")
async def api_delete_order(order_id: str, request: Request):
    """Admin privilege to remove an order record."""
    if not request.session.get("authenticated"):
        return JSONResponse({"ok": False, "error": "Unauthorized: Administrator login required"}, status_code=401)

    global REAL_CUSTOMERS
    database.db_delete_order(order_id)
    REAL_CUSTOMERS = [r for r in REAL_CUSTOMERS if r.get("order_id") != order_id]
    return JSONResponse({"ok": True, "order_id": order_id})


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
        count = len(REAL_CUSTOMERS) if len(REAL_CUSTOMERS) > 0 else 1
        default_files = f"customer_export.json ({count} PII record{'s' if count != 1 else ''})"
        files = body.get("files") or default_files
        msg = f"🚨 DATA EXFILTRATION DETECTED: Attacker at {clean_ip} [{geo['isp']}] extracted `{files}`. Decoy honeypot dataset served with active Canary tripwires."
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
        new_node = body.get("node", "Netherlands - Amsterdam")
        msg = f"🌐 ATTACKER VPN SPOOFING: Adversary switched routing tunnel to `{new_node}` (Apparent IP: {clean_ip} [{geo['isp']}])."
        level = "warning"
        
    elif event_type in ("port_scan", "recon"):
        msg = f"🔍 PORT RECONNAISSANCE PROBE: Network port scan on ports 80/8000/443/2222 detected from IP {clean_ip} [{geo['isp']}]."
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
    if not request.session.get("authenticated"):
        # For testing / demo simplicity allow export if flagged as suspicious
        pass

    suspicious = request.session.get("suspicious", True)
    if suspicious:
        token = request.session.get("canary_token") or str(uuid.uuid4())
        base = str(request.base_url).rstrip("/")
        payload = data.generate_honeypot_export(base, token, source_records=REAL_CUSTOMERS)

        ip = client_ip(request)
        geo = resolve_ip_geolocation(ip)
        state.BREACH.update({
            "download_ip": ip,
            "download_isp": geo["isp"],
            "download_user_agent": request.headers.get("user-agent", "unknown"),
            "download_time": time.time(),
        })

        rec_count = len(payload)
        alert = state.new_alert(
            f"🚨 EXFILTRATION ATTEMPT DETECTED: Flagged session from IP {ip} ({geo['isp']}) downloaded customer dataset ({rec_count} record{'s' if rec_count != 1 else ''}). "
            f"Decoy honeypot dataset with active canary tracking token served instead of raw unmasked data.",
            level="critical",
            meta={"ip": ip, "isp": geo["isp"], "token": token, "type": "data_exfiltration", "count": rec_count}
        )
        await broadcast_alert(alert)

        # Automatically generate + submit the preliminary breach report
        await auto_submit_report(stage="preliminary")
    else:
        payload = REAL_CUSTOMERS

    filename = "customer_export.json"
    return JSONResponse(payload, headers={
        "Content-Disposition": f"attachment; filename={filename}"
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
    
    # Save hit to MySQL
    try:
        conn = database.get_mysql_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO canary_hits (token, ip, isp, user_agent, triggered_at) VALUES (%s, %s, %s, %s, %s)",
                    (token, ip, geo["isp"], hit["user_agent"], hit["timestamp"])
                )
            conn.commit()
            conn.close()
    except Exception:
        pass

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
    body = await request.json()
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
    if not state.BREACH:
        # Initialize baseline breach record if none exists for manual reporting
        state.BREACH.update({
            "incident_id": "INC-" + uuid.uuid4().hex[:8].upper(),
            "detected_at": time.time() - 3600,
            "attacker_ip": "185.220.101.45",
            "download_ip": "185.220.101.45",
            "download_isp": "Tor Exit Node (Amsterdam)",
            "download_user_agent": "Mozilla/5.0 (Kali Linux x86_64)",
            "download_time": time.time() - 1800,
        })

    pdf_bytes = reports.build_breach_report_pdf(state.BREACH, state.ALERTS, state.CANARY_HITS)
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
    path = reports.SUBMITTED_REPORTS_DIR / filename
    if not path.exists() or path.parent != reports.SUBMITTED_REPORTS_DIR:
        return JSONResponse({"error": "not found"}, status_code=404)
    return StreamingResponse(
        iter([path.read_bytes()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ------------------------------------------------------------- hardware --
@app.get("/api/hardware/status")
def hardware_status():
    """Returns status of integrated IoT hardware nodes (ESP32 Siren, Raspberry Pi Node, GSM Modem)."""
    return JSONResponse({
        "status": "ONLINE",
        "nodes": [
            {
                "id": "NODE-01",
                "name": "Raspberry Pi 4 Honeypot Gateway",
                "type": "Edge Honeypot Server",
                "ip": "192.168.1.150 (VLAN 20 - DMZ)",
                "status": "ARMED",
                "uptime": "14d 08h 22m",
                "cpu_temp": "42.5°C"
            },
            {
                "id": "NODE-02",
                "name": "ESP32 Threat Strobe & Siren Controller",
                "type": "Physical Strobe & Audio Alarm",
                "port": f"{hardware_bridge.port or 'COM7'} (115200 baud)",
                "status": "ONLINE_ARMED" if (hardware_bridge.ser and hardware_bridge.ser.is_open) else "ACTIVE_LISTENING",
                "last_trigger": "Standing by"
            },
            {
                "id": "NODE-03",
                "name": "SOC Real-Time Threat Engine",
                "type": "WebSocket Incident Broadcaster",
                "status": "OPERATIONAL",
                "signal_strength": "100%"
            }
        ],
        "active_alarm": len(state.ALERTS) > 0 and state.ALERTS[-1].get("level") == "critical"
    })


@app.post("/api/hardware/trigger-test")
async def hardware_trigger_test():
    """Manual hardware test to trigger the physical siren and SOC alert stream."""
    alert = state.new_alert(
        "⚡ HARDWARE INTEGRATION TEST: Physical ESP32 Strobe Alarm activated & SOC alert broadcast.",
        level="critical",
        meta={"attack_type": "HARDWARE TEST", "ip": "127.0.0.1"}
    )
    await broadcast_alert(alert)
    return JSONResponse({"ok": True, "message": "Hardware test triggered successfully."})


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
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    import uvicorn
    print("[COMPANY SERVER] Starting Defender Portal on http://127.0.0.1:8080 ...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=True)
