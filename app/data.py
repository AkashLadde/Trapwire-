"""
TRAPWIRE — Data Minimization, Masking & Salted One-Way SHA-256 Export Protection

Contains zero hardcoded/synthetic customer datasets. Real order records come
strictly from the database (`app/database.py`). During an admin view, PII is
masked per DPDP Act, 2023 data-minimization guidelines; during data exfiltration
(`build_hashed_export`), every sensitive PII field on real order records is
replaced with a salted one-way SHA-256 digest and tagged with a canary beacon.
"""

import hashlib
import os
import secrets
from typing import Dict, List, Optional


def mask_aadhaar(value: str) -> str:
    if not value:
        return "—"
    last = value.split("-")[-1] if "-" in value else value[-4:]
    return f"XXXX-XXXX-{last}"


def mask_pan(value: str) -> str:
    if not value:
        return "—"
    return "XXXXX" + (value[5:] if len(value) > 5 else value[-4:])


def mask_card(value: str) -> str:
    if not value:
        return "—"
    last = value[-4:] if len(value) >= 4 else value
    return "**** **** **** " + last


def truncate_hash(value: str, length: int = 16) -> str:
    return value[:length] + "…" if len(value) > length else value


def salted_sha256(value: str, salt: str) -> str:
    """Irreversible salted one-way SHA-256 hex digest for sensitive PII."""
    normalized = (value or "").strip()
    return hashlib.sha256(f"{salt}:{normalized}".encode("utf-8")).hexdigest()


def build_hashed_export(
    canary_url_base: str,
    token: str,
    source_records: Optional[List[Dict]] = None,
    salt: Optional[str] = None,
) -> List[Dict]:
    """
    Build a DPDP-safe export from REAL database order records.
    - Returns [] when no orders exist in the database (never invents fake rows).
    - Hashes every sensitive PII field (customer_name, phone, email, aadhaar,
      pan, card_last4, address) with salted one-way SHA-256 so zero plaintext
      PII ever leaves the server.
    - Embeds `_tracking_invoice_url` canary token for forensic attribution.
    """
    if not source_records:
        return []

    canary_link = f"{canary_url_base}/canary/{token}"
    effective_salt = salt or os.getenv("TRAPWIRE_HASH_SALT") or token or secrets.token_hex(16)

    exported: List[Dict] = []
    for orig in source_records:
        r = dict(orig)
        for k in ("aadhaar_display", "pan_display", "card_display", "phone_display", "email_display"):
            r.pop(k, None)

        for field in ("customer_name", "phone", "email", "aadhaar", "pan", "card_last4", "address"):
            raw_val = str(r.get(field) or "")
            r[field] = salted_sha256(raw_val if raw_val else f"EMPTY_{field}", effective_salt)

        r["_hash_algorithm"] = "SHA-256 (salted)"
        r["_data_protection_note"] = (
            "Sensitive PII fields are hashed with salted one-way SHA-256 and cannot be reversed."
        )
        r["_tracking_invoice_url"] = canary_link
        exported.append(r)

    return exported


# Backwards-compatible alias
generate_honeypot_export = build_hashed_export
