"""
Generates two datasets:

1. CUSTOMERS  -> what a genuine, trusted admin sees (realistic looking
   e-commerce order data, all fields fully synthetic/random).
2. honeypot data -> what a flagged/suspicious session sees instead. It
   LOOKS identical in structure to the real data (that's the deception),
   but every record is fake and carries a hidden canary field that pings
   the server the moment it's "opened" by the attacker.

All PII values below (Aadhaar/PAN/phone/etc.) are randomly generated,
NOT real people's data.
"""
import random
import string
import uuid
import hashlib

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Kabir", "Ananya",
               "Diya", "Meera", "Priya", "Rohan", "Sanya", "Kavya",
               "Arjun", "Neha", "Rahul", "Pooja"]
LAST_NAMES = ["Sharma", "Verma", "Reddy", "Iyer", "Nair", "Gupta",
              "Khan", "Patil", "Joshi", "Mehta", "Singh", "Rao"]
CITIES = ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Pune",
          "Chennai", "Bidar", "Kolkata", "Ahmedabad", "Jaipur"]
ITEMS = ["Wireless Earbuds", "Running Shoes", "Kurta Set", "Laptop Bag",
         "Smart Watch", "Cotton Saree", "Bluetooth Speaker", "Backpack",
         "Sunglasses", "Formal Shirt"]
STATUSES = [("Delivered", 5), ("Shipped", 2), ("Processing", 2), ("Pending", 1)]


def _rand_digits(n):
    return "".join(random.choices(string.digits, k=n))


def _fake_aadhaar():
    return f"{_rand_digits(4)}-{_rand_digits(4)}-{_rand_digits(4)}"


def _fake_pan():
    letters = "".join(random.choices(string.ascii_uppercase, k=5))
    digits = _rand_digits(4)
    last = random.choice(string.ascii_uppercase)
    return f"{letters}{digits}{last}"


def _fake_phone():
    return f"+91 {random.choice(['7','8','9'])}{_rand_digits(9)}"


def _fake_email(name):
    domain = random.choice(["gmail.com", "yahoo.com", "outlook.com"])
    return f"{name.lower()}{random.randint(1,999)}@{domain}"


def _fake_card_last4():
    return _rand_digits(4)


def _fake_status():
    pool = []
    for label, weight in STATUSES:
        pool += [label] * weight
    return random.choice(pool)


def generate_customers(n=14):
    records = []
    for _ in range(n):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        records.append({
            "order_id": "ORD" + _rand_digits(6),
            "customer_name": name,
            "phone": _fake_phone(),
            "email": _fake_email(first),
            "aadhaar": _fake_aadhaar(),
            "pan": _fake_pan(),
            "address": f"{random.randint(1,999)}, MG Road, {random.choice(CITIES)}",
            "card_last4": _fake_card_last4(),
            "item": random.choice(ITEMS),
            "order_value": random.randint(299, 24999),
            "status": _fake_status(),
        })
    return records


def mask_aadhaar(value: str) -> str:
    return "XXXX-XXXX-" + value.split("-")[-1]


def mask_pan(value: str) -> str:
    return "XXXXX" + value[5:]


def mask_card(value: str) -> str:
    return "**** **** **** " + value


def truncate_hash(value: str, length: int = 16) -> str:
    """For on-screen display only -- the full hash is still what's in
    the actual exported file, this just keeps the admin table readable."""
    return value[:length] + "…" if len(value) > length else value


def _hash_field(value: str) -> str:
    """One-way SHA-256 hash, shown as a hex digest. Even if this export
    is exfiltrated, the underlying value can't be recovered from it --
    this is standard cryptographic data protection, not obfuscation."""
    return hashlib.sha256(value.encode()).hexdigest()


def generate_honeypot_view(n=14):
    """
    What a flagged/suspicious session sees ON SCREEN in the dashboard.
    Deliberately realistic-looking (same as real data, just synthetic)
    so the deception holds -- an attacker who sees obviously-fake or
    obviously-hashed data on screen would immediately recognise the
    honeypot and abandon the attempt before ever exporting anything.
    """
    return generate_customers(n)


def generate_honeypot_export(canary_url_base: str, token: str, n=14):
    """
    What actually gets served when a flagged session calls /api/export --
    i.e. the file that leaves the system. Structurally identical to the
    real dataset, but every sensitive field is replaced with its SHA-256
    hash rather than a plausible-looking fake value, and the whole export
    carries a canary tracking link. So an attacker who exports data gets:
    (a) no usable personal data at all -- it was synthetic to begin with,
        and hashed on top of that for good measure, and
    (b) a tracking token that attributes them the moment they open it.
    """
    records = generate_customers(n)
    canary_link = f"{canary_url_base}/canary/{token}"
    for r in records:
        r["order_id"] = "ORD" + "".join(random.choices(string.digits, k=6))
        r["aadhaar"] = _hash_field(r["aadhaar"])
        r["pan"] = _hash_field(r["pan"])
        r["phone"] = _hash_field(r["phone"])
        r["email"] = _hash_field(r["email"])
        r["card_last4"] = _hash_field(r["card_last4"])[:12]
        r["_data_protection_note"] = "Sensitive fields are SHA-256 hashed and cannot be reversed."
        r["_tracking_invoice_url"] = canary_link  # the "bait"
    return records
