import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.db.database import init_db, get_connection

SAMPLE_PRODUCTS = [
    {
        "id": "item-001",
        "name": "Ergonomic Mechanical Keyboard",
        "category": "Keyboards",
        "subcategory": "Keyboards",
        "description": "Split wireless mechanical keyboard with quiet tactile switches and customizable tilt.",
        "reference_price_cents": 8000,   # $80.00
        "cogs_cents": 4000,              # $40.00 (50.0% base margin)
        "inventory": 45,
        "complementary_ids": "item-002,item-006,item-011",
        "tags": "wireless,ergonomic,split,mechanical,quiet,bluetooth",
        "use_cases": "productivity,study,wellness",
        "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-002",
        "name": "Padded Memory Foam Wrist Rest",
        "category": "Accessories",
        "subcategory": "Ergonomic Supports",
        "description": "Ergonomically contoured cooling gel wrist support for compact and full-size keyboards.",
        "reference_price_cents": 2500,   # $25.00
        "cogs_cents": 1000,              # $10.00 (60.0% base margin)
        "inventory": 80,
        "complementary_ids": "item-001,item-003",
        "tags": "ergonomic,memory-foam,cooling-gel,wrist-rest,comfortable",
        "use_cases": "productivity,gaming,study,wellness",
        "image_url": "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-003",
        "name": "Precision Vertical Wireless Mouse",
        "category": "Mice",
        "subcategory": "Ergonomic Mice",
        "description": "Ergonomic 57-degree vertical grip mouse to eliminate forearm strain with dual Bluetooth/2.4G.",
        "reference_price_cents": 6500,   # $65.00
        "cogs_cents": 3200,              # $32.00 (50.8% base margin)
        "inventory": 50,
        "complementary_ids": "item-004,item-002,item-006",
        "tags": "wireless,vertical,ergonomic,bluetooth,optical",
        "use_cases": "productivity,wellness,study",
        "image_url": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-004",
        "name": "Micro-Weave Desk Mat (XL)",
        "category": "Accessories",
        "subcategory": "Desk Surfaces",
        "description": "Water-resistant stitched-edge microfiber gaming and productivity surface (900x400mm).",
        "reference_price_cents": 3000,   # $30.00
        "cogs_cents": 1100,              # $11.00 (63.3% base margin)
        "inventory": 65,
        "complementary_ids": "item-001,item-003,item-023",
        "tags": "desk-mat,microfiber,water-resistant,xl,smooth,durable",
        "use_cases": "gaming,productivity,study",
        "image_url": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-005",
        "name": "Aluminum Monitor Riser Stand",
        "category": "Workspace",
        "subcategory": "Stands & Risers",
        "description": "Heavy-duty anodized aluminum monitor platform with integrated cable management slot.",
        "reference_price_cents": 5500,   # $55.00
        "cogs_cents": 2500,              # $25.00 (54.5% base margin)
        "inventory": 35,
        "complementary_ids": "item-007,item-008,item-018",
        "tags": "aluminum,riser,ergonomic,desk-organization,minimalist",
        "use_cases": "productivity,study,entertainment",
        "image_url": "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-006",
        "name": "Braided Coiled Keyboard Cable",
        "category": "Accessories",
        "subcategory": "Cables & Connectors",
        "description": "Double-sleeved aviator connector Type-C to Type-A cable with gold-plated connectors.",
        "reference_price_cents": 2800,   # $28.00
        "cogs_cents": 1000,              # $10.00 (64.3% base margin)
        "inventory": 40,
        "complementary_ids": "item-001,item-011",
        "tags": "cable,coiled,aviator,usb-c,custom-keyboard,aesthetic",
        "use_cases": "productivity,gaming,entertainment",
        "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-007",
        "name": "ScreenBar LED Monitor Light",
        "category": "Workspace",
        "subcategory": "Lighting",
        "description": "Auto-dimming eye-care screen lamp with zero screen glare and adjustable color temperatures.",
        "reference_price_cents": 7500,   # $75.00
        "cogs_cents": 3600,              # $36.00 (52.0% base margin)
        "inventory": 30,
        "complementary_ids": "item-005,item-008",
        "tags": "lighting,eye-care,led,auto-dimming,anti-glare,minimalist",
        "use_cases": "productivity,study,wellness",
        "image_url": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-008",
        "name": "4K Ultra HD Streaming Webcam",
        "category": "Audio & Video",
        "subcategory": "Cameras",
        "description": "Sony STARVIS sensor with dual omnidirectional noise-canceling mics and privacy shutter.",
        "reference_price_cents": 11000,  # $110.00
        "cogs_cents": 5800,              # $58.00 (47.3% base margin)
        "inventory": 25,
        "complementary_ids": "item-007,item-009",
        "tags": "webcam,4k,streaming,video-conference,microphone,sony-sensor",
        "use_cases": "productivity,study,entertainment,gaming",
        "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-009",
        "name": "USB-C Desktop Microphone with Arm",
        "category": "Audio & Video",
        "subcategory": "Audio Recording",
        "description": "Cardioid condenser microphone with boom arm, shock mount, and tap-to-mute sensor.",
        "reference_price_cents": 8500,   # $85.00
        "cogs_cents": 4200,              # $42.00 (50.6% base margin)
        "inventory": 30,
        "complementary_ids": "item-008,item-010",
        "tags": "microphone,usb-c,boom-arm,condenser,cardioid,streaming",
        "use_cases": "productivity,gaming,entertainment,study",
        "image_url": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-010",
        "name": "Active Noise Cancelling Headphones",
        "category": "Audio & Video",
        "subcategory": "Headphones",
        "description": "Over-ear hybrid ANC wireless headphones with 40h battery life and multi-point connectivity.",
        "reference_price_cents": 14000,  # $140.00
        "cogs_cents": 7200,              # $72.00 (48.6% base margin)
        "inventory": 20,
        "complementary_ids": "item-009,item-012,item-024",
        "tags": "anc,wireless,bluetooth,headphones,noise-cancelling,travel",
        "use_cases": "study,travel,productivity,entertainment",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-011",
        "name": "Custom Keycap Set (Retro Theme)",
        "category": "Keyboards",
        "subcategory": "Keycap Sets",
        "description": "Thick PBT dye-sublimated cherry profile keycaps compatible with MX-style switches.",
        "reference_price_cents": 4500,   # $45.00
        "cogs_cents": 1900,              # $19.00 (57.8% base margin)
        "inventory": 40,
        "complementary_ids": "item-001,item-006",
        "tags": "keycaps,pbt,retro,cherry-profile,custom-keyboard",
        "use_cases": "productivity,gaming,entertainment",
        "image_url": "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-012",
        "name": "Under-Desk Headphone Mount",
        "category": "Accessories",
        "subcategory": "Mounts & Organizers",
        "description": "Solid aluminum dual-hanger headset hook with built-in silicone cable loop.",
        "reference_price_cents": 1800,   # $18.00
        "cogs_cents": 600,               # $6.00 (66.7% base margin)
        "inventory": 70,
        "complementary_ids": "item-010,item-005",
        "tags": "headphone-mount,under-desk,aluminum,space-saving,organizer",
        "use_cases": "productivity,gaming,study",
        "image_url": "https://images.unsplash.com/photo-1546435770-a3e426bf472b?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-013",
        "name": "MagSafe 3-in-1 Wireless Charging Stand",
        "category": "Power & Cables",
        "subcategory": "Wireless Chargers",
        "description": "Fast 15W wireless dock for smartphone, smart watch, and wireless earbuds simultaneously.",
        "reference_price_cents": 6000,   # $60.00
        "cogs_cents": 2800,              # $28.00 (53.3% base margin)
        "inventory": 50,
        "complementary_ids": "item-014,item-015",
        "tags": "magsafe,wireless-charging,3-in-1,fast-charge,desk-dock",
        "use_cases": "productivity,study,travel",
        "image_url": "https://images.unsplash.com/photo-1586953208448-b95a79798f07?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-014",
        "name": "65W GaN Fast Wall Charger",
        "category": "Power & Cables",
        "subcategory": "Power Adapters",
        "description": "Compact gallium nitride dual USB-C and USB-A power adapter for laptops and tablets.",
        "reference_price_cents": 3500,   # $35.00
        "cogs_cents": 1400,              # $14.00 (60.0% base margin)
        "inventory": 75,
        "complementary_ids": "item-013,item-015,item-024",
        "tags": "gan,fast-charger,65w,usb-c,compact,travel-ready",
        "use_cases": "travel,productivity,study",
        "image_url": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-015",
        "name": "Braided 100W USB-C Cable (2m)",
        "category": "Power & Cables",
        "subcategory": "Cables & Connectors",
        "description": "Heavy-duty nylon braided power delivery cable with E-marker smart chip.",
        "reference_price_cents": 1600,   # $16.00
        "cogs_cents": 500,               # $5.00 (68.8% base margin)
        "inventory": 90,
        "complementary_ids": "item-013,item-014",
        "tags": "usb-c,100w,power-delivery,braided,durable,charging",
        "use_cases": "productivity,gaming,study,travel",
        "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-016",
        "name": "Adjustable Laptop Cooling Stand",
        "category": "Workspace",
        "subcategory": "Stands & Risers",
        "description": "Foldable ventilated ergonomic laptop elevator supporting devices up to 17 inches.",
        "reference_price_cents": 4200,   # $42.00
        "cogs_cents": 1800,              # $18.00 (57.1% base margin)
        "inventory": 40,
        "complementary_ids": "item-001,item-003,item-017",
        "tags": "laptop-stand,ergonomic,cooling,foldable,aluminum,portable",
        "use_cases": "productivity,study,travel,wellness",
        "image_url": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-017",
        "name": "USB-C Multiport Hub (7-in-1)",
        "category": "Workspace",
        "subcategory": "Hubs & Docks",
        "description": "Includes 4K HDMI, 100W PD pass-through, SD card reader, and 3x USB 3.0 ports.",
        "reference_price_cents": 4800,   # $48.00
        "cogs_cents": 2100,              # $21.00 (56.2% base margin)
        "inventory": 45,
        "complementary_ids": "item-016,item-001",
        "tags": "hub,dock,usb-c,hdmi,4k,sd-card,multiport,connectivity",
        "use_cases": "productivity,study,travel",
        "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-018",
        "name": "Cable Management Spine & Tray",
        "category": "Workspace",
        "subcategory": "Desk Organization",
        "description": "Heavy duty under-desk wire organizer basket with flexible desk-to-floor spine.",
        "reference_price_cents": 3200,   # $32.00
        "cogs_cents": 1200,              # $12.00 (62.5% base margin)
        "inventory": 55,
        "complementary_ids": "item-005,item-019",
        "tags": "cable-tray,cable-management,clean-desk,spine,under-desk",
        "use_cases": "productivity,gaming,study",
        "image_url": "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-019",
        "name": "Self-Adhesive Magnetic Cable Clips",
        "category": "Accessories",
        "subcategory": "Cable Clips",
        "description": "6-pack of magnetic cable anchors to prevent cords from dropping behind desks.",
        "reference_price_cents": 1400,   # $14.00
        "cogs_cents": 400,               # $4.00 (71.4% base margin)
        "inventory": 100,
        "complementary_ids": "item-018,item-015",
        "tags": "cable-clips,magnetic,organization,adhesive,desk-neatness",
        "use_cases": "productivity,gaming,study",
        "image_url": "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-020",
        "name": "Screen Cleaning Kit with Microfiber",
        "category": "Accessories",
        "subcategory": "Maintenance",
        "description": "Ammonia and alcohol-free gentle display cleaning spray with two microfiber cloths.",
        "reference_price_cents": 1200,   # $12.00
        "cogs_cents": 350,               # $3.50 (70.8% base margin)
        "inventory": 120,
        "complementary_ids": "item-007,item-008",
        "tags": "cleaning-kit,screen-cleaner,microfiber,care,anti-static",
        "use_cases": "productivity,gaming,study,wellness",
        "image_url": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-021",
        "name": "Insulated Stainless Steel Desk Tumbler (500ml)",
        "category": "Lifestyle",
        "subcategory": "Drinkware",
        "description": "Vacuum-insulated ceramic-lined spill-resistant thermal mug keeping drinks hot for 6h or cold for 12h.",
        "reference_price_cents": 2400,   # $24.00
        "cogs_cents": 800,               # $8.00 (66.7% base margin)
        "inventory": 60,
        "complementary_ids": "item-004,item-022",
        "tags": "drinkware,tumbler,hydration,thermal,spill-resistant,desk-safe",
        "use_cases": "productivity,gaming,study,wellness,travel",
        "image_url": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-022",
        "name": "Organic Focus Herbal Tea & Infuser Set",
        "category": "Lifestyle",
        "subcategory": "Refreshments",
        "description": "Certified organic botanical blend with spearmint, ginkgo, and stainless steel twist infuser.",
        "reference_price_cents": 1600,   # $16.00
        "cogs_cents": 500,               # $5.00 (68.8% base margin)
        "inventory": 70,
        "complementary_ids": "item-021,item-004",
        "tags": "tea,organic,refreshment,focus,caffeine-free,wellness",
        "use_cases": "productivity,study,wellness",
        "image_url": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-023",
        "name": "Low-Latency RGB Wireless Gaming Mouse",
        "category": "Mice",
        "subcategory": "Gaming Mice",
        "description": "Ultra-lightweight 58g ergonomic gaming mouse with 26K DPI optical sensor and PTFE glides.",
        "reference_price_cents": 7000,   # $70.00
        "cogs_cents": 3400,              # $34.00 (51.4% base margin)
        "inventory": 45,
        "complementary_ids": "item-004,item-006,item-021",
        "tags": "gaming,rgb,high-dpi,ultra-light,wireless,ptfe",
        "use_cases": "gaming,entertainment",
        "image_url": "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-024",
        "name": "Protective Hard-Shell Tech Travel Case",
        "category": "Accessories",
        "subcategory": "Travel Organizers",
        "description": "Water-resistant EVA hard-shell organizer case for cables, chargers, mouse, and power banks.",
        "reference_price_cents": 2200,   # $22.00
        "cogs_cents": 750,               # $7.50 (65.9% base margin)
        "inventory": 65,
        "complementary_ids": "item-014,item-015,item-010",
        "tags": "travel,travel-case,organizer,shockproof,eva,portable",
        "use_cases": "travel,productivity,study",
        "image_url": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80"
    }
]

def seed_catalog(db_path: str | None = None) -> int:
    """Seeds the 24 products into SQLite database deterministically using INSERT OR REPLACE."""
    init_db(db_path)
    inserted_count = 0
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        for p in SAMPLE_PRODUCTS:
            cursor.execute("""
                INSERT OR REPLACE INTO products (
                    id, name, category, subcategory, description,
                    reference_price_cents, cogs_cents, inventory,
                    complementary_ids, tags, use_cases, image_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                p["id"],
                p["name"],
                p["category"],
                p.get("subcategory", p["category"]),
                p["description"],
                p["reference_price_cents"],
                p["cogs_cents"],
                p["inventory"],
                p["complementary_ids"],
                p.get("tags", ""),
                p.get("use_cases", "productivity"),
                p["image_url"]
            ))
            inserted_count += 1
        conn.commit()
    finally:
        conn.close()
    return inserted_count

if __name__ == "__main__":
    count = seed_catalog()
    print(f"Catalog successfully seeded with {count} verified products.")
