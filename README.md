# TRAPWIRE — Local Demo (Company + Attacker Portals)

Educational cybersecurity capstone demo. Everything runs locally — the
"attacker" side only ever talks to this same local server; nothing here
touches the real internet or any real system.

## Setup & Optional Sample Data

```bash
pip install -r requirements.txt
cp .env.example .env
```

The `orders`, `users`, and `projects` tables start clean in MySQL (or SQLite fallback).
Add records directly from the Company Admin Dashboard or load optional **clearly labelled synthetic demo rows** for testing:

```bash
python seed_sample_data.py           # seeds synthetic demo orders/users/projects
python seed_sample_data.py --clear   # clears synthetic demo data
```

## Run

```
uvicorn app.main:app --reload --port 8080
```

Open http://127.0.0.1:8080/

(Or run **both** portals at once on their own ports with `python run_servers.py`
— Company/Defender on 8080, standalone Attacker console on 9000.)

## Database (MySQL)

TRAPWIRE uses **MySQL** and auto-creates the `trapwire_db` database on first run;
if MySQL is unreachable it falls back to a local SQLite file so the demo still runs.
Make sure the `pymysql` driver is installed (it's in `requirements.txt`) and MySQL
is running, then set the connection via env vars (see `.env.example`):

```bash
export MYSQL_HOST=localhost MYSQL_USER=trapwire MYSQL_PASSWORD=strongpass MYSQL_DATABASE=trapwire_db
uvicorn app.main:app --port 8080
```

On startup the log must show `Connected to MySQL Server ...`. If it says
`Falling back to persistent SQLite Engine`, MySQL isn't reachable or the driver
isn't installed. Or bring up MySQL **and** the app together with one command:

```bash
docker compose up --build        # MySQL + app, then open http://127.0.0.1:8080/
```

## Physical alert node (red LED + buzzer + OLED)

Optional ESP32 hardware: when any attack is detected, a **red LED** flashes, a
**buzzer** sounds, and a **0.96" OLED** shows the attacker's details (type, IP,
ISP, location, incident ID, DPB ack). It hooks into the same alert pipeline as
the dashboard, so it needs no extra wiring in software. With no board attached,
the dashboard's **Hardware Nodes & IoT** tab shows a live "virtual OLED" mirror
of exactly what the hardware would display. Full build + flashing guide:
[`hardware/README.md`](hardware/README.md). Quick bench test:
`python -m app.hardware --test`.

## How to demo it

1. Open the Attacker Portal (`/attacker`) in one tab.
   - Click a VPN node (cosmetic — shows why VPN alone doesn't defeat attribution).
   - Click "Start Brute-Force Attack" — it tries the built-in wordlist against
     the real login endpoint. The real password is a few attempts in, so it
     fails a few times before succeeding (that failure count is what flags
     the session as suspicious server-side).
   - Click "Open Company Dashboard" once cracked.
2. On the dashboard (as the attacker), click "Export Customer Data".
   - The dashboard *view* shows masked data under **DPDP Act, 2023** guidelines.
     When `/api/export` is triggered by a flagged/attacker session, every
     sensitive field (`customer_name`, `phone`, `email`, `aadhaar`, `pan`,
     `card_last4`, `address`) is replaced with its **one-way salted SHA-256
     hash** before export (`app/data.py`) — never plaintext PII. If the
     `orders` table is empty, `/api/export` returns `[]` with an
     `X-Canary-Tracking-Url` header. The moment a download happens, TRAPWIRE
     captures the real connecting IP/ISP, automatically generates a PRELIMINARY
     breach report, and submits it to the built-in Data Protection Board portal
     (see below) — which issues an acknowledgement number back.
   - "Opening" the downloaded file loads a small tracking page in the
     attacker's own browser tab (the canary token). That page runs ordinary
     JavaScript — the same category as any analytics script on any normal
     website — to read screen resolution, timezone, language, and platform,
     then sends that back. No code runs outside that one tab, nothing is
     installed, nothing persists. This then triggers a FINAL/updated report
     with full attribution, also submitted and acknowledged.
3. Open the Company Portal (`/company/login`) in a separate/incognito
   session and log in normally with `admin` / `Admin@2026!` on the first try
   (no honeypot flag).
   - Go to the Security Center tab — live alerts (brute-force detected,
     honeypot served, canary triggered, device fingerprint captured) plus
     an "Auto-Submitted Reports" list, each with a download link and a
     link to its DPB acknowledgement certificate.
   - You can also click "Generate Ad-hoc Report" anytime for a manual copy.
4. Open the **Data Protection Board Portal** directly at `/dpb` — a
   separate, distinctly-styled registry showing every breach notification
   ever submitted, each with its own acknowledgement certificate page and
   downloadable PDF. (This is implemented as a separate module/router
   inside the same server rather than a second process, so there's only
   one thing to run — but it has its own storage, templates, and look.)
5. Reset state between demo runs: `GET /api/reset-demo`

## What's real vs simulated (be upfront about this in your viva)

- Real / working: brute-force detection heuristic, honeypot data
  switching, canary-token attribution with live browser-fingerprint capture
  (screen, timezone, platform — a real technique used by actual security
  teams, no malware involved), live alerting via WebSocket, automated PDF
  compliance report generation, and a working (simulated) Data Protection
  Board portal that receives, stores, and acknowledges every submission.
- Simulated for the demo: the "VPN" in the attacker console uses RFC 5737
  `TEST-NET` addresses as cosmetic labels; the DPB portal is clearly marked as
  an educational simulation and is not a real government system (no official
  emblem is used, and every page carries a visible disclaimer banner); offline
  geolocation returns an explicit `"Localhost / Offline Network"` or
  `"Unresolved External IP (Offline)"` indicator rather than fabricated ISPs;
  and only the live ESP32 node state (`app/hardware.py`) is reported on
  `/api/hardware/status`.
- Deliberately NOT included: no actual malware/virus payload, and no
  generic credential-cracking tool aimed at third-party systems — the
  brute-force here only ever targets this app's own demo login endpoint,
  and attacker-detail capture is ordinary client-side JavaScript in a
  browser tab, not code that runs on or infects the attacker's system.
  This keeps the project in "legitimate security research / defensive
  simulation" territory instead of building actual attack tooling.
