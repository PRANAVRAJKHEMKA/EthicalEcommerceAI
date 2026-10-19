"""FairCart AI — Decision Twin Inventory & Available-To-Promise (ATP) Engine

Maintains accurate Available-To-Promise (ATP) inventory levels,
computes dynamic scarcity shadow prices (lambda_i), generates auditable
stockout/excess inventory alerts, and ensures thread-safe allocation accounting.
"""

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

from backend.app.db.database import get_connection
from backend.app.models.decision_twin_schemas import (
    InventoryAlert,
    InventoryItem,
)

logger = logging.getLogger("faircart.twin.inventory")

# Deterministic realistic inventory profile configuration for catalog products
# E.g. high-demand mechanical keyboard has scarce stock, whereas cable is abundant
DEFAULT_INVENTORY_PROFILES = {
    # Scarce / High-demand hardware items
    "item-001": {"on_hand": 12, "reserved": 2, "safety_stock": 10, "incoming": 25, "lead_time_days": 14},  # Ergonomic Mechanical Keyboard
    "item-003": {"on_hand": 18, "reserved": 3, "safety_stock": 12, "incoming": 30, "lead_time_days": 10},  # Precision Vertical Wireless Mouse
    "item-005": {"on_hand": 8, "reserved": 2, "safety_stock": 8, "incoming": 15, "lead_time_days": 21},   # Ultrawide Curved Monitor 34"
    "item-011": {"on_hand": 14, "reserved": 4, "safety_stock": 12, "incoming": 20, "lead_time_days": 14}, # Active Noise-Cancelling Headphones
    "item-015": {"on_hand": 9, "reserved": 1, "safety_stock": 10, "incoming": 15, "lead_time_days": 18},  # 4K USB-C Streaming Webcam
    # Balanced accessories & office items
    "item-002": {"on_hand": 85, "reserved": 5, "safety_stock": 15, "incoming": 50, "lead_time_days": 7},  # Padded Memory Foam Wrist Rest
    "item-004": {"on_hand": 110, "reserved": 10, "safety_stock": 20, "incoming": 60, "lead_time_days": 5}, # Large Desk Mat (Water-Resistant)
    "item-006": {"on_hand": 45, "reserved": 5, "safety_stock": 15, "incoming": 30, "lead_time_days": 7},  # Aluminum Dual-Arm Monitor Stand
    "item-007": {"on_hand": 65, "reserved": 6, "safety_stock": 15, "incoming": 40, "lead_time_days": 7},  # 8-in-1 USB-C PD Docking Station
    "item-008": {"on_hand": 140, "reserved": 12, "safety_stock": 25, "incoming": 80, "lead_time_days": 4}, # Braided USB-C to USB-C Cable (6.6ft)
    "item-012": {"on_hand": 55, "reserved": 5, "safety_stock": 15, "incoming": 35, "lead_time_days": 7},  # Aluminum Headphone Stand
    "item-016": {"on_hand": 70, "reserved": 4, "safety_stock": 15, "incoming": 40, "lead_time_days": 7},  # Clip-On LED Ring Light
}


def calculate_atp(on_hand: int, reserved: int) -> int:
    """Computes Available-To-Promise (ATP) inventory.

    ATP = max(0, on_hand - reserved)
    """
    return max(0, on_hand - reserved)


def determine_stock_status(atp: int, safety_stock: int, demand_forecast_14d: float = 14.0) -> str:
    """Classifies inventory into auditable operational tiers."""
    if atp <= 0:
        return "OUT_OF_STOCK"
    if atp <= max(2, int(safety_stock * 0.5)):
        return "CRITICAL_STOCKOUT_RISK"
    if atp <= safety_stock:
        return "LOW_STOCK"
    if atp > max(50, int(demand_forecast_14d * 3.0)):
        return "OVERSTOCKED"
    return "HEALTHY"


def calculate_scarcity_lambda(
    reference_price: float,
    cogs: float,
    atp: int,
    safety_stock: int,
    forecast_demand_14d: float | None = None,
    max_multiplier: float = 1.0,
) -> float:
    """Computes the inventory scarcity shadow price (lambda_i) in USD per unit.

    Units: USD ($) per unit of inventory allocated to a promotional incentive.

    Economic Model:
      lambda_i represents the expected opportunity cost of sacrificing an organic,
      full-reference-price customer sale by allocating constrained warehouse inventory
      to a discounted promotional offer.

      Bounded by: [0.0, (reference_price - cogs) * max_multiplier]
      By default (max_multiplier=1.0), the opportunity cost of 1 unit cannot exceed
      the full unit gross profit of an organic full-margin sale ($r_{s,0} - c_i$).

    Formula:
      effective_forecast:
        - If forecast_demand_14d is None: applies conservative safe fallback
          effective_forecast = max(14.0, safety_stock * 1.5)
        - If forecast_demand_14d <= 0.0: genuine zero organic demand -> lambda_i = 0.0
        - Otherwise: effective_forecast = float(forecast_demand_14d)

      threshold:
        T_i = max(effective_forecast, safety_stock * 1.5, 1.0)

      When atp > T_i:
        lambda_i = 0.0 (inventory is abundant; zero opportunity cost)

      When atp <= 0:
        lambda_i = unit_margin * max_multiplier (inventory depleted; full opportunity cost)

      When 0 < atp <= T_i:
        demand_pressure = max(0.0, effective_forecast / max(1.0, atp))
        scarcity_factor = max(0.0, 1.0 - (atp / T_i))
        lambda_i = unit_margin * max(0.0, min(max_multiplier, demand_pressure * scarcity_factor))

    Edge Case Invariants:
      1. atp <= 0: Inventory depleted; lambda_i = unit_margin * max_multiplier if forecast > 0.
      2. forecast_demand_14d is None: Safe fallback (>= 14.0 units) protects constrained stock under uncertainty.
      3. forecast_demand_14d <= 0.0: Genuine zero organic demand yields lambda_i = 0.0.
      4. safety_stock <= 0: T_i = max(effective_forecast, 1.0). If atp > T_i, lambda = 0; if atp <= T_i, scarcity penalty applies.
      5. reference_price <= cogs: Negative/zero unit margin yields lambda_i = 0.0.
      6. Unusually large demand: Cleanly saturated at unit_margin * max_multiplier without overflow.
    """
    unit_margin = max(0.0, float(reference_price) - float(cogs))
    if unit_margin <= 0.0:
        return 0.0

    clean_safety = max(0.0, float(safety_stock))

    # Forecast resolution: differentiate missing forecast from genuine zero demand
    if forecast_demand_14d is None:
        # Safe fallback: at least 14 units (1 unit/day) or 1.5x safety stock
        forecast = max(14.0, clean_safety * 1.5)
    else:
        forecast = float(forecast_demand_14d)
        if forecast <= 0.0:
            # Genuine zero demand: zero opportunity cost
            return 0.0

    clean_atp = float(atp)
    threshold = max(forecast, clean_safety * 1.5, 1.0)

    # Abundant stock regime: zero shadow cost
    if clean_atp > threshold:
        return 0.0

    # Depleted or backordered stock regime: maximum unit margin penalty
    if clean_atp <= 0.0:
        return round(unit_margin * max_multiplier, 2)

    # Constrained stock regime: smooth proportional opportunity cost
    demand_pressure = max(0.0, forecast / max(1.0, clean_atp))
    scarcity_factor = max(0.0, 1.0 - (clean_atp / threshold))

    raw_lambda = unit_margin * max(0.0, min(max_multiplier, demand_pressure * scarcity_factor))
    return round(float(raw_lambda), 2)


class TwinInventoryRepository:
    """Data access and operational logic for Decision Twin inventory and ATP."""

    def __init__(self, db_path: str | None = None, database_url: str | None = None):
        self.db_path = db_path
        self.database_url = database_url

    def _get_connection(self):
        return get_connection(self.db_path, self.database_url)

    def seed_initial_inventory(self, storefront_id: str = "primary_storefront") -> int:
        """Seeds realistic inventory levels for all catalog products if sku_inventory is unseeded."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM sku_inventory WHERE storefront_id = ?", (storefront_id,))
            row = cursor.fetchone()
            count = row["cnt"] if row else 0
            if count > 0:
                return count

            # Fetch catalog products
            cursor.execute("SELECT id, name, category, reference_price_cents, cogs_cents, inventory FROM products")
            products = cursor.fetchall()

            now_iso = datetime.now(timezone.utc).isoformat()
            seeded = 0

            for p in products:
                sku = p["id"]
                ref_cents = int(p["reference_price_cents"])

                # Check predefined profile or derive realistic defaults
                if sku in DEFAULT_INVENTORY_PROFILES:
                    prof = DEFAULT_INVENTORY_PROFILES[sku]
                    on_hand = prof["on_hand"]
                    reserved = prof["reserved"]
                    safety = prof["safety_stock"]
                    incoming = prof["incoming"]
                    lead_days = prof["lead_time_days"]
                else:
                    # High-value items have smaller stock, low-cost have abundant stock
                    if ref_cents >= 10000:  # >= $100
                        on_hand = 15
                        reserved = 2
                        safety = 10
                        incoming = 20
                        lead_days = 14
                    elif ref_cents >= 4000:  # $40 - $100
                        on_hand = 35
                        reserved = 4
                        safety = 12
                        incoming = 35
                        lead_days = 10
                    else:  # Under $40
                        on_hand = 90
                        reserved = 6
                        safety = 20
                        incoming = 60
                        lead_days = 7

                cursor.execute("""
                    INSERT OR REPLACE INTO sku_inventory (
                        sku, storefront_id, on_hand, reserved, safety_stock, incoming, lead_time_days, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (sku, storefront_id, on_hand, reserved, safety, incoming, lead_days, now_iso))
                seeded += 1

            conn.commit()
            return seeded
        finally:
            conn.close()

    def get_inventory_item(self, sku: str, storefront_id: str = "primary_storefront") -> InventoryItem | None:
        """Fetches the current inventory snapshot and computed ATP for a SKU."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.*, p.name as product_name, p.category, p.reference_price_cents, p.cogs_cents
                FROM sku_inventory i
                JOIN products p ON i.sku = p.id
                WHERE i.sku = ? AND i.storefront_id = ?
            """, (sku, storefront_id))
            row = cursor.fetchone()
            if not row:
                return None

            on_hand = int(row["on_hand"])
            reserved = int(row["reserved"])
            safety = int(row["safety_stock"])
            incoming = int(row["incoming"])
            lead_days = int(row["lead_time_days"])
            atp = calculate_atp(on_hand, reserved)

            ref_price = round(int(row["reference_price_cents"]) / 100.0, 2)
            cogs = round(int(row["cogs_cents"]) / 100.0, 2)

            # Query point forecast from demand_forecasts if available, else None (safe fallback)
            fc_point: float | None = None
            try:
                cursor.execute("""
                    SELECT point_forecast FROM demand_forecasts
                    WHERE sku = ? AND storefront_id = ? AND horizon_days = 14
                    ORDER BY created_at DESC LIMIT 1
                """, (sku, storefront_id))
                fc_row = cursor.fetchone()
                if fc_row and fc_row["point_forecast"] is not None:
                    fc_point = float(fc_row["point_forecast"])
            except Exception:
                fc_point = None

            scarcity_lambda = calculate_scarcity_lambda(ref_price, cogs, atp, safety, fc_point)
            status = determine_stock_status(atp, safety, fc_point if fc_point is not None else max(14.0, float(safety * 1.5)))

            return InventoryItem(
                sku=sku,
                product_name=row["product_name"],
                category=row["category"],
                storefront_id=storefront_id,
                on_hand=on_hand,
                reserved=reserved,
                safety_stock=safety,
                incoming=incoming,
                lead_time_days=lead_days,
                atp=atp,
                scarcity_lambda=scarcity_lambda,
                stock_status=status,
                updated_at=row["updated_at"],
            )
        finally:
            conn.close()

    def list_inventory(
        self,
        storefront_id: str = "primary_storefront",
        category: str | None = None,
        limit: int = 100,
    ) -> list[InventoryItem]:
        """Lists inventory items with ATP and scarcity shadow costs."""
        # Ensure initial seed exists
        self.seed_initial_inventory(storefront_id)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Pre-fetch point forecasts for storefront at 14d horizon
            fc_map: dict[str, float] = {}
            try:
                cursor.execute("""
                    SELECT sku, point_forecast FROM demand_forecasts
                    WHERE storefront_id = ? AND horizon_days = 14
                    ORDER BY created_at ASC
                """, (storefront_id,))
                for r in cursor.fetchall():
                    if r["point_forecast"] is not None:
                        fc_map[r["sku"]] = float(r["point_forecast"])
            except Exception:
                fc_map = {}

            query = """
                SELECT i.*, p.name as product_name, p.category, p.reference_price_cents, p.cogs_cents
                FROM sku_inventory i
                JOIN products p ON i.sku = p.id
                WHERE i.storefront_id = ?
            """
            params: list[Any] = [storefront_id]
            if category and category.lower() != "all":
                query += " AND LOWER(p.category) = LOWER(?)"
                params.append(category)

            query += " ORDER BY i.on_hand ASC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            items: list[InventoryItem] = []

            for row in rows:
                on_hand = int(row["on_hand"])
                reserved = int(row["reserved"])
                safety = int(row["safety_stock"])
                incoming = int(row["incoming"])
                lead_days = int(row["lead_time_days"])
                atp = calculate_atp(on_hand, reserved)
                ref_price = round(int(row["reference_price_cents"]) / 100.0, 2)
                cogs = round(int(row["cogs_cents"]) / 100.0, 2)
                fc_point = fc_map.get(row["sku"], None)
                scarcity_lambda = calculate_scarcity_lambda(ref_price, cogs, atp, safety, fc_point)
                status = determine_stock_status(atp, safety, fc_point if fc_point is not None else max(14.0, float(safety * 1.5)))

                items.append(InventoryItem(
                    sku=row["sku"],
                    product_name=row["product_name"],
                    category=row["category"],
                    storefront_id=storefront_id,
                    on_hand=on_hand,
                    reserved=reserved,
                    safety_stock=safety,
                    incoming=incoming,
                    lead_time_days=lead_days,
                    atp=atp,
                    scarcity_lambda=scarcity_lambda,
                    stock_status=status,
                    updated_at=row["updated_at"],
                ))
            return items
        finally:
            conn.close()

    def update_stock(
        self,
        sku: str,
        on_hand_delta: int = 0,
        reserved_delta: int = 0,
        storefront_id: str = "primary_storefront",
    ) -> bool:
        """Modifies physical stock or reserved allocations atomically."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT on_hand, reserved FROM sku_inventory
                WHERE sku = ? AND storefront_id = ?
            """, (sku, storefront_id))
            row = cursor.fetchone()
            if not row:
                return False

            new_on_hand = max(0, int(row["on_hand"]) + on_hand_delta)
            new_reserved = max(0, int(row["reserved"]) + reserved_delta)
            now_iso = datetime.now(timezone.utc).isoformat()

            cursor.execute("""
                UPDATE sku_inventory
                SET on_hand = ?, reserved = ?, updated_at = ?
                WHERE sku = ? AND storefront_id = ?
            """, (new_on_hand, new_reserved, now_iso, sku, storefront_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_inventory_alerts(self, storefront_id: str = "primary_storefront") -> list[InventoryAlert]:
        """Generates proactive, auditable inventory alerts for merchants."""
        items = self.list_inventory(storefront_id=storefront_id, limit=200)
        alerts: list[InventoryAlert] = []

        for item in items:
            # Approximate daily sales rate = safety_stock / 10
            daily_burn = max(0.5, item.safety_stock / 10.0)
            days_supply = round(item.atp / daily_burn, 1)

            if item.stock_status == "CRITICAL_STOCKOUT_RISK":
                alerts.append(InventoryAlert(
                    alert_id=f"alt_crit_{item.sku}",
                    sku=item.sku,
                    product_name=item.product_name,
                    severity="CRITICAL",
                    alert_type="STOCKOUT_RISK",
                    description=f"Only {item.atp} ATP units remaining ({days_supply} days of supply). High risk of stockout within supplier lead time ({item.lead_time_days} days).",
                    suggested_action=f"Suppress promotional discounts; reserve stock for full-margin organic traffic; expedite replenishment PO.",
                    days_of_supply_remaining=days_supply,
                ))
            elif item.stock_status == "LOW_STOCK":
                alerts.append(InventoryAlert(
                    alert_id=f"alt_low_{item.sku}",
                    sku=item.sku,
                    product_name=item.product_name,
                    severity="WARNING",
                    alert_type="REPLENISHMENT_RECOMMENDED",
                    description=f"Stock ({item.atp} units) is approaching safety buffer ({item.safety_stock} units). Supplier replenishment lead time is {item.lead_time_days} days.",
                    suggested_action="Issue replenishment purchase order; moderate bundle discounting.",
                    days_of_supply_remaining=days_supply,
                ))
            elif item.stock_status == "OVERSTOCKED":
                alerts.append(InventoryAlert(
                    alert_id=f"alt_over_{item.sku}",
                    sku=item.sku,
                    product_name=item.product_name,
                    severity="INFO",
                    alert_type="MARKDOWN_CANDIDATE",
                    description=f"High inventory surplus ({item.atp} ATP units, ~{days_supply} days supply). Scarcity opportunity cost is $0.00.",
                    suggested_action="Eligible for aggressive bundle incentives or promotional anchor offers to accelerate sell-through.",
                    days_of_supply_remaining=days_supply,
                ))

        # Sort: CRITICAL first, then WARNING, then INFO
        severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        alerts.sort(key=lambda a: (severity_order.get(a.severity, 3), a.days_of_supply_remaining))
        return alerts
