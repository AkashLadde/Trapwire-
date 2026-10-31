"""
TRAPWIRE — Alert Notification Service (Stub)
SMS alerts disabled per project configuration.
"""

def send_admin_sms_alert(message: str, phone: str = "") -> dict:
    """Stubbed alert function - SMS dispatches are deactivated."""
    return {
        "success": True,
        "message": message,
        "status": "DISABLED"
    }
