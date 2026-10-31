# TRAPWIRE — Local Demo (Company + Attacker Portals)

Educational cybersecurity capstone demo. Everything runs locally — the
"attacker" side only ever talks to this same local server; nothing here
touches the real internet or any real system.

## Setup

```
pip install -r requirements.txt
```

## Run

```
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/

## How to demo it

1. Open the Attacker Portal (`/attacker`) in one tab.
   - Click a VPN node (cosmetic — shows why VPN alone doesn't defeat attribution).
   - Click "Start Brute-Force Attack" — it tries the built-in wordlist against
     the real login endpoint. The real password is a few attempts in, so it
     fails a few times before succeeding (that failure count is what flags
     the session as suspicious server-side).
   - Click "Open Company Dashboard" once cracked.
2. On the dashboard (as the attacker), click "Export Customer Data".
   - The dashboard *view* still shows realistic-looking masked data (so the
     deception holds up while the attacker is deciding what to do). But the
     actual exported file is different: every sensitive field (Aadhaar,
     PAN, phone, email, card) is replaced with its SHA-256 hash before
     export — so even the downloaded file contains no usable personal
     data, hashed on top of already being synthetic. The moment this
     download happens, TRAPWIRE captures the real connecting IP/ISP,
     automatically generates a PRELIMINARY breach report, and submits it
     to the built-in Data Protection Board portal (see below) — which
     issues an acknowledgement number back.
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
- Simulated for the demo: the "VPN" is a cosmetic label; the DPB portal is
  clearly marked as an educational simulation and is not a real government
  system (no official emblem is used, and every page carries a visible
  disclaimer banner); the geolocation lookup falls back to a labeled
  simulated result if there's no internet access to ip-api.com; there's no
  real network packet capture (that's listed as future work in your own
  P1 slide).
- Deliberately NOT included: no actual malware/virus payload, and no
  generic credential-cracking tool aimed at third-party systems — the
  brute-force here only ever targets this app's own demo login endpoint,
  and attacker-detail capture is ordinary client-side JavaScript in a
  browser tab, not code that runs on or infects the attacker's system.
  This keeps the project in "legitimate security research / defensive
  simulation" territory instead of building actual attack tooling.

## Fix before your final submission

Your P1 slide says "DPDP Act, 2013" — the correct name is the
Digital Personal Data Protection (DPDP) Act, 2023.
