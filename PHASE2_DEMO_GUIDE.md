# TRAPWIRE Phase 2 — Real-Attack Lab: Demo Guide
### Kya badla, kaise chalaye, viva me kya bole

---

## 1. Ek line me Phase 2 kya hai

Pehle SQLi/XSS/LFI "attacks" attacker console khud server ko announce karta tha
(`POST /api/attacker-session-event`) — attacker apna attack khud batata tha.
**Phase 2 me ye model khatm hai.** Ab TRAPWIRE ke andar ek asal vulnerable
*decoy shop* hai, us par curl / Burp / sqlmap se **real attack** hota hai, aur
detection **server-side** hoti hai — attacker console ki koi zaroorat nahi.

## 2. Kya-kya add / change hua

| File | Change |
|---|---|
| `app/lab.py` | **NAYA (~690 lines).** Decoy-only lab DB (`honeypot_lab.db`) + 6 real attack surfaces + server-side detection engine (probe vs confirmed, throttled alerts, auto-report wiring) |
| `app/main.py` | Lab router mount, har request ko inspect karne wala detection middleware, lab ko asli `broadcast_alert` + `auto_submit_report` pipeline se wiring |
| `static/js/attacker_terminal.js` | `sqli`, `xss`, `traversal` commands ab **real** lab calls karte hain aur server ka asal response print karte hain; naye commands: `idor`, `ssrf`; help text updated |
| `test_lab_attacks.py` | **NAYA.** 21-check verification suite — saare real requests, koi self-report nahi |
| `lab_sandbox/` | Decoy files: `public/readme.txt`, `secrets/.env` (honeytokens), `secrets/passwd` (decoy) |
| Baaki sab | **Untouched.** Original `test_full_system.py` ab bhi pura pass hota hai (regression verified) |

### Real attack surfaces (sab decoy layer par)
| Attack | Endpoint | Asal me kya hota hai |
|---|---|---|
| SQL Injection | `GET /lab/shop/product?id=1` · `GET /lab/shop/search?q=` | Input seedha SQL query me concatenate hota hai — sirf alag decoy DB (`honeypot_lab.db`) par |
| Stored XSS | `POST /lab/shop/review` → `GET /lab/shop/product-page/1` | Review bina encoding store/render hota hai; payload viewer ke browser me execute hota hai |
| Reflected XSS | `GET /lab/shop/search-page?q=` | Query bina encoding page me reflect hoti hai |
| IDOR / BOLA | `GET /lab/api/customers/{id}` | Koi auth/ownership check hi nahi; id badlo, dusre ka (decoy) record milta hai; 3+ ids = confirmed enumeration alert |
| LFI / Traversal | `GET /lab/files/download?name=` | `../` asal me traverse karta hai — lekin `lab_sandbox/` ke bahar jaana blocked + logged; sirf decoy `.env`/`passwd` mil sakte hain |
| SSRF | `GET /lab/fetch?url=` → `GET /lab/internal/metadata` | Server URL fetch karta hai; sirf apna internal decoy metadata allow-listed hai; `169.254.169.254` jaise real metadata address blocked + logged |

### Detection ke 2 level (viva ka core)
- **PROBE** — real request me attack signature dikha → warning alert.
- **CONFIRMED** — payload decoy layer par asal me succeed hua (UNION se decoy users nikal aaye, stored payload plant hua, decoy secret serve hua, server ne internal metadata fetch kiya) → critical alert + maujooda pipeline se **auto DPDP-style report file**.
- Alerts throttled hain (per IP+type), taaki sqlmap ke saikdon requests dashboard ko flood na karein. Ginti `GET /lab/detection-stats` par milti hai.
- Honeytoken tripwire: decoy `.env` wali API key kisi bhi request me dikhi → confirmed honeytoken alert.

## 3. Chalaye kaise

```bash
pip install -r requirements.txt
python run_servers.py
# Defender + lab:  http://127.0.0.1:8000/lab/      (saari attack surfaces ki list)
# Attacker console: http://127.0.0.1:9000  (commands: sqli, xss, idor, ssrf, traversal)
# Lab band karna ho to:  TRAPWIRE_LAB_MODE=0 python run_servers.py
# Demo se pehle fresh state:  POST http://127.0.0.1:8000/lab/reset
```

## 4. Verified test results (21 Oct 2026, is build par asal run)

- **`test_lab_attacks.py` — 21/21 PASS.** Boolean SQLi differential, UNION se
  4 decoy user rows extract, stored payload page me unescaped render, reflected
  XSS, bina auth 3 alag customer records (IDOR), traversal se decoy `.env`
  serve, sandbox se bahar escape **403 blocked**, SSRF se internal decoy
  metadata fetch, real cloud-metadata **403 blocked**, aur — sabse aham —
  **10 server-side lab alerts + 5 auto-filed reports, bina
  `/api/attacker-session-event` ko ek baar bhi call kiye.**
- **sqlmap (independent proof):**
  `sqlmap -u "http://127.0.0.1:8000/lab/shop/product?id=1" --batch --dbms=sqlite --tables`
  → injection point `id` confirm (boolean-based blind + UNION query, 4 columns),
  back-end DBMS: SQLite, **5 tables enumerate** (lab_users, lab_products,
  lab_customers, lab_reviews, sqlite_sequence). Usi dauraan detection stats me
  SQLi probes badh kar 10 ho gaye — matlab sqlmap ko bhi server ne khud pakda.
- **Regression:** original `test_full_system.py` ke saare 7 sections PASS —
  purani features (brute-force, export, canary, DPB) bilkul nahi tooti.

## 5. Viva-day demo script (~6 minute)

1. `http://127.0.0.1:8000/lab/` kholo — attack surface dikhao.
2. Dusre tab me SOC dashboard (company login) kholo.
3. **Terminal/curl se** (console se nahi!): 
   `curl "http://127.0.0.1:8000/lab/shop/product?id=-1 UNION SELECT id, username, password, role FROM lab_users-- "` (URL-encode karke)
   → decoy users screen par; dashboard par **SQL INJECTION CONFIRMED** alert live.
4. sqlmap wali command chalao → tables enumerate; stats page par probe count badhta dikhao.
5. Console (port 9000) se `xss` chalao → mili hui link kholo → alert box asal me execute; dashboard par XSS CONFIRMED.
6. Console se `idor`, `ssrf`, `traversal` chalao → har ek ka asal server response + dashboard alert.
7. Security Center me auto-filed report + DPB acknowledgement dikha kar band karo.

## 6. Examiner ke mushkil sawaal — seedhe jawab

**Q: "Real attacker apna attack announce nahi karega. Bina console ke pakdoge kaise?"**
A: "Sir, Phase 2 me detection server-side hai. Har request middleware aur lab endpoints par inspect hoti hai. Abhi aap chahein to apne laptop se curl ya Burp se attack karke dekh lein — console band rakhte hain, alert phir bhi aayega. Hamne test suite me yahi verify kiya hai: 21/21 checks bina self-report endpoint ko chhuye pass hue."

**Q: "Vulnerable code jaan-boojh kar kyun likha? Ye to galat practice hai."**
A: "Sir, ye DVWA aur OWASP Juice Shop wala hi established training pattern hai — hamare college ke VAPT manual ke Experiments 04/05/09 bhi yahi karte hain. Fark ye hai ki hamara vulnerable layer sirf ek alag decoy database aur decoy sandbox par chalta hai, localhost par bind hai, aur `TRAPWIRE_LAB_MODE=0` se pura band ho sakta hai. Real data isse kabhi touch nahi hota."

**Q: "RCE kyun nahi hai?"**
A: "Sir, host par real command execution student laptop par safe nahi hai. Report ke future scope me ephemeral Docker container wala design isiliye rakha hai — RCE sirf disposable container ke andar hona chahiye."

**Q: "Detection pattern-based hai — attacker payload badal de to?"**
A: "Sir, sahi pakde — ye signature + behaviour based hai (IDOR enumeration count, SSRF allow-list violation, honeytoken use). ML anomaly detection future scope me hai. Lekin ek cheez pattern se aage ki hai: CONFIRMED alert tabhi aata hai jab payload asal me succeed ho — sirf signature dikhne par sirf probe alert aata hai."

## 7. Safety rules (kabhi todna nahi)

1. Lab sirf **127.0.0.1** par — college LAN ya internet par kabhi expose nahi.
2. Burp/ZAP/sqlmap ka target sirf apne ports (8000/3000/8080) — bahar ki koi site nahi.
3. Saara data synthetic decoy hai; decoy `.env` ki keys kahin asli jagah use nahi karni (wohi honeytoken tripwire hai).
4. Demo ke baad server band; viva se pehle `POST /lab/reset` se fresh state.

---
*Phase 2 patch — 21 Oct 2026. Files: `app/lab.py` (naya), `app/main.py` (wiring),
`static/js/attacker_terminal.js` (real commands), `test_lab_attacks.py` (naya),
`lab_sandbox/` (decoy files). Baaki original project untouched.*
