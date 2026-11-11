"""
TRAPWIRE — Independent Attacker Portal Server (Server 2)
Dedicated Kali Linux Offensive Pentest Console running on Port 9000.
Targets the Company Defender Server at http://127.0.0.1:8080.
"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="TRAPWIRE Offensive Pentest Console")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and templates
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

DEFENDER_PORT = os.getenv("DEFENDER_PORT", "8080")


def _resolve_target_api_base(request: Request) -> str:
    """Resolve defender backend URL from COMPANY_URL or derive dynamically from request host."""
    explicit = os.getenv("COMPANY_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    host = (request.url.hostname or "127.0.0.1").strip()
    return f"{scheme}://{host}:{DEFENDER_PORT}"


# [SYNTHETIC LAB SIMULATOR] RFC 5737 TEST-NET addresses for simulated exit nodes
VPN_NODES = [
    {"label": "Simulated Exit — Zone A", "fake_ip": "198.51.100.10"},
    {"label": "Simulated Exit — Zone B", "fake_ip": "203.0.113.20"},
    {"label": "Simulated Exit — Zone C", "fake_ip": "192.0.2.30"},
    {"label": "Simulated Exit — Zone D", "fake_ip": "198.51.100.40"},
]

ATTACK_WORDLIST = [
    "123456",
    "password",
    "admin123",
    "admin@123",
    "Welcome@123",
    "qwerty123",
    "Admin@2026!",
    "letmein123",
]


@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
@app.get("/attacker/login", response_class=HTMLResponse)
def attacker_login_page(request: Request):
    return templates.TemplateResponse("attacker_login.html", {
        "request": request,
        "target_api_base": _resolve_target_api_base(request),
        "console_url": "/console",
        "target_username": "admin"
    })


@app.get("/console", response_class=HTMLResponse)
@app.get("/attacker", response_class=HTMLResponse)
@app.get("/attacker/console", response_class=HTMLResponse)
def attacker_console(request: Request):
    return templates.TemplateResponse("attacker_portal.html", {
        "request": request,
        "target_username": "admin",
        "wordlist": ATTACK_WORDLIST,
        "vpn_nodes": VPN_NODES,
        "target_api_base": _resolve_target_api_base(request),
        "login_url": "/login",
    })


if __name__ == "__main__":
    import uvicorn
    print("[ATTACKER SERVER] Starting TRAPWIRE Pentest Console on http://127.0.0.1:9000 ...")
    uvicorn.run("app.attacker_server:app", host="127.0.0.1", port=9000, reload=True)
