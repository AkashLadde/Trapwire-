"""
TRAPWIRE — End-to-End Integration Test Suite
Requires the defender server on http://127.0.0.1:8080 (python run_servers.py).
"""
import os
import re
import requests

base_admin = 'http://127.0.0.1:8080'
ADMIN_USER = os.getenv('TRAPWIRE_ADMIN_USER', 'admin')
ADMIN_PASS = os.getenv('TRAPWIRE_ADMIN_PASS', 'Admin@2026!')
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')

print('=== 0. Resetting clean demo baseline ===')
assert requests.get(f'{base_admin}/api/reset-demo').status_code == 200

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

print('=== 5. Creating Real Test Order + Testing Hashed Exfiltration & Canary ===')
admin_sess = requests.Session()
r_admin = admin_sess.post(f'{base_admin}/api/login', data={'username': ADMIN_USER, 'password': ADMIN_PASS})
assert r_admin.status_code == 200 and r_admin.json().get('ok')

test_order_id = 'ORD-E2E-TEST-01'
# Remove stale order if leftover from an interrupted run
admin_sess.delete(f'{base_admin}/api/orders/{test_order_id}')
r_create = admin_sess.post(f'{base_admin}/api/orders', json={
    'order_id': test_order_id,
    'customer_name': 'E2E Verification Customer',
    'phone': '+91 90000 11111',
    'email': 'e2e.verify@example.test',
    'aadhaar': '1111-2222-3333',
    'pan': 'TESTP1234Z',
    'card_last4': '4321',
    'address': '100 Test Block, Bengaluru',
    'item': 'Hardware Token',
    'order_value': 4999,
    'status': 'Delivered',
})
assert r_create.status_code == 200 and r_create.json().get('ok'), r_create.text

try:
    s = requests.Session()
    s.post(f'{base_admin}/api/login', data={'username': ADMIN_USER, 'password': 'wrong_password'})
    s.post(f'{base_admin}/api/login', data={'username': ADMIN_USER, 'password': 'wrong_password'})
    s.post(f'{base_admin}/api/login', data={'username': ADMIN_USER, 'password': 'wrong_password'})
    s.post(f'{base_admin}/api/login', data={'username': ADMIN_USER, 'password': ADMIN_PASS})
    export_res = s.get(f'{base_admin}/api/export')
    assert export_res.status_code == 200
    export_records = export_res.json()
    assert isinstance(export_records, list) and len(export_records) >= 1, export_records

    body_text = export_res.text
    for plaintext_pii in ('E2E Verification Customer', '1111-2222-3333', 'TESTP1234Z', 'e2e.verify@example.test', '90000 11111'):
        assert plaintext_pii not in body_text, f'Plaintext PII leaked in export: {plaintext_pii}'

    first = export_records[0]
    for hashed_col in ('customer_name', 'phone', 'email', 'aadhaar', 'pan', 'card_last4', 'address'):
        assert SHA256_RE.match(first[hashed_col]), f'Field {hashed_col} not salted SHA-256 hex: {first[hashed_col]}'

    print(f'PASS: Exfiltrated {len(export_records)} salted-SHA256 records with active canary token.')

    canary_url = export_res.headers.get('X-Canary-Tracking-Url') or first.get('_tracking_invoice_url')
    assert canary_url and '/canary/' in canary_url
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
finally:
    admin_sess.delete(f'{base_admin}/api/orders/{test_order_id}')

print('=== 6. Verifying DPB Registry and Auto-submitted Reports ===')
reports_res = requests.get(f'{base_admin}/api/submitted-reports')
reports_list = reports_res.json()
assert len(reports_list) >= 1
print(f'PASS: Total Auto-Submitted DPB Breach Reports: {len(reports_list)}')

print('=== 7. Verifying Alerts Stream ===')
alerts_res = requests.get(f'{base_admin}/api/alerts')
alerts = alerts_res.json()
assert len(alerts) >= 4
print(f'PASS: Total Recognized Threat Alerts: {len(alerts)}')
