"""
TRAPWIRE — Independent Attacker Portal Server (Server 2)
Dedicated Kali Linux Offensive Pentest Console running on Port 9000.
Targets the Company Defender Server at http://127.0.0.1:8000.
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

TARGET_COMPANY_URL = os.getenv("COMPANY_URL", "http://127.0.0.1:8080")

VPN_NODES = [
    {"label": "Netherlands - Amsterdam", "fake_ip": "185.20.209.0"},
    {"label": "Singapore", "fake_ip": "175.41.141.147"},
    {"label": "USA - New York", "fake_ip": "161.185.157.24"},
    {"label": "Germany - Frankfurt", "fake_ip": "172.104.137.31"},
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
        "target_api_base": TARGET_COMPANY_URL,
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
        "show_login": False,
        "target_api_base": TARGET_COMPANY_URL
    })


if __name__ == "__main__":
    import uvicorn
    print("[ATTACKER SERVER] Starting TRAPWIRE Pentest Console on http://127.0.0.1:9000 ...")
    uvicorn.run("app.attacker_server:app", host="127.0.0.1", port=9000, reload=True)
