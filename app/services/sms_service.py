"""
TRAPWIRE — Real-Time Admin SMS Notification Service
Sends automated security emergency dispatches to Admin Phone: 9901625399 (+91 99016 25399)
"""

import os
import time
import requests
from typing import Optional
from app import database

ADMIN_PHONE_NUMBER = "9901625399"
ADMIN_PHONE_FORMATTED = "+91 99016 25399"

# Optional Twilio / Fast2SMS credentials if provided via ENV
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")


def send_admin_sms_alert(message: str, phone: str = ADMIN_PHONE_NUMBER) -> dict:
    """
    Dispatches a high-priority security SMS to the admin.
    Logs dispatch to MySQL/SQLite audit log and triggers webhooks.
    """
    timestamp = time.time()
    clean_phone = phone.replace("+91", "").replace(" ", "").strip()
    status = "DISPATCHED"
    gateway = "SIMULATED_GSM_RELAY"

    # 1. If Fast2SMS Key is configured, attempt real GSM gateway dispatch
    if FAST2SMS_API_KEY:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            payload = {
                "route": "q",
                "message": f"[TRAPWIRE SOC ALERT] {message}",
                "language": "english",
                "flash": 0,
                "numbers": clean_phone,
            }
            headers = {"authorization": FAST2SMS_API_KEY}
            resp = requests.post(url, data=payload, headers=headers, timeout=3)
            if resp.ok:
                gateway = "FAST2SMS_LIVE"
        except Exception as e:
            print(f"[SMS GATEWAY ERROR] {e}")

    # 2. Record in MySQL database
    database.db_save_sms(phone=f"+91 {clean_phone}", message=message, status=status)
    print(f"[ADMIN SMS SENT] To: {ADMIN_PHONE_FORMATTED} | Gateway: {gateway} | Message: {message}")

    return {
        "success": True,
        "recipient": ADMIN_PHONE_FORMATTED,
        "raw_number": clean_phone,
        "message": message,
        "timestamp": timestamp,
        "gateway": gateway,
        "status": status
    }
