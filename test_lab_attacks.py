"""
TRAPWIRE Phase 2 — Real-Attack Lab Verification Suite
======================================================
Run the defender first:   python run_servers.py   (or uvicorn app.main:app --port 8080)
Then:                     python test_lab_attacks.py

Every test fires a REAL request at the lab endpoints (the same requests
curl / Burp Suite / sqlmap would send). Nothing in this suite calls
/api/attacker-session-event — all detection asserted here is SERVER-SIDE.
Verified result on the patched build: 21/21 PASS (21 Oct 2026), plus
sqlmap independently confirmed the SQLi (see PHASE2_DEMO_GUIDE.md).
"""
import requests, time, sys

B = "http://127.0.0.1:8080"
ok = fail = 0

def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print(f"PASS: {name} {extra}")
    else:
        fail += 1; print(f"FAIL: {name} {extra}")

requests.post(f"{B}/lab/reset")
time.sleep(0.3)

r = requests.get(f"{B}/lab/shop/product", params={"id": "1"})
check("T1 normal product fetch", r.status_code == 200 and "Earbuds" in r.text)

r1 = requests.get(f"{B}/lab/shop/product", params={"id": "1 AND 1=1"})
r2 = requests.get(f"{B}/lab/shop/product", params={"id": "1 AND 1=2"})
check("T2 boolean SQLi differential", len(r1.json()["results"]) == 1 and len(r2.json()["results"]) == 0)

r = requests.get(f"{B}/lab/shop/product", params={"id": "-1 UNION SELECT id, username, password, role FROM lab_users-- "})
rows = r.json()["results"]
check("T3 UNION extraction returns decoy users", len(rows) == 4 and any("DECOY-" in str(x) for x in rows), f"rows={len(rows)}")

r = requests.get(f"{B}/lab/shop/search", params={"q": "' UNION SELECT id, username, password, role FROM lab_users-- "})
check("T4 search UNION extraction", any("DECOY-" in str(x) for x in r.json()["results"]))

marker = "<script>alert('TWTEST" + str(int(time.time())) + "')</script>"
r = requests.post(f"{B}/lab/shop/review", json={"product_id": 1, "author": "tester", "comment": marker})
check("T5 stored XSS planted", r.status_code == 200 and r.json().get("ok"))

r = requests.get(f"{B}/lab/shop/product-page/1")
check("T6 stored payload present UNESCAPED in page", marker in r.text)

m2 = "<script>alert('TWREFL')</script>"
r = requests.get(f"{B}/lab/shop/search-page", params={"q": m2})
check("T7 reflected payload unescaped", m2 in r.text)

names = set()
for i in (1, 2, 3):
    rr = requests.get(f"{B}/lab/api/customers/{i}")
    if rr.status_code == 200:
        names.add(rr.json()["name"])
check("T8 IDOR returns 3 distinct decoy customers without auth", len(names) == 3, str(names))

r = requests.get(f"{B}/lab/files/download", params={"name": "readme.txt"})
check("T9a legit sandbox file", r.status_code == 200 and "decoy" in r.text.lower())
r = requests.get(f"{B}/lab/files/download", params={"name": "../secrets/.env"})
check("T9b traversal serves DECOY .env", r.status_code == 200 and "DECOY" in r.text)
r = requests.get(f"{B}/lab/files/download", params={"name": "../../../etc/passwd"})
check("T9c escape beyond sandbox blocked (403, no real passwd)", r.status_code == 403 and "root:" not in r.text)

r = requests.get(f"{B}/lab/fetch", params={"url": f"{B}/lab/internal/metadata"})
check("T10a SSRF fetched internal decoy metadata", r.status_code == 200 and "iam_credentials" in r.text)
r = requests.get(f"{B}/lab/fetch", params={"url": "http://169.254.169.254/latest/meta-data"})
check("T10b real cloud metadata blocked", r.status_code == 403)

time.sleep(0.5)
alerts = requests.get(f"{B}/api/alerts").json()
msgs = " || ".join(a["message"] for a in alerts)
lab_alerts = [a for a in alerts if a.get("meta", {}).get("source") == "trapwire-lab"]
check("T11a lab alerts generated server-side", len(lab_alerts) >= 4, f"count={len(lab_alerts)}")
check("T11b SQLi CONFIRMED alert", "SQL INJECTION CONFIRMED (server-side)" in msgs)
check("T11c XSS CONFIRMED alert", "CROSS-SITE SCRIPTING (XSS) CONFIRMED (server-side)" in msgs)
check("T11d IDOR CONFIRMED alert", "IDOR / BROKEN ACCESS CONTROL CONFIRMED (server-side)" in msgs)
check("T11e SSRF CONFIRMED alert", "SSRF CONFIRMED (server-side)" in msgs)
check("T11f LFI CONFIRMED alert", "PATH TRAVERSAL / LFI CONFIRMED (server-side)" in msgs)

st = requests.get(f"{B}/lab/detection-stats").json()["stats"]
check("T12 detection stats recorded", st.get("sql_injection", {}).get("confirmed", 0) >= 1 and st.get("xss", {}).get("confirmed", 0) >= 1, str(st))

reps = requests.get(f"{B}/api/submitted-reports").json()
check("T13 DPDP-style auto-reports filed", len(reps) >= 1, f"reports={len(reps)}")

print(f"\n==== RESULT: {ok} passed, {fail} failed ====")
sys.exit(1 if fail else 0)
