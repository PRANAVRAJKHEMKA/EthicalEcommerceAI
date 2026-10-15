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
        "complementary_ids": "item-002,item-006,item-011,item-025",
        "tags": "wireless,ergonomic,split,mechanical,quiet,bluetooth,typing",
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
        "complementary_ids": "item-001,item-003,item-029",
        "tags": "ergonomic,memory-foam,cooling-gel,wrist-rest,comfortable,support",
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
        "complementary_ids": "item-004,item-002,item-016",
        "tags": "wireless,vertical,ergonomic,bluetooth,optical,neutral-grip",
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
        "complementary_ids": "item-001,item-003,item-023,item-032",
        "tags": "desk-mat,microfiber,water-resistant,xl,smooth,durable,gliding",
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
        "tags": "aluminum,riser,ergonomic,desk-organization,minimalist,elevation",
        "use_cases": "productivity,study,wellness",
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
        "complementary_ids": "item-001,item-011,item-025",
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
        "complementary_ids": "item-005,item-008,item-020",
        "tags": "lighting,eye-care,led,auto-dimming,anti-glare,minimalist,reading",
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
        "complementary_ids": "item-007,item-009,item-020",
        "tags": "webcam,4k,streaming,video-conference,microphone,sony-sensor,zoom",
        "use_cases": "productivity,study,entertainment,gaming",
        "image_url": "https://images.unsplash.com/photo-1588702547919-26089e690ecc?auto=format&fit=crop&w=600&q=80"
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
        "complementary_ids": "item-008,item-010,item-028",
        "tags": "microphone,usb-c,boom-arm,condenser,cardioid,streaming,podcasting",
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
        "complementary_ids": "item-009,item-012,item-024,item-026",
        "tags": "anc,wireless,bluetooth,headphones,noise-cancelling,travel,focus",
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
        "complementary_ids": "item-001,item-006,item-025",
        "tags": "keycaps,pbt,retro,cherry-profile,custom-keyboard,dye-sub",
        "use_cases": "productivity,gaming,entertainment",
        "image_url": "https://images.unsplash.com/photo-1601445638532-3c6f6c3aa1d6?auto=format&fit=crop&w=600&q=80"
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
        "complementary_ids": "item-010,item-005,item-018",
        "tags": "headphone-mount,under-desk,aluminum,space-saving,organizer,silicone",
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
        "complementary_ids": "item-014,item-015,item-026",
        "tags": "magsafe,wireless-charging,3-in-1,fast-charge,desk-dock,nightstand",
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
        "complementary_ids": "item-013,item-015,item-024,item-026",
        "tags": "gan,fast-charger,65w,usb-c,compact,travel-ready,power-adapter",
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
        "complementary_ids": "item-013,item-014,item-017,item-026",
        "tags": "usb-c,100w,power-delivery,braided,durable,charging,high-current",
        "use_cases": "productivity,gaming,study,travel",
        "image_url": "https://images.unsplash.com/photo-1563770660941-20978e870e26?auto=format&fit=crop&w=600&q=80"
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
        "complementary_ids": "item-001,item-003,item-017,item-029",
        "tags": "laptop-stand,ergonomic,cooling,foldable,aluminum,portable,ventilation",
        "use_cases": "productivity,study,travel,wellness",
        "image_url": "https://images.unsplash.com/photo-1541807084-5c52b6b3adef?auto=format&fit=crop&w=600&q=80"
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
        "complementary_ids": "item-016,item-001,item-030",
        "tags": "hub,dock,usb-c,hdmi,4k,sd-card,multiport,connectivity,adapter",
        "use_cases": "productivity,study,travel",
        "image_url": "https://images.unsplash.com/photo-1625842268584-8f3296236761?auto=format&fit=crop&w=600&q=80"
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
        "complementary_ids": "item-005,item-019,item-012",
        "tags": "cable-tray,cable-management,clean-desk,spine,under-desk,routing",
        "use_cases": "productivity,gaming,study",
        "image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=600&q=80"
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
        "complementary_ids": "item-018,item-015,item-006",
        "tags": "cable-clips,magnetic,organization,adhesive,desk-neatness,anchors",
        "use_cases": "productivity,gaming,study",
        "image_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=600&q=80"
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
        "complementary_ids": "item-007,item-008,item-016",
        "tags": "cleaning-kit,screen-cleaner,microfiber,care,anti-static,screen-care",
        "use_cases": "productivity,gaming,study,wellness",
        "image_url": "https://images.unsplash.com/photo-1585421514738-01798e348b17?auto=format&fit=crop&w=600&q=80"
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
        "complementary_ids": "item-004,item-022,item-031",
        "tags": "drinkware,tumbler,hydration,thermal,spill-resistant,desk-safe,ceramic-lined",
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
        "complementary_ids": "item-021,item-031,item-004",
        "tags": "tea,organic,refreshment,focus,caffeine-free,wellness,herbal",
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
        "complementary_ids": "item-004,item-006,item-032",
        "tags": "gaming,rgb,high-dpi,ultra-light,wireless,ptfe,low-latency",
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
        "complementary_ids": "item-014,item-015,item-010,item-026",
        "tags": "travel,travel-case,organizer,shockproof,eva,portable,cable-case",
        "use_cases": "travel,productivity,study",
        "image_url": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-025",
        "name": "Hot-Swappable Mechanical Switch Pack (35x)",
        "category": "Keyboards",
        "subcategory": "Components",
        "description": "Factory-lubricated 5-pin mechanical switches offering crisp tactile response and smooth keystrokes.",
        "reference_price_cents": 3200,   # $32.00
        "cogs_cents": 1200,              # $12.00 (62.5% base margin)
        "inventory": 45,
        "complementary_ids": "item-001,item-011,item-006",
        "tags": "switches,tactile,lubed,hot-swap,mechanical,custom-keyboard,modding",
        "use_cases": "productivity,gaming,entertainment",
        "image_url": "https://images.unsplash.com/photo-1595225476474-87563907a212?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-026",
        "name": "Ultra-Compact 65W Power Bank (20,000mAh)",
        "category": "Power & Cables",
        "subcategory": "Portable Power",
        "description": "High-capacity airline-safe power bank with smart LCD status display and dual USB-C fast ports.",
        "reference_price_cents": 5800,   # $58.00
        "cogs_cents": 2600,              # $26.00 (55.2% base margin)
        "inventory": 40,
        "complementary_ids": "item-015,item-014,item-024",
        "tags": "power-bank,portable,battery,fast-charge,usb-c,travel,digital-display",
        "use_cases": "travel,study,productivity",
        "image_url": "https://images.unsplash.com/photo-1609592424367-7b89569766bb?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-027",
        "name": "Dual-Arm Gas Spring Monitor Mount",
        "category": "Workspace",
        "subcategory": "Mounts & Organizers",
        "description": "Full-motion counterbalanced dual monitor desk arm supporting screens up to 32 inches each.",
        "reference_price_cents": 8200,   # $82.00
        "cogs_cents": 3800,              # $38.00 (53.7% base margin)
        "inventory": 25,
        "complementary_ids": "item-005,item-007,item-018",
        "tags": "monitor-arm,dual-screen,gas-spring,ergonomic,desk-mount,cable-channels",
        "use_cases": "productivity,gaming,wellness",
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-028",
        "name": "Studio Acoustic Desk Isolation Pads",
        "category": "Audio & Video",
        "subcategory": "Audio Accessories",
        "description": "High-density polyurethane decoupling foam pads for desktop speakers to eliminate vibrations.",
        "reference_price_cents": 2600,   # $26.00
        "cogs_cents": 900,               # $9.00 (65.4% base margin)
        "inventory": 50,
        "complementary_ids": "item-009,item-010,item-004",
        "tags": "acoustic,isolation,pads,speakers,audio,damping,foam",
        "use_cases": "productivity,entertainment,gaming",
        "image_url": "https://images.unsplash.com/photo-1545454675-3531b543be5d?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-029",
        "name": "Memory Foam Ergonomic Lumbar Cushion",
        "category": "Workspace",
        "subcategory": "Ergonomic Supports",
        "description": "Orthopedic contoured memory foam back support with breathable mesh cover for task chairs.",
        "reference_price_cents": 4000,   # $40.00
        "cogs_cents": 1600,              # $16.00 (60.0% base margin)
        "inventory": 45,
        "complementary_ids": "item-002,item-016,item-003",
        "tags": "lumbar,back-support,ergonomic,memory-foam,posture,chair-cushion",
        "use_cases": "wellness,productivity,study",
        "image_url": "https://images.unsplash.com/photo-1584100936595-c0654b55a2e2?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-030",
        "name": "Braided Ultra High-Speed HDMI 2.1 Cable (2m)",
        "category": "Power & Cables",
        "subcategory": "Cables & Connectors",
        "description": "48Gbps bandwidth cable supporting 8K@60Hz and 4K@120Hz gaming with dynamic HDR and eARC.",
        "reference_price_cents": 2000,   # $20.00
        "cogs_cents": 600,               # $6.00 (70.0% base margin)
        "inventory": 80,
        "complementary_ids": "item-017,item-008,item-027",
        "tags": "hdmi,hdmi-2.1,8k,4k-120hz,gaming,braided,high-speed,display",
        "use_cases": "gaming,entertainment,productivity",
        "image_url": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-031",
        "name": "Artisanal Dark Chocolate & Nut Fuel Pack",
        "category": "Lifestyle",
        "subcategory": "Refreshments",
        "description": "Small-batch 72% Ecuadorian cacao bites with roasted almonds and sea salt for study and work sessions.",
        "reference_price_cents": 1400,   # $14.00
        "cogs_cents": 450,               # $4.50 (67.9% base margin)
        "inventory": 85,
        "complementary_ids": "item-021,item-022,item-004",
        "tags": "snack,chocolate,nuts,energy,focus,refreshment,desk-snack",
        "use_cases": "study,productivity,gaming,wellness",
        "image_url": "https://images.unsplash.com/photo-1599599810769-bcde5a160d32?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-032",
        "name": "Ultra-Glide Mouse Bungee with 2-Port USB Hub",
        "category": "Mice",
        "subcategory": "Gaming Accessories",
        "description": "Tangle-free anti-drag flexible silicone arm with weighted base and integrated dual USB 3.0 ports.",
        "reference_price_cents": 2800,   # $28.00
        "cogs_cents": 1000,              # $10.00 (64.3% base margin)
        "inventory": 50,
        "complementary_ids": "item-023,item-004,item-006",
        "tags": "mouse-bungee,cable-holder,gaming,anti-drag,silicone,usb-hub,esports",
        "use_cases": "gaming,entertainment",
        "image_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=600&q=80"
    }
]

def seed_catalog(db_path: str | None = None) -> int:
    """Seeds the 32 products into SQLite database deterministically using INSERT OR REPLACE."""
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
