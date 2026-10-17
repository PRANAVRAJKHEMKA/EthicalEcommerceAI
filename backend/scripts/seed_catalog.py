import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.config import settings
from backend.app.db.database import init_db, get_connection
from backend.app.db.repository import CatalogRepository

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
        "complementary_ids": "item-002,item-006,item-011,item-016,item-025",
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
    },
    # -------------------------------------------------------------------------
    # GROCERY & PANTRY (item-033 to item-040)
    # -------------------------------------------------------------------------
    {
        "id": "item-033",
        "name": "Artisanal Bronze-Cut Rigatoni Pasta",
        "category": "Grocery & Pantry",
        "subcategory": "Pasta & Grains",
        "description": "Slow-dried Italian durum wheat bronze-die rigatoni pasta with a coarse texture for optimal sauce adhesion.",
        "reference_price_cents": 650,    # $6.50
        "cogs_cents": 280,               # $2.80 (56.9% base margin)
        "inventory": 60,
        "complementary_ids": "item-034,item-035,item-036,item-056",
        "tags": "pasta,durum-wheat,bronze-cut,italian,dinner,pantry-staple",
        "use_cases": "pantry,kitchen,wellness",
        "image_url": "https://images.unsplash.com/photo-1621996346565-e3d5d6281728?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-034",
        "name": "Slow-Simmered San Marzano Marinara Sauce",
        "category": "Grocery & Pantry",
        "subcategory": "Sauces & Condiments",
        "description": "Traditional Italian marinara cooked with whole peeled San Marzano tomatoes, fresh basil, and extra virgin olive oil.",
        "reference_price_cents": 800,    # $8.00
        "cogs_cents": 350,               # $3.50 (56.3% base margin)
        "inventory": 55,
        "complementary_ids": "item-033,item-035,item-036,item-049",
        "tags": "marinara,tomato-sauce,san-marzano,pasta-sauce,italian,organic",
        "use_cases": "pantry,kitchen",
        "image_url": "https://images.unsplash.com/photo-1572449043416-55f4685c9bb7?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-035",
        "name": "Single-Estate Extra Virgin Olive Oil",
        "category": "Grocery & Pantry",
        "subcategory": "Oils & Vinegars",
        "description": "First cold-pressed extra virgin olive oil from Sicilian olives with notes of fresh green herbs and artichoke (500ml).",
        "reference_price_cents": 1800,   # $18.00
        "cogs_cents": 850,               # $8.50 (52.8% base margin)
        "inventory": 45,
        "complementary_ids": "item-033,item-034,item-049,item-051",
        "tags": "olive-oil,evoo,cold-pressed,sicilian,finishing-oil,culinary",
        "use_cases": "pantry,kitchen,wellness",
        "image_url": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-036",
        "name": "Aged Parmigiano Reggiano Wedge",
        "category": "Grocery & Pantry",
        "subcategory": "Cheese & Dairy",
        "description": "24-month aged authentic Italian Parmigiano Reggiano with rich umami depth and crystalline crunch (200g).",
        "reference_price_cents": 1150,   # $11.50
        "cogs_cents": 550,               # $5.50 (52.2% base margin)
        "inventory": 40,
        "complementary_ids": "item-033,item-034,item-035",
        "tags": "cheese,parmesan,parmigiano,aged,italian,umami,gourmet",
        "use_cases": "pantry,kitchen",
        "image_url": "https://images.unsplash.com/photo-1452195100486-9cc805987862?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-037",
        "name": "Organic Whole Bean Medium Roast Coffee",
        "category": "Grocery & Pantry",
        "subcategory": "Coffee & Tea",
        "description": "Single-origin washed Ethiopian Arabica beans with floral jasmine aroma and bright citrus sweetness (12oz).",
        "reference_price_cents": 1600,   # $16.00
        "cogs_cents": 700,               # $7.00 (56.3% base margin)
        "inventory": 65,
        "complementary_ids": "item-027,item-038,item-039",
        "tags": "coffee,whole-bean,arabica,ethiopian,organic,medium-roast",
        "use_cases": "productivity,study,wellness",
        "image_url": "https://images.unsplash.com/photo-1559056199-641a0ac8b55e?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-038",
        "name": "Raw Wildflower Mountain Honey",
        "category": "Grocery & Pantry",
        "subcategory": "Sweeteners & Spreads",
        "description": "Unfiltered raw mountain honey harvested from sustainably kept high-altitude apiaries (16oz jar).",
        "reference_price_cents": 1200,   # $12.00
        "cogs_cents": 500,               # $5.00 (58.3% base margin)
        "inventory": 50,
        "complementary_ids": "item-037,item-039,item-079",
        "tags": "honey,raw,wildflower,unfiltered,natural,sweetener",
        "use_cases": "wellness,study,pantry",
        "image_url": "https://images.unsplash.com/photo-1587049352846-4a222e784d38?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-039",
        "name": "Rolled Organic Gluten-Free Oats",
        "category": "Grocery & Pantry",
        "subcategory": "Breakfast & Cereals",
        "description": "Thick-rolled whole grain gluten-free oats perfect for warm morning porridge, overnight oats, and baking (32oz).",
        "reference_price_cents": 750,    # $7.50
        "cogs_cents": 300,               # $3.00 (60.0% base margin)
        "inventory": 70,
        "complementary_ids": "item-038,item-040,item-057",
        "tags": "oats,gluten-free,organic,breakfast,whole-grain,meal-prep",
        "use_cases": "wellness,productivity,pantry",
        "image_url": "https://images.unsplash.com/photo-1586444248902-2f64eddc13df?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-040",
        "name": "Organic Raw California Walnuts",
        "category": "Grocery & Pantry",
        "subcategory": "Nuts & Dried Fruit",
        "description": "Crisp unsalted California walnut halves naturally rich in plant-based Omega-3 ALA fatty acids (16oz pouch).",
        "reference_price_cents": 1300,   # $13.00
        "cogs_cents": 600,               # $6.00 (53.8% base margin)
        "inventory": 55,
        "complementary_ids": "item-031,item-038,item-039",
        "tags": "walnuts,nuts,raw,omega-3,healthy-fats,brain-food,snack",
        "use_cases": "study,wellness,productivity,pantry",
        "image_url": "https://images.unsplash.com/photo-1508061253366-f7da158b6d46?auto=format&fit=crop&w=600&q=80"
    },
    # -------------------------------------------------------------------------
    # STATIONERY & STUDY (item-041 to item-048)
    # -------------------------------------------------------------------------
    {
        "id": "item-041",
        "name": "Hardcover Dot-Grid Journal Notebook",
        "category": "Stationery & Study",
        "subcategory": "Notebooks & Journals",
        "description": "Lay-flat A5 notebook with 160 numbered pages of 120gsm bleed-resistant bamboo paper and dual ribbon bookmarks.",
        "reference_price_cents": 2200,   # $22.00
        "cogs_cents": 900,               # $9.00 (59.1% base margin)
        "inventory": 65,
        "complementary_ids": "item-042,item-043,item-044,item-048",
        "tags": "journal,notebook,dot-grid,bullet-journal,lay-flat,bamboo-paper",
        "use_cases": "study,productivity,wellness",
        "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-042",
        "name": "Quick-Dry Fine Gel Ink Pens (Pack of 5)",
        "category": "Stationery & Study",
        "subcategory": "Writing Instruments",
        "description": "0.5mm Japanese tungsten carbide rollerball gel pens with instant smear-proof pigment black ink.",
        "reference_price_cents": 1250,   # $12.50
        "cogs_cents": 480,               # $4.80 (61.6% base margin)
        "inventory": 80,
        "complementary_ids": "item-041,item-043,item-044,item-045",
        "tags": "pens,gel-pens,black-ink,fine-point,smear-proof,writing",
        "use_cases": "study,productivity",
        "image_url": "https://images.unsplash.com/photo-1585336261026-7756f7e43681?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-043",
        "name": "Aesthetic Pastel Chisel Highlighters",
        "category": "Stationery & Study",
        "subcategory": "Writing Instruments",
        "description": "Set of 6 soft muted pastel dual-tip highlighters engineered to prevent eye fatigue during textbook study.",
        "reference_price_cents": 950,    # $9.50
        "cogs_cents": 350,               # $3.50 (63.2% base margin)
        "inventory": 75,
        "complementary_ids": "item-041,item-042,item-044,item-047",
        "tags": "highlighters,pastel,chisel-tip,study-tools,student,reading",
        "use_cases": "study,productivity",
        "image_url": "https://images.unsplash.com/photo-1583485088034-697b5bc54ccd?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-044",
        "name": "Transparent Adhesive Sticky Notes",
        "category": "Stationery & Study",
        "subcategory": "Desk Accessories",
        "description": "3 pads of clear waterproof vellum adhesive sticky notes allowing annotations directly over textbook diagrams.",
        "reference_price_cents": 700,    # $7.00
        "cogs_cents": 250,               # $2.50 (64.3% base margin)
        "inventory": 90,
        "complementary_ids": "item-041,item-042,item-043,item-047",
        "tags": "sticky-notes,transparent,vellum,annotation,study-aid,removable",
        "use_cases": "study,productivity",
        "image_url": "https://images.unsplash.com/photo-1606326608606-aa0b62935f2b?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-045",
        "name": "Magnetic Metal Wire Desk Organizer Tray",
        "category": "Stationery & Study",
        "subcategory": "Desk Organization",
        "description": "Minimalist powder-coated steel modular desk organizer with dedicated slots for pens, notes, and accessories.",
        "reference_price_cents": 1800,   # $18.00
        "cogs_cents": 700,               # $7.00 (61.1% base margin)
        "inventory": 50,
        "complementary_ids": "item-041,item-042,item-010,item-085",
        "tags": "organizer,desk-tray,steel,minimalist,stationery,storage",
        "use_cases": "productivity,study,wellness",
        "image_url": "https://images.unsplash.com/photo-1507842229451-7f01be8610ce?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-046",
        "name": "Brass Precision Mechanical Pencil",
        "category": "Stationery & Study",
        "subcategory": "Writing Instruments",
        "description": "Solid brass hexagonal drafting pencil with knurled grip, fixed 4mm lead sleeve, and balanced center of mass (0.5mm).",
        "reference_price_cents": 2400,   # $24.00
        "cogs_cents": 1000,              # $10.00 (58.3% base margin)
        "inventory": 45,
        "complementary_ids": "item-041,item-044,item-047",
        "tags": "pencil,mechanical-pencil,brass,drafting,technical-drawing,0.5mm",
        "use_cases": "study,productivity",
        "image_url": "https://images.unsplash.com/photo-1585336261026-7756f7e43681?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-047",
        "name": "Index Tab Divider Flags with Ruler",
        "category": "Stationery & Study",
        "subcategory": "Desk Accessories",
        "description": "400 repositionable translucent film page markers with writeable surface and portable snap-in plastic ruler.",
        "reference_price_cents": 600,    # $6.00
        "cogs_cents": 200,               # $2.00 (66.7% base margin)
        "inventory": 100,
        "complementary_ids": "item-041,item-043,item-044,item-048",
        "tags": "tabs,index-flags,page-markers,bookmarks,study,organization",
        "use_cases": "study,productivity",
        "image_url": "https://images.unsplash.com/photo-1586075010923-2dd4570fb338?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-048",
        "name": "Ergonomic Angle Document & Book Holder",
        "category": "Stationery & Study",
        "subcategory": "Ergonomic Reading",
        "description": "Foldable aluminum desktop book stand with 6 adjustable angles and spring-loaded page clips to relieve neck tension.",
        "reference_price_cents": 2600,   # $26.00
        "cogs_cents": 1100,              # $11.00 (57.7% base margin)
        "inventory": 40,
        "complementary_ids": "item-041,item-007,item-008",
        "tags": "book-stand,document-holder,reading-stand,ergonomic,posture,study",
        "use_cases": "study,wellness,productivity",
        "image_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=600&q=80"
    },
    # -------------------------------------------------------------------------
    # KITCHEN & DINING (item-049 to item-056)
    # -------------------------------------------------------------------------
    {
        "id": "item-049",
        "name": "Hard-Anodized Nonstick 10-Inch Skillet Pan",
        "category": "Kitchen & Dining",
        "subcategory": "Cookware",
        "description": "Triple-layer reinforced nonstick frying pan with heavy-gauge aluminum core and stay-cool cast stainless steel handle.",
        "reference_price_cents": 4500,   # $45.00
        "cogs_cents": 2000,              # $20.00 (55.6% base margin)
        "inventory": 45,
        "complementary_ids": "item-050,item-051,item-035,item-067",
        "tags": "skillet,frying-pan,nonstick,cookware,kitchen,cooking",
        "use_cases": "kitchen,pantry,wellness",
        "image_url": "https://images.unsplash.com/photo-1584990347449-39906f0e303d?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-050",
        "name": "Heat-Resistant Silicone Cooking Utensils",
        "category": "Kitchen & Dining",
        "subcategory": "Kitchen Utensils",
        "description": "5-piece seamless food-grade silicone utensil set including spatula, spoonula, slotted turner, ladle, and basting brush.",
        "reference_price_cents": 2800,   # $28.00
        "cogs_cents": 1100,              # $11.00 (60.7% base margin)
        "inventory": 60,
        "complementary_ids": "item-049,item-051,item-053",
        "tags": "utensils,silicone,spatula,ladle,heat-resistant,nonstick-safe",
        "use_cases": "kitchen,pantry",
        "image_url": "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-051",
        "name": "End-Grain Organic Bamboo Cutting Board",
        "category": "Kitchen & Dining",
        "subcategory": "Food Prep",
        "description": "Extra-large reversible organic moso bamboo chopping board with deep perimeter juice groove and side carry handles.",
        "reference_price_cents": 3200,   # $32.00
        "cogs_cents": 1350,              # $13.50 (57.8% base margin)
        "inventory": 50,
        "complementary_ids": "item-052,item-049,item-050,item-068",
        "tags": "cutting-board,chopping-board,bamboo,organic,juice-groove,kitchen",
        "use_cases": "kitchen,pantry",
        "image_url": "https://images.unsplash.com/photo-1590794056470-36e67610029b?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-052",
        "name": "Japanese High-Carbon Stainless Chef Knife",
        "category": "Kitchen & Dining",
        "subcategory": "Cutlery",
        "description": "8-inch razor-sharp gyuto chef knife forged from high-carbon AUS-10 steel with ergonomic pakkawood handle.",
        "reference_price_cents": 6500,   # $65.00
        "cogs_cents": 2800,              # $28.00 (56.9% base margin)
        "inventory": 35,
        "complementary_ids": "item-051,item-049,item-050",
        "tags": "knife,chef-knife,cutlery,japanese-steel,razor-sharp,culinary",
        "use_cases": "kitchen,pantry",
        "image_url": "https://images.unsplash.com/photo-1593618998160-e34014e67546?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-053",
        "name": "Stainless Measuring Spoons & Cups Set",
        "category": "Kitchen & Dining",
        "subcategory": "Baking & Prep",
        "description": "Heavy-duty 18/8 stainless steel measuring cups and magnetic nesting spoons with etched metric and imperial markings.",
        "reference_price_cents": 1900,   # $19.00
        "cogs_cents": 750,               # $7.50 (60.5% base margin)
        "inventory": 65,
        "complementary_ids": "item-049,item-050,item-055",
        "tags": "measuring-cups,measuring-spoons,stainless-steel,baking,cooking",
        "use_cases": "kitchen,pantry",
        "image_url": "https://images.unsplash.com/photo-1584990347449-39906f0e303d?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-054",
        "name": "Cast Iron Grill Press with Wood Handle",
        "category": "Kitchen & Dining",
        "subcategory": "Cookware Accessories",
        "description": "Heavy seasoned cast iron bacon and burger weight press with stay-cool natural hardwood handle.",
        "reference_price_cents": 2200,   # $22.00
        "cogs_cents": 900,               # $9.00 (59.1% base margin)
        "inventory": 40,
        "complementary_ids": "item-049,item-050",
        "tags": "grill-press,cast-iron,burger-smash,cooking,barbecue",
        "use_cases": "kitchen,pantry",
        "image_url": "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-055",
        "name": "Oven-Safe Silicone Baking Mat Pair",
        "category": "Kitchen & Dining",
        "subcategory": "Bakeware",
        "description": "Set of 2 half-sheet fiberglass-reinforced non-stick silicone mats rated heat-resistant to 480 degrees Fahrenheit.",
        "reference_price_cents": 1600,   # $16.00
        "cogs_cents": 600,               # $6.00 (62.5% base margin)
        "inventory": 70,
        "complementary_ids": "item-053,item-050",
        "tags": "baking-mat,silicone,nonstick,oven-safe,reusable,baking",
        "use_cases": "kitchen,pantry",
        "image_url": "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-056",
        "name": "Stainless Steel Fine Mesh Colander",
        "category": "Kitchen & Dining",
        "subcategory": "Food Prep",
        "description": "5-quart micro-perforated stainless steel colander with wide rim handles and elevated pedestal base.",
        "reference_price_cents": 1850,   # $18.50
        "cogs_cents": 750,               # $7.50 (59.5% base margin)
        "inventory": 55,
        "complementary_ids": "item-033,item-049,item-051",
        "tags": "colander,strainer,stainless-steel,pasta-strainer,kitchen,drainer",
        "use_cases": "kitchen,pantry",
        "image_url": "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=600&q=80"
    },
    # -------------------------------------------------------------------------
    # FOOD STORAGE & ORGANIZATION (item-057 to item-064)
    # -------------------------------------------------------------------------
    {
        "id": "item-057",
        "name": "Borosilicate Glass Meal Prep Containers",
        "category": "Food Storage & Organization",
        "subcategory": "Food Containers",
        "description": "Pack of 4 airtight oven-safe borosilicate glass containers with four-latch leakproof BPA-free locking lids.",
        "reference_price_cents": 3600,   # $36.00
        "cogs_cents": 1500,              # $15.00 (58.3% base margin)
        "inventory": 55,
        "complementary_ids": "item-058,item-059,item-062,item-039",
        "tags": "glass-containers,meal-prep,leakproof,airtight,oven-safe,bpa-free",
        "use_cases": "wellness,cooking,pantry,productivity",
        "image_url": "https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-058",
        "name": "Reusable Platinum Silicone Food Storage Bags",
        "category": "Food Storage & Organization",
        "subcategory": "Food Bags",
        "description": "Set of 4 dishwasher and freezer safe pinch-loc hermetic seal pure platinum silicone reusable sandwich bags.",
        "reference_price_cents": 2600,   # $26.00
        "cogs_cents": 1000,              # $10.00 (61.5% base margin)
        "inventory": 65,
        "complementary_ids": "item-057,item-060,item-062",
        "tags": "silicone-bags,reusable,zero-waste,leakproof,freezer-safe,snack-bags",
        "use_cases": "wellness,travel,pantry",
        "image_url": "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-059",
        "name": "Clear Stackable Pantry Storage Bins",
        "category": "Food Storage & Organization",
        "subcategory": "Pantry Organization",
        "description": "Set of 3 shatter-resistant clear acrylic organizer bins with integrated open-front access and built-in carry handles.",
        "reference_price_cents": 2400,   # $24.00
        "cogs_cents": 950,               # $9.50 (60.4% base margin)
        "inventory": 60,
        "complementary_ids": "item-057,item-062,item-063,item-064",
        "tags": "pantry-bins,storage-bins,stackable,acrylic,organization,pantry",
        "use_cases": "pantry,kitchen,wellness",
        "image_url": "https://images.unsplash.com/photo-1584269600519-112d071b35e6?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-060",
        "name": "Reusable Beeswax Food Wrap Assortment",
        "category": "Food Storage & Organization",
        "subcategory": "Food Wraps",
        "description": "Pack of 3 sustainable organic cotton food wraps infused with beeswax, jojoba oil, and tree resin for cheese and bread.",
        "reference_price_cents": 1500,   # $15.00
        "cogs_cents": 550,               # $5.50 (63.3% base margin)
        "inventory": 70,
        "complementary_ids": "item-036,item-057,item-058",
        "tags": "beeswax-wrap,eco-friendly,zero-waste,organic,food-storage",
        "use_cases": "wellness,pantry,kitchen",
        "image_url": "https://images.unsplash.com/photo-1610557892470-55d9e80c0bce?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-061",
        "name": "Vacuum Sealed Stainless Steel Food Jar",
        "category": "Food Storage & Organization",
        "subcategory": "Thermal Jars",
        "description": "Double-wall vacuum insulated 16oz wide-mouth thermos food container keeping meals piping hot for 9 hours.",
        "reference_price_cents": 2800,   # $28.00
        "cogs_cents": 1200,              # $12.00 (57.1% base margin)
        "inventory": 45,
        "complementary_ids": "item-027,item-057,item-058",
        "tags": "food-jar,thermos,insulated,vacuum-sealed,lunch-box,portable",
        "use_cases": "travel,study,productivity",
        "image_url": "https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-062",
        "name": "Waterproof Chalkboard Pantry Labels",
        "category": "Food Storage & Organization",
        "subcategory": "Organization Accessories",
        "description": "96 reusable vinyl peel-and-stick chalkboard labels with fine-tip dustless liquid chalk marker.",
        "reference_price_cents": 800,    # $8.00
        "cogs_cents": 280,               # $2.80 (65.0% base margin)
        "inventory": 85,
        "complementary_ids": "item-057,item-059,item-063",
        "tags": "labels,pantry-labels,chalkboard,reusable,organization,stickers",
        "use_cases": "pantry,kitchen,wellness",
        "image_url": "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-063",
        "name": "Airtight Cereal & Dry Grain Dispenser",
        "category": "Food Storage & Organization",
        "subcategory": "Pantry Organization",
        "description": "2.5-liter modular clear grain dispenser with silicone hermetic seal lid and one-handed easy-pour spout.",
        "reference_price_cents": 2100,   # $21.00
        "cogs_cents": 850,               # $8.50 (59.5% base margin)
        "inventory": 50,
        "complementary_ids": "item-039,item-059,item-062",
        "tags": "dispenser,cereal-container,dry-food,airtight,pantry-storage",
        "use_cases": "pantry,wellness,kitchen",
        "image_url": "https://images.unsplash.com/photo-1584269600519-112d071b35e6?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-064",
        "name": "Expandable Bamboo Drawer Spice Rack",
        "category": "Food Storage & Organization",
        "subcategory": "Pantry Organization",
        "description": "3-tier tilted bamboo organizer rack expanding from 12 to 24 inches for standard kitchen spice jars.",
        "reference_price_cents": 2500,   # $25.00
        "cogs_cents": 1050,              # $10.50 (58.0% base margin)
        "inventory": 45,
        "complementary_ids": "item-051,item-059,item-062",
        "tags": "spice-rack,bamboo,expandable,drawer-organizer,kitchen-storage",
        "use_cases": "kitchen,pantry",
        "image_url": "https://images.unsplash.com/photo-1590794056470-36e67610029b?auto=format&fit=crop&w=600&q=80"
    },
    # -------------------------------------------------------------------------
    # HOME & CLEANING (item-065 to item-072)
    # -------------------------------------------------------------------------
    {
        "id": "item-065",
        "name": "Concentrated Multi-Surface Eco Cleaner",
        "category": "Home & Cleaning",
        "subcategory": "Cleaners",
        "description": "Plant-based citrus vinegar concentrated surface spray in an amber apothecary glass spray bottle (16oz).",
        "reference_price_cents": 1800,   # $18.00
        "cogs_cents": 650,               # $6.50 (63.9% base margin)
        "inventory": 60,
        "complementary_ids": "item-066,item-067,item-072",
        "tags": "cleaner,multi-surface,eco-friendly,glass-bottle,non-toxic,cleaning",
        "use_cases": "home_care,wellness,kitchen",
        "image_url": "https://images.unsplash.com/photo-1585421514738-01798e348b17?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-066",
        "name": "Ultra-Absorbent Waffle Microfiber Cloths",
        "category": "Home & Cleaning",
        "subcategory": "Cleaning Tools",
        "description": "Pack of 6 lint-free dual-texture 400gsm microfiber cleaning towels for streak-free glass and countertop care.",
        "reference_price_cents": 1400,   # $14.00
        "cogs_cents": 480,               # $4.80 (65.7% base margin)
        "inventory": 80,
        "complementary_ids": "item-065,item-067,item-068",
        "tags": "microfiber,cleaning-cloths,streak-free,absorbent,lint-free",
        "use_cases": "home_care,wellness,kitchen",
        "image_url": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-067",
        "name": "Plant-Based Foaming Dish Soap & Dispenser",
        "category": "Home & Cleaning",
        "subcategory": "Dish Care",
        "description": "Biodegradable lemon verbena foaming dish soap with refillable matte ceramic countertop pump (16oz).",
        "reference_price_cents": 1650,   # $16.50
        "cogs_cents": 600,               # $6.00 (63.6% base margin)
        "inventory": 65,
        "complementary_ids": "item-068,item-066,item-072,item-049",
        "tags": "dish-soap,foaming,ceramic-dispenser,biodegradable,eco-friendly",
        "use_cases": "home_care,kitchen,wellness",
        "image_url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-068",
        "name": "Natural Sisal & Beechwood Dish Scrub Brush",
        "category": "Home & Cleaning",
        "subcategory": "Dish Care",
        "description": "Pair of ergonomic natural beechwood dish brushes with sturdy compostable sisal and palm fiber bristles.",
        "reference_price_cents": 1100,   # $11.00
        "cogs_cents": 380,               # $3.80 (65.5% base margin)
        "inventory": 75,
        "complementary_ids": "item-067,item-049,item-051,item-072",
        "tags": "scrub-brush,dish-brush,beechwood,sisal,plastic-free,compostable",
        "use_cases": "home_care,kitchen,wellness",
        "image_url": "https://images.unsplash.com/photo-1585421514738-01798e348b17?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-069",
        "name": "Organic Lavender Essential Oil Room Spray",
        "category": "Home & Cleaning",
        "subcategory": "Aromatherapy & Air Care",
        "description": "Calming linen and ambient mist distilled from organic French lavender flowers with zero artificial fragrances (8oz).",
        "reference_price_cents": 1500,   # $15.00
        "cogs_cents": 520,               # $5.20 (65.3% base margin)
        "inventory": 50,
        "complementary_ids": "item-077,item-080,item-065",
        "tags": "room-spray,lavender,essential-oil,calming,aromatherapy,linen-mist",
        "use_cases": "home_care,wellness,study",
        "image_url": "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-070",
        "name": "Organic Wool Dryer Balls Set",
        "category": "Home & Cleaning",
        "subcategory": "Laundry Care",
        "description": "Set of 6 pure New Zealand wool dryer balls that naturally soften laundry and reduce tumble drying time by 25%.",
        "reference_price_cents": 1350,   # $13.50
        "cogs_cents": 450,               # $4.50 (66.7% base margin)
        "inventory": 70,
        "complementary_ids": "item-069,item-065",
        "tags": "dryer-balls,wool,laundry,natural-softener,energy-saving",
        "use_cases": "home_care,wellness",
        "image_url": "https://images.unsplash.com/photo-1582735689369-4fe89db7114c?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-071",
        "name": "Countertop Stainless Steel Compost Caddy",
        "category": "Home & Cleaning",
        "subcategory": "Waste Management",
        "description": "1-gallon brushed stainless steel food scrap compost bin with integrated activated charcoal odor filter lid.",
        "reference_price_cents": 2900,   # $29.00
        "cogs_cents": 1200,              # $12.00 (58.6% base margin)
        "inventory": 40,
        "complementary_ids": "item-051,item-067,item-068",
        "tags": "compost-bin,countertop,stainless-steel,odor-filter,food-waste",
        "use_cases": "home_care,kitchen,wellness",
        "image_url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-072",
        "name": "Biodegradable Swedish Cellulose Sponges",
        "category": "Home & Cleaning",
        "subcategory": "Cleaning Tools",
        "description": "Pack of 5 reusable Swedish dishcloths made from natural wood pulp and cotton, absorbing 20x their weight.",
        "reference_price_cents": 900,    # $9.00
        "cogs_cents": 300,               # $3.00 (66.7% base margin)
        "inventory": 85,
        "complementary_ids": "item-067,item-065,item-068",
        "tags": "sponge-cloths,swedish-dishcloths,cellulose,biodegradable,eco-cleaning",
        "use_cases": "home_care,kitchen,wellness",
        "image_url": "https://images.unsplash.com/photo-1585421514738-01798e348b17?auto=format&fit=crop&w=600&q=80"
    },
    # -------------------------------------------------------------------------
    # PERSONAL CARE (item-073 to item-080)
    # -------------------------------------------------------------------------
    {
        "id": "item-073",
        "name": "Botanical Shea Butter Intensive Hand Cream",
        "category": "Personal Care",
        "subcategory": "Skin Care",
        "description": "Fast-absorbing non-greasy restorative hand balm formulated with 20% organic shea butter and chamomile (75ml).",
        "reference_price_cents": 1400,   # $14.00
        "cogs_cents": 480,               # $4.80 (65.7% base margin)
        "inventory": 70,
        "complementary_ids": "item-074,item-075,item-002",
        "tags": "hand-cream,shea-butter,skincare,moisturizing,non-greasy,wellness",
        "use_cases": "personal_care,wellness,productivity,study",
        "image_url": "https://images.unsplash.com/photo-1608248597359-e931e9c20a81?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-074",
        "name": "Nourishing Beeswax & Peppermint Lip Balm",
        "category": "Personal Care",
        "subcategory": "Lip Care",
        "description": "Trio of soothing lip balms crafted from natural beeswax, cold-pressed almond oil, and refreshing field peppermint.",
        "reference_price_cents": 1000,   # $10.00
        "cogs_cents": 320,               # $3.20 (68.0% base margin)
        "inventory": 85,
        "complementary_ids": "item-073,item-075,item-020",
        "tags": "lip-balm,beeswax,peppermint,soothing,natural,hydration",
        "use_cases": "personal_care,wellness,travel,productivity",
        "image_url": "https://images.unsplash.com/photo-1586495777744-4413f21062fa?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-075",
        "name": "Preservative-Free Lubricating Eye Drops",
        "category": "Personal Care",
        "subcategory": "Eye Care",
        "description": "30 single-use sterile vials of electrolyte-balanced lubricating drops formulated to relieve digital screen dry eyes.",
        "reference_price_cents": 1600,   # $16.00
        "cogs_cents": 650,               # $6.50 (59.4% base margin)
        "inventory": 60,
        "complementary_ids": "item-007,item-073,item-080",
        "tags": "eye-drops,screen-fatigue,preservative-free,lubricating,digital-wellness",
        "use_cases": "personal_care,productivity,study,gaming,wellness",
        "image_url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-076",
        "name": "Natural Jade Stone Facial Roller & Gua Sha",
        "category": "Personal Care",
        "subcategory": "Self Care Tools",
        "description": "Authentic Xiuyan green jade facial roller and contoured sculpting gua sha stone for cooling lymphatic drainage.",
        "reference_price_cents": 1900,   # $19.00
        "cogs_cents": 700,               # $7.00 (63.2% base margin)
        "inventory": 45,
        "complementary_ids": "item-073,item-077,item-080",
        "tags": "jade-roller,gua-sha,facial-tool,lymphatic,self-care,cooling",
        "use_cases": "personal_care,wellness",
        "image_url": "https://images.unsplash.com/photo-1598440947619-2c35fc9aa908?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-077",
        "name": "Epsom & Himalayan Mineral Bath Soak",
        "category": "Personal Care",
        "subcategory": "Bath & Body",
        "description": "Pure magnesium sulfate Epsom crystal salts blended with pink Himalayan rock salt and eucalyptus essential oil (32oz).",
        "reference_price_cents": 1500,   # $15.00
        "cogs_cents": 550,               # $5.50 (63.3% base margin)
        "inventory": 50,
        "complementary_ids": "item-069,item-076,item-078",
        "tags": "bath-salts,epsom-salt,himalayan,magnesium,muscle-relief,recovery",
        "use_cases": "personal_care,wellness",
        "image_url": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-078",
        "name": "Natural Bristle Dry Body Brush",
        "category": "Personal Care",
        "subcategory": "Self Care Tools",
        "description": "Polished FSC lotus wood body brush with firm natural boar bristles and cotton hand strap for dry body exfoliation.",
        "reference_price_cents": 1350,   # $13.50
        "cogs_cents": 450,               # $4.50 (66.7% base margin)
        "inventory": 55,
        "complementary_ids": "item-077,item-073",
        "tags": "body-brush,dry-brush,exfoliation,lotus-wood,natural-bristles",
        "use_cases": "personal_care,wellness",
        "image_url": "https://images.unsplash.com/photo-1519735777090-ec97162dc266?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-079",
        "name": "Organic Peppermint Herbal Tea Bags",
        "category": "Personal Care",
        "subcategory": "Herbal Teas",
        "description": "Caffeine-free soothing whole-leaf Pacific Northwest peppermint tea bags for evening relaxation (24 count box).",
        "reference_price_cents": 850,    # $8.50
        "cogs_cents": 300,               # $3.00 (64.7% base margin)
        "inventory": 80,
        "complementary_ids": "item-038,item-080,item-027",
        "tags": "peppermint-tea,herbal-tea,caffeine-free,relaxation,digestive",
        "use_cases": "personal_care,wellness,study,productivity",
        "image_url": "https://images.unsplash.com/photo-1597481499750-3e6b22637e12?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-080",
        "name": "100% Pure Mulberry Silk Sleep Mask",
        "category": "Personal Care",
        "subcategory": "Sleep Essentials",
        "description": "Ultra-soft 22 momme grade 6A pure mulberry silk eye contour mask with adjustable headband for complete blackout sleep.",
        "reference_price_cents": 2200,   # $22.00
        "cogs_cents": 850,               # $8.50 (61.4% base margin)
        "inventory": 60,
        "complementary_ids": "item-069,item-075,item-079",
        "tags": "silk-mask,eye-mask,sleep,blackout,mulberry-silk,relaxation",
        "use_cases": "personal_care,wellness,travel",
        "image_url": "https://images.unsplash.com/photo-1584100936595-c0654b55a2e2?auto=format&fit=crop&w=600&q=80"
    },
    # -------------------------------------------------------------------------
    # HOME OFFICE (item-081 to item-088)
    # -------------------------------------------------------------------------
    {
        "id": "item-081",
        "name": "Under-Desk Metal Cable Management Tray",
        "category": "Home Office",
        "subcategory": "Cable Management",
        "description": "Heavy-duty steel wire mesh raceway tray that mounts beneath any desk to conceal power strips and surge protectors.",
        "reference_price_cents": 2700,   # $27.00
        "cogs_cents": 1050,              # $10.50 (61.1% base margin)
        "inventory": 50,
        "complementary_ids": "item-016,item-086,item-010",
        "tags": "cable-tray,under-desk,cable-management,steel,desk-organization",
        "use_cases": "productivity,gaming,home_office",
        "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-082",
        "name": "Gas-Spring Single Monitor Desk Mount Arm",
        "category": "Home Office",
        "subcategory": "Monitor Mounts",
        "description": "Full-motion counterbalanced mechanical arm supporting displays up to 32 inches and 19.8 lbs with VESA 75/100 bracket.",
        "reference_price_cents": 4800,   # $48.00
        "cogs_cents": 2100,              # $21.00 (56.3% base margin)
        "inventory": 40,
        "complementary_ids": "item-005,item-007,item-081",
        "tags": "monitor-arm,vesa-mount,gas-spring,ergonomic,desk-clearance",
        "use_cases": "productivity,gaming,wellness,home_office",
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-083",
        "name": "Non-Slip Chair Mat for Hardwood Floors",
        "category": "Home Office",
        "subcategory": "Floor Protection",
        "description": "High-impact non-curling transparent polycarbonate protector mat (36x48 inches) designed for smooth caster rolling.",
        "reference_price_cents": 3800,   # $38.00
        "cogs_cents": 1600,              # $16.00 (57.9% base margin)
        "inventory": 35,
        "complementary_ids": "item-030,item-013,item-004",
        "tags": "chair-mat,floor-protector,hardwood,polycarbonate,desk-chair",
        "use_cases": "productivity,wellness,home_office",
        "image_url": "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-084",
        "name": "Dimmable LED Architect Desk Lamp",
        "category": "Home Office",
        "subcategory": "Task Lighting",
        "description": "Multi-jointed cantilever clamp-on swing arm task lamp with 5 color temperatures, touch dimmer, and 24W output.",
        "reference_price_cents": 4200,   # $42.00
        "cogs_cents": 1850,              # $18.50 (56.0% base margin)
        "inventory": 45,
        "complementary_ids": "item-007,item-041,item-048",
        "tags": "architect-lamp,swing-arm,led-lamp,clamp-on,task-lighting,drafting",
        "use_cases": "study,productivity,home_office",
        "image_url": "https://images.unsplash.com/photo-1534349762230-e0cadf78f5da?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-085",
        "name": "Compact Desktop Dry Erase Glass Whiteboard",
        "category": "Home Office",
        "subcategory": "Desk Accessories",
        "description": "Angled tempered glass memo board with internal storage drawer that fits directly between keyboard and monitor.",
        "reference_price_cents": 2500,   # $25.00
        "cogs_cents": 1000,              # $10.00 (60.0% base margin)
        "inventory": 50,
        "complementary_ids": "item-001,item-042,item-045",
        "tags": "whiteboard,glass-easel,memo-board,dry-erase,desk-storage",
        "use_cases": "productivity,study,home_office",
        "image_url": "https://images.unsplash.com/photo-1517842645767-c639042777db?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-086",
        "name": "Reusable Neoprene Zipper Cable Sleeves",
        "category": "Home Office",
        "subcategory": "Cable Management",
        "description": "Pack of 4 flexible 20-inch neoprene zippered cable wrap tubes designed to consolidate up to 10 messy peripheral cords.",
        "reference_price_cents": 1450,   # $14.50
        "cogs_cents": 500,               # $5.00 (65.5% base margin)
        "inventory": 70,
        "complementary_ids": "item-081,item-010,item-017",
        "tags": "cable-sleeve,neoprene,zipper,cable-tidy,wire-organizer",
        "use_cases": "productivity,gaming,home_office",
        "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-087",
        "name": "Solid Wood Headphone Desk Display Stand",
        "category": "Home Office",
        "subcategory": "Audio Accessories",
        "description": "Sculpted solid black walnut omega-arch headphone cradle designed to preserve headband cushion contours.",
        "reference_price_cents": 2800,   # $28.00
        "cogs_cents": 1150,              # $11.50 (58.9% base margin)
        "inventory": 40,
        "complementary_ids": "item-024,item-015,item-004",
        "tags": "headphone-stand,walnut,wood,audio-stand,desk-accessory",
        "use_cases": "productivity,gaming,entertainment,home_office",
        "image_url": "https://images.unsplash.com/photo-1545454675-3531b543be5d?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-088",
        "name": "Acoustic Privacy Felt Desk Divider",
        "category": "Home Office",
        "subcategory": "Desk Partitions",
        "description": "Clamp-on 24x16 inch sound-dampening recycled PET acoustic felt modesty panel that reduces visual distractions.",
        "reference_price_cents": 3600,   # $36.00
        "cogs_cents": 1500,              # $15.00 (58.3% base margin)
        "inventory": 35,
        "complementary_ids": "item-009,item-025,item-082",
        "tags": "privacy-panel,acoustic-felt,desk-divider,sound-absorption,modesty-screen",
        "use_cases": "productivity,study,home_office",
        "image_url": "https://images.unsplash.com/photo-1497215842964-222b430dc094?auto=format&fit=crop&w=600&q=80"
    },
    # -------------------------------------------------------------------------
    # ELECTRONICS & GADGETS (item-089 to item-096)
    # -------------------------------------------------------------------------
    {
        "id": "item-089",
        "name": "Portable 10,000mAh Magnetic Power Bank",
        "category": "Electronics & Gadgets",
        "subcategory": "Portable Power",
        "description": "Slim wireless external battery with MagSafe magnetic snap alignment, 20W USB-C PD fast charging, and kickstand.",
        "reference_price_cents": 4200,   # $42.00
        "cogs_cents": 1800,              # $18.00 (57.1% base margin)
        "inventory": 50,
        "complementary_ids": "item-016,item-017,item-094",
        "tags": "power-bank,magsafe,wireless-charging,battery-pack,usb-c,travel",
        "use_cases": "travel,productivity",
        "image_url": "https://images.unsplash.com/photo-1609592424855-6c701469e34e?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-090",
        "name": "USB-C to 4K 60Hz HDMI Aluminum Cable",
        "category": "Electronics & Gadgets",
        "subcategory": "Cables & Adapters",
        "description": "6-foot nylon braided direct video adapter cable connecting USB-C/Thunderbolt laptops to external 4K monitors.",
        "reference_price_cents": 1800,   # $18.00
        "cogs_cents": 650,               # $6.50 (63.9% base margin)
        "inventory": 65,
        "complementary_ids": "item-018,item-008,item-082",
        "tags": "usb-c-hdmi,4k-60hz,display-cable,braided,aluminum,video-cable",
        "use_cases": "productivity,gaming,study,home_office",
        "image_url": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-091",
        "name": "Smart Wi-Fi Energy Monitoring Mini Plug (2-Pack)",
        "category": "Electronics & Gadgets",
        "subcategory": "Smart Home",
        "description": "Compact 15A smart electrical outlets with real-time kilowatt-hour power consumption metering and scheduling.",
        "reference_price_cents": 2200,   # $22.00
        "cogs_cents": 850,               # $8.50 (61.4% base margin)
        "inventory": 55,
        "complementary_ids": "item-016,item-081,item-084",
        "tags": "smart-plug,wifi,energy-meter,home-automation,timer",
        "use_cases": "productivity,home_office",
        "image_url": "https://images.unsplash.com/photo-1558002038-1055907df827?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-092",
        "name": "Compact Electronic Screen Cleaner Kit",
        "category": "Electronics & Gadgets",
        "subcategory": "Maintenance",
        "description": "Refillable alcohol-free screen mist bottle integrated into an all-in-one microfiber wipe body for phones and monitors.",
        "reference_price_cents": 1150,   # $11.50
        "cogs_cents": 400,               # $4.00 (65.2% base margin)
        "inventory": 80,
        "complementary_ids": "item-007,item-004,item-066",
        "tags": "screen-cleaner,microfiber,anti-static,screen-spray,lens-cleaner",
        "use_cases": "productivity,study,travel",
        "image_url": "https://images.unsplash.com/photo-1585421514738-01798e348b17?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-093",
        "name": "Braided Right-Angle USB-C Cable (10ft)",
        "category": "Electronics & Gadgets",
        "subcategory": "Cables & Adapters",
        "description": "Extra-long 10ft heavy-duty braided 60W charge cable with ergonomic 90-degree L-shaped connector for tight spaces.",
        "reference_price_cents": 1600,   # $16.00
        "cogs_cents": 550,               # $5.50 (65.6% base margin)
        "inventory": 70,
        "complementary_ids": "item-016,item-089,item-017",
        "tags": "usb-c-cable,right-angle,10ft,long-cable,braided,charging",
        "use_cases": "productivity,travel,gaming",
        "image_url": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-094",
        "name": "3-in-1 Foldable Travel Wireless Charger",
        "category": "Electronics & Gadgets",
        "subcategory": "Charging Docks",
        "description": "Folding silicone MagSafe travel pad charging phone, smartwatch, and wireless earbuds simultaneously from one cable.",
        "reference_price_cents": 3900,   # $39.00
        "cogs_cents": 1650,              # $16.50 (57.7% base margin)
        "inventory": 45,
        "complementary_ids": "item-016,item-089,item-020",
        "tags": "travel-charger,wireless-charger,3-in-1,magsafe,foldable",
        "use_cases": "travel,productivity,wellness",
        "image_url": "https://images.unsplash.com/photo-1586953208448-b95a79798f07?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-095",
        "name": "Ultra-Slim Bluetooth Numeric Keypad",
        "category": "Electronics & Gadgets",
        "subcategory": "Computer Peripherals",
        "description": "Rechargeable 34-key brushed aluminum numeric keypad with scissor switches for accounting, spreadsheets, and data entry.",
        "reference_price_cents": 2600,   # $26.00
        "cogs_cents": 1050,              # $10.50 (59.6% base margin)
        "inventory": 50,
        "complementary_ids": "item-001,item-003,item-004",
        "tags": "numeric-keypad,numpad,bluetooth,accounting,data-entry,aluminum",
        "use_cases": "productivity,study,home_office",
        "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=600&q=80"
    },
    {
        "id": "item-096",
        "name": "Anti-Static Electronics Precision Screwdriver Set",
        "category": "Electronics & Gadgets",
        "subcategory": "Tools & Repair",
        "description": "24 magnetic S2 alloy steel precision driver bits with aluminum handle and push-to-open sliding storage case.",
        "reference_price_cents": 2100,   # $21.00
        "cogs_cents": 800,               # $8.00 (61.9% base margin)
        "inventory": 55,
        "complementary_ids": "item-011,item-012,item-081",
        "tags": "screwdriver-set,precision-tools,electronics-repair,magnetic-bits,aluminum-case",
        "use_cases": "productivity,gaming,home_office",
        "image_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=600&q=80"
    }
]

def seed_catalog(db_path: str | None = None) -> int:
    """Seeds the 96 products into SQLite database deterministically using INSERT OR REPLACE."""
    target_db = db_path or settings.DATABASE_PATH
    init_db(target_db)
    inserted_count = 0
    conn = get_connection(db_path=target_db, database_url="")
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

    # Invalidate in-process catalog cache so changes take effect immediately
    CatalogRepository.invalidate_cache()
    return inserted_count

if __name__ == "__main__":
    count = seed_catalog()
    print(f"Catalog successfully seeded with {count} verified products.")
