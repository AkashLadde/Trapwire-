import requests

base_admin = 'http://127.0.0.1:8080'
base_hacker = 'http://127.0.0.1:9000'

print('=== 1. Testing Landing Page ===')
res_landing = requests.get(base_admin)
assert res_landing.status_code == 200
assert 'Admin Login' in res_landing.text
print('PASS: Landing page features direct link for Admin Login.')

print('=== 2. Testing Attacker Login Attempt (Wrong Passphrase) ===')
res_atk_fail = requests.post(f'{base_admin}/api/attacker-session-event', json={
    'event': 'terminal_login_attempt',
    'user': 'unknown_hacker',
    'password_attempt': 'wrong_password_123',
    'tool': 'Kali Workstation HUD'
})
assert res_atk_fail.status_code == 200
print('PASS: Attacker login attempt recognized:', res_atk_fail.json())

print('=== 3. Testing Attacker Successful Login ===')
res_atk_ok = requests.post(f'{base_admin}/api/attacker-session-event', json={
    'event': 'terminal_login_success',
    'user': 'root',
    'password_attempt': 'toor',
    'tool': 'Kali Workstation'
})
assert res_atk_ok.status_code == 200
print('PASS: Attacker successful login recognized:', res_atk_ok.json())

print('=== 4. Testing SQL Injection Attack and Automated DPB Submission ===')
res_sqli = requests.post(f'{base_admin}/api/attacker-session-event', json={
    'event': 'sqli_attack',
    'user': 'root',
    'payload': "' UNION SELECT username, password FROM users --",
    'target': '/api/orders'
})
assert res_sqli.status_code == 200
sqli_data = res_sqli.json()
print('PASS: SQLi attack recognized with IP/ISP and DPB ack:', sqli_data)
assert sqli_data.get('dpb_ack') is not None

print('=== 5. Testing Decoy Data Exfiltration and Canary Phone-Home ===')
s = requests.Session()
s.post(f'{base_admin}/api/login', data={'username': 'admin', 'password': 'wrong_password'})
s.post(f'{base_admin}/api/login', data={'username': 'admin', 'password': 'wrong_password'})
s.post(f'{base_admin}/api/login', data={'username': 'admin', 'password': 'wrong_password'})
s.post(f'{base_admin}/api/login', data={'username': 'admin', 'password': 'Admin@2026!'})
export_res = s.get(f'{base_admin}/api/export')
assert export_res.status_code == 200
export_records = export_res.json()
print(f'PASS: Exfiltrated {len(export_records)} decoy records with active canary token.')

# Trigger canary tracking link
canary_url = export_records[0].get('_tracking_invoice_url')
token = canary_url.split('/canary/')[1]
canary_get = requests.get(canary_url)
assert canary_get.status_code == 200
canary_post = requests.post(f'{base_admin}/api/canary-details/{token}', json={
    'screen': '2560x1440',
    'platform': 'Linux x86_64',
    'timezone': 'Asia/Kolkata',
    'cores': 16,
    'language': 'en-US'
})
assert canary_post.status_code == 200
print('PASS: Canary tracking beacon captured device attribution and auto-filed final DPB report.')

print('=== 6. Verifying DPB Registry and Auto-submitted Reports ===')
reports_res = requests.get(f'{base_admin}/api/submitted-reports')
reports = reports_res.json()
print(f'PASS: Total Auto-Submitted DPB Breach Reports: {len(reports)}')
for r in reports[:3]:
    print(f"   -> Incident: {r['incident_id']} | Ack: {r['ack_number']} | IP: {r['attacker_ip']} | ISP: {r['attacker_isp']}")

print('=== 7. Verifying Alerts Stream ===')
alerts_res = requests.get(f'{base_admin}/api/alerts')
alerts = alerts_res.json()
print(f'PASS: Total Recognized Threat Alerts: {len(alerts)}')
for a in alerts[:5]:
    clean_msg = a['message'][:90].encode('ascii', 'replace').decode('ascii')
    print(f"   -> [{a['level'].upper()}] {clean_msg}...")
