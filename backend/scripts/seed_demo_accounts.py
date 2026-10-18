"""FairCart AI — Demonstration Accounts & Synthetic Order Seeding Script (Milestone 6B)

Provisions exactly five demonstration personas with cryptographically random high-entropy passwords,
stores Argon2id hashes in SQLite, and seeds ~3 itemized, synthetic past orders per account.
Saves local credentials exclusively to the gitignored `.local/demo-credentials.local.md`.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import secrets
import string
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from argon2 import PasswordHasher
from backend.app.db.database import get_connection, init_db
from backend.app.db.repository import CatalogRepository

DEMO_PERSONAS = [
    {
        "id": "usr_demo_gamer",
        "username": "demo_gamer",
        "display_name": "Alex Mercer (Gamer)",
        "persona_description": "Competitive gamer and esports enthusiast seeking ultra-low latency peripherals, high-refresh display connectivity, and ergonomic mechanical gear.",
        "password_prefix": "Gamer",
        "orders": [
            {
                "id": "ord_gamer_001",
                "days_ago": 18,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-023", "quantity": 1, "discount_pct": 0.10},  # RGB Gaming Mouse ($70.00 -> $63.00)
                    {"product_id": "item-004", "quantity": 1, "discount_pct": 0.10},  # Desk Mat XL ($30.00 -> $27.00)
                    {"product_id": "item-032", "quantity": 1, "discount_pct": 0.00},  # Mouse Bungee ($28.00 -> $28.00)
                ],
            },
            {
                "id": "ord_gamer_002",
                "days_ago": 9,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-001", "quantity": 1, "discount_pct": 0.00},  # Mechanical Keyboard ($80.00 -> $80.00)
                    {"product_id": "item-006", "quantity": 1, "discount_pct": 0.15},  # Coiled Cable ($28.00 -> $23.80)
                    {"product_id": "item-025", "quantity": 1, "discount_pct": 0.15},  # Switch Pack ($32.00 -> $27.20)
                ],
            },
            {
                "id": "ord_gamer_003",
                "days_ago": 2,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-030", "quantity": 2, "discount_pct": 0.00},  # HDMI 2.1 Cable ($20.00 * 2 = $40.00)
                    {"product_id": "item-010", "quantity": 1, "discount_pct": 0.10},  # ANC Headphones ($140.00 -> $126.00)
                ],
            },
        ],
    },
    {
        "id": "usr_demo_student",
        "username": "demo_student",
        "display_name": "Maya Lin (Student)",
        "persona_description": "University student optimizing a compact study nook for long research sessions, eye comfort, and focus.",
        "password_prefix": "Student",
        "orders": [
            {
                "id": "ord_student_001",
                "days_ago": 21,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-001", "quantity": 1, "discount_pct": 0.00},  # Mechanical Keyboard ($80.00 -> $80.00)
                    {"product_id": "item-007", "quantity": 1, "discount_pct": 0.10},  # ScreenBar Light ($75.00 -> $67.50)
                    {"product_id": "item-022", "quantity": 1, "discount_pct": 0.10},  # Focus Tea ($16.00 -> $14.40)
                ],
            },
            {
                "id": "ord_student_002",
                "days_ago": 11,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-016", "quantity": 1, "discount_pct": 0.10},  # Laptop Stand ($42.00 -> $37.80)
                    {"product_id": "item-015", "quantity": 1, "discount_pct": 0.00},  # 100W USB-C Cable ($16.00 -> $16.00)
                    {"product_id": "item-031", "quantity": 2, "discount_pct": 0.00},  # Dark Chocolate Fuel ($14.00 * 2 = $28.00)
                ],
            },
            {
                "id": "ord_student_003",
                "days_ago": 4,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-003", "quantity": 1, "discount_pct": 0.00},  # Vertical Mouse ($65.00 -> $65.00)
                    {"product_id": "item-002", "quantity": 1, "discount_pct": 0.15},  # Wrist Rest ($25.00 -> $21.25)
                ],
            },
        ],
    },
    {
        "id": "usr_demo_creator",
        "username": "demo_creator",
        "display_name": "Devon Reed (Creator)",
        "persona_description": "Audio/video producer, streamer, and tech content creator prioritizing 4K capture, studio acoustics, and high-speed multi-port connectivity.",
        "password_prefix": "Creator",
        "orders": [
            {
                "id": "ord_creator_001",
                "days_ago": 25,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-008", "quantity": 1, "discount_pct": 0.00},  # 4K Streaming Webcam ($110.00 -> $110.00)
                    {"product_id": "item-009", "quantity": 1, "discount_pct": 0.10},  # Desktop Mic with Arm ($85.00 -> $76.50)
                    {"product_id": "item-028", "quantity": 1, "discount_pct": 0.10},  # Acoustic Isolation Pads ($26.00 -> $23.40)
                ],
            },
            {
                "id": "ord_creator_002",
                "days_ago": 14,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-017", "quantity": 1, "discount_pct": 0.00},  # 7-in-1 Hub ($48.00 -> $48.00)
                    {"product_id": "item-010", "quantity": 1, "discount_pct": 0.10},  # ANC Headphones ($140.00 -> $126.00)
                    {"product_id": "item-012", "quantity": 1, "discount_pct": 0.10},  # Headphone Mount ($18.00 -> $16.20)
                ],
            },
            {
                "id": "ord_creator_003",
                "days_ago": 3,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-005", "quantity": 1, "discount_pct": 0.00},  # Monitor Riser Stand ($55.00 -> $55.00)
                    {"product_id": "item-007", "quantity": 1, "discount_pct": 0.10},  # ScreenBar Light ($75.00 -> $67.50)
                ],
            },
        ],
    },
    {
        "id": "usr_demo_traveler",
        "username": "demo_traveler",
        "display_name": "Jordan Hayes (Traveler)",
        "persona_description": "Remote digital nomad traveling frequently between co-working spaces and airports, valuing lightweight power, compact cases, and portable chargers.",
        "password_prefix": "Traveler",
        "orders": [
            {
                "id": "ord_traveler_001",
                "days_ago": 28,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-026", "quantity": 1, "discount_pct": 0.00},  # 65W Power Bank ($58.00 -> $58.00)
                    {"product_id": "item-024", "quantity": 1, "discount_pct": 0.15},  # Hard-Shell Travel Case ($22.00 -> $18.70)
                    {"product_id": "item-014", "quantity": 1, "discount_pct": 0.10},  # 65W GaN Charger ($35.00 -> $31.50)
                ],
            },
            {
                "id": "ord_traveler_002",
                "days_ago": 16,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-010", "quantity": 1, "discount_pct": 0.05},  # ANC Headphones ($140.00 -> $133.00)
                    {"product_id": "item-015", "quantity": 1, "discount_pct": 0.00},  # 100W USB-C Cable ($16.00 -> $16.00)
                    {"product_id": "item-021", "quantity": 1, "discount_pct": 0.10},  # Desk Tumbler ($24.00 -> $21.60)
                ],
            },
            {
                "id": "ord_traveler_003",
                "days_ago": 5,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-016", "quantity": 1, "discount_pct": 0.10},  # Laptop Stand ($42.00 -> $37.80)
                    {"product_id": "item-017", "quantity": 1, "discount_pct": 0.00},  # 7-in-1 Hub ($48.00 -> $48.00)
                ],
            },
        ],
    },
    {
        "id": "usr_demo_office",
        "username": "demo_office",
        "display_name": "Sarah Jenkins (Office Pro)",
        "persona_description": "Corporate knowledge worker prioritizing posture health, dual-monitor ergonomics, clean cable organization, and wrist support.",
        "password_prefix": "Office",
        "orders": [
            {
                "id": "ord_office_001",
                "days_ago": 30,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-001", "quantity": 1, "discount_pct": 0.00},  # Mechanical Keyboard ($80.00 -> $80.00)
                    {"product_id": "item-002", "quantity": 1, "discount_pct": 0.15},  # Wrist Rest ($25.00 -> $21.25)
                    {"product_id": "item-029", "quantity": 1, "discount_pct": 0.10},  # Lumbar Cushion ($40.00 -> $36.00)
                ],
            },
            {
                "id": "ord_office_002",
                "days_ago": 19,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-003", "quantity": 1, "discount_pct": 0.00},  # Vertical Mouse ($65.00 -> $65.00)
                    {"product_id": "item-005", "quantity": 1, "discount_pct": 0.10},  # Monitor Riser Stand ($55.00 -> $49.50)
                    {"product_id": "item-018", "quantity": 1, "discount_pct": 0.10},  # Cable Spine & Tray ($32.00 -> $28.80)
                ],
            },
            {
                "id": "ord_office_003",
                "days_ago": 6,
                "status": "completed_simulated",
                "provenance": "synthetic_demonstration",
                "items": [
                    {"product_id": "item-027", "quantity": 1, "discount_pct": 0.00},  # Dual-Arm Monitor Mount ($82.00 -> $82.00)
                    {"product_id": "item-019", "quantity": 1, "discount_pct": 0.10},  # Magnetic Cable Clips ($14.00 -> $12.60)
                    {"product_id": "item-020", "quantity": 1, "discount_pct": 0.00},  # Screen Cleaning Kit ($12.00 -> $12.00)
                ],
            },
        ],
    },
]

MERCHANT_PERSONAS = [
    {
        "id": "usr_demo_merchant",
        "username": "demo_merchant",
        "display_name": "FairCart Merchant (Store Owner)",
        "persona_description": "Store owner and multi-store merchant administrator managing catalogue pricing, margins, and profit intelligence.",
        "password_prefix": "Merchant",
        "role": "merchant",
        "orders": [],
    },
    {
        "id": "usr_demo_merchant_2",
        "username": "demo_merchant_2",
        "display_name": "Secondary Merchant (External Store)",
        "persona_description": "Secondary store merchant managing separate external storefronts.",
        "password_prefix": "MerchantTwo",
        "role": "merchant",
        "orders": [],
    },
]

ALL_PROVISIONED_PERSONAS = DEMO_PERSONAS + MERCHANT_PERSONAS

def generate_random_password(prefix: str) -> str:
    """Generates a cryptographically random, high-entropy password (20 chars)."""
    # 14 random chars from upper, lower, digits, and special characters
    special = "!@#$%^&*"
    chars = string.ascii_letters + string.digits + special
    rand_part = "".join(secrets.choice(chars) for _ in range(14))
    return f"{prefix}#{rand_part}"

def load_existing_local_credentials() -> dict[str, str]:
    """Reads existing plaintext credentials from .local/demo-credentials.local.md if present."""
    cred_file = PROJECT_ROOT / ".local" / "demo-credentials.local.md"
    if not cred_file.exists():
        return {}
    
    text = cred_file.read_text(encoding="utf-8")
    creds = {}
    for line in text.splitlines():
        match = re.search(r"\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|", line)
        if match:
            u, p = match.group(1), match.group(2)
            if u not in ("Username", "---"):
                creds[u] = p
    return creds

def save_local_credentials(credentials: dict[str, str]) -> Path:
    """Saves plaintext credentials exclusively to local ignored report."""
    local_dir = PROJECT_ROOT / ".local"
    local_dir.mkdir(parents=True, exist_ok=True)
    report_path = local_dir / "demo-credentials.local.md"

    md_lines = [
        "# FairCart AI — Local Demonstration Credentials",
        "",
        "> **CONFIDENTIAL / LOCAL ONLY** — Excluded from Git via `.gitignore`.",
        "> These credentials are provided strictly for demonstration and testing.",
        "",
        "| Persona | Username | Generated Password | Role Description |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for p in ALL_PROVISIONED_PERSONAS:
        u = p["username"]
        pw = credentials.get(u, "")
        role = p["persona_description"].split(".")[0]
        md_lines.append(f"| **{p['display_name']}** | `{u}` | `{pw}` | {role} |")

    md_lines.extend([
        "",
        "## Security Notes",
        "- Stored in SQLite as **Argon2id** password hashes ($m=65536, t=3, p=4).",
        "- Ordinary customer logins grant **zero** merchant administrative privileges.",
        "- Merchant logins are scoped to their respective owned multi-store datasets.",
        "- To rotate credentials, run `python -m backend.scripts.seed_demo_accounts --rotate`.",
    ])

    report_path.write_text("\n".join(md_lines), encoding="utf-8")
    return report_path


def seed_demo_accounts(db_path: str | None = None, rotate: bool = False) -> dict[str, str]:
    """Seeds demo customer and merchant accounts idempotently."""
    init_db(db_path)
    repo = CatalogRepository(db_path)
    ph = PasswordHasher()

    products = {p.id: p for p in repo.get_all_entities()}
    existing_creds = {} if rotate else load_existing_local_credentials()
    final_creds: dict[str, str] = {}

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # 1. Provision Users (Customers + Merchants)
        from backend.app.auth import verify_password

        for p in ALL_PROVISIONED_PERSONAS:
            u = p["username"]
            existing_user = repo.get_user_by_username(u)
            role = p.get("role", "customer")

            if existing_user and not rotate and u in existing_creds:
                if verify_password(existing_user.password_hash, existing_creds[u]):
                    final_creds[u] = existing_creds[u]
                else:
                    raw_pass = existing_creds[u]
                    p_hash = ph.hash(raw_pass)
                    final_creds[u] = raw_pass
                    cursor.execute("UPDATE users SET password_hash = ?, role = ? WHERE username = ?;", (p_hash, role, u))
            else:
                raw_pass = generate_random_password(p["password_prefix"])
                p_hash = ph.hash(raw_pass)
                final_creds[u] = raw_pass

                if existing_user:
                    cursor.execute("UPDATE users SET password_hash = ?, role = ? WHERE username = ?;", (p_hash, role, u))
                else:
                    now = datetime.now(timezone.utc).isoformat()
                    cursor.execute("""
                        INSERT INTO users (id, username, display_name, persona_description, password_hash, role, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (p["id"], u, p["display_name"], p["persona_description"], p_hash, role, now))

        # 2. Provision Synthetic Past Orders (Idempotent for customer personas)
        for p in DEMO_PERSONAS:
            user_id = p["id"]
            for ord_data in p["orders"]:
                order_id = ord_data["id"]
                # Check if order already exists
                cursor.execute("SELECT id FROM orders WHERE id = ?;", (order_id,))
                if cursor.fetchone():
                    continue

                order_items = []
                total_standard_cents = 0
                total_final_cents = 0

                for itm in ord_data["items"]:
                    pid = itm["product_id"]
                    qty = itm["quantity"]
                    prod = products.get(pid)
                    if not prod:
                        continue

                    ref_cents = prod.reference_price_cents
                    disc_pct = itm["discount_pct"]
                    unit_cents = int(round(ref_cents * (1.0 - disc_pct)))
                    line_total = unit_cents * qty
                    savings_cents = (ref_cents - unit_cents) * qty

                    total_standard_cents += ref_cents * qty
                    total_final_cents += line_total

                    order_items.append({
                        "product_id": prod.id,
                        "name": prod.name,
                        "category": prod.category,
                        "image_url": prod.image_url,
                        "quantity": qty,
                        "reference_price": round(ref_cents / 100.0, 2),
                        "simulated_price": round(unit_cents / 100.0, 2),
                        "savings": round(savings_cents / 100.0, 2),
                        "line_total": round(line_total / 100.0, 2),
                    })

                total_savings_cents = total_standard_cents - total_final_cents
                created_dt = datetime.now(timezone.utc) - timedelta(days=ord_data["days_ago"])

                cursor.execute("""
                    INSERT INTO orders (
                        id, user_id, created_at, status, provenance, currency, total_cents, savings_cents, items_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    order_id,
                    user_id,
                    created_dt.isoformat(),
                    ord_data["status"],
                    ord_data["provenance"],
                    "USD",
                    total_final_cents,
                    total_savings_cents,
                    json.dumps(order_items),
                ))

        conn.commit()
    finally:
        conn.close()

    save_local_credentials(final_creds)
    return final_creds

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed FairCart AI demo accounts and orders.")
    parser.add_argument("--rotate", action="store_true", help="Rotate passwords and generate new random credentials")
    args = parser.parse_args()

    creds = seed_demo_accounts(rotate=args.rotate)
    print("Successfully seeded 5 demonstration accounts and synthetic past orders.")
    print("Generated credentials written to .local/demo-credentials.local.md (gitignored).")
    for u, p in creds.items():
        print(f"  {u}: {p}")
