"""FairCart AI — Multi-Store Profit Intelligence Engine (Step 5.20)

Provides backend-authoritative ingestion, validation, and analytics for multi-storefront commerce data:
1. Validates order-line sales CSVs and traffic funnel event CSVs.
2. Enforces resource limits (file size, row limits, cell lengths) and privacy bounds (PII rejection).
3. Computes multi-store financial and conversion metrics:
   - Net Revenue = Gross Line Revenue - Discounts - Refunds
   - Gross Profit = Net Revenue - Applicable COGS
   - Gross Margin % = (Gross Profit / Net Revenue) * 100
   - Distinct Orders = Count of unique completed orders (never double-counted per item line)
   - AOV = Net Revenue / Distinct Completed Orders
   - Session-to-Order Conversion Rate = Distinct Completed Orders / Unique Sessions
4. Maintains strict currency isolation and denominator safety (zero/negative revenue guards).
5. Surfaces observational attribution and diagnostic warnings (uneconomic discount subsidization).
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("faircart.multi_store")

# Resource & security limits
MAX_CSV_BYTES = 10 * 1024 * 1024  # 10 MB max upload
MAX_CSV_ROWS = 20_000             # Max 20,000 rows per batch
MAX_CELL_CHARS = 1_000            # Max 1,000 chars per cell
MAX_ERROR_REPORT_ROWS = 50        # Limit detailed row errors in response

# Sensitive PII keywords that must be rejected to preserve privacy
FORBIDDEN_PII_KEYWORDS = {
    "email", "customer_email", "user_email", "mail",
    "first_name", "last_name", "full_name", "customer_name", "name",
    "credit_card", "card_number", "pan", "cvv", "cvc", "expiry",
    "ssn", "social_security", "national_id",
    "phone", "phone_number", "mobile",
    "billing_address", "shipping_address", "street", "postal_code", "zip",
    "ip_address", "client_ip", "mac_address",
}

# Supported currencies
VALID_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY"}

# Supported order statuses
VALID_ORDER_STATUSES = {"completed", "refunded", "cancelled", "pending"}

# Funnel event mapping for traffic
CANONICAL_TRAFFIC_EVENTS = {
    "product_view", "product_viewed", "product_focus",
    "search_submitted",
    "recommendation_impression", "recommendation_shown",
    "recommendation_click", "recommendation_accepted",
    "add_to_cart", "cart_item_added", "cart_add",
    "checkout_started",
    "demo_order_completed", "simulated_purchase_completed",
    "order_completed",
}

EVENT_NORMALIZATION = {
    "product_viewed": "product_view",
    "product_focus": "product_view",
    "cart_item_added": "add_to_cart",
    "cart_add": "add_to_cart",
    "recommendation_shown": "recommendation_impression",
    "recommendation_accepted": "recommendation_click",
    "simulated_purchase_completed": "demo_order_completed",
}

# Acquisition channels
VALID_CHANNELS = {
    "organic_search", "paid_search", "social_referral", "paid_social",
    "direct", "email", "affiliate", "referral", "unattributed"
}


def parse_timestamp_flexible(ts_str: str) -> str | None:
    """Parses various ISO and standard date formats into clean ISO-8601 UTC strings."""
    if not ts_str or not ts_str.strip():
        return None
    cleaned = ts_str.strip()
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    # Try fromisoformat as a fallback
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def normalize_channel(ch_str: str | None) -> str:
    """Normalizes raw acquisition/attribution channel strings."""
    if not ch_str or not ch_str.strip():
        return "unattributed"
    c = ch_str.strip().lower().replace(" ", "_").replace("-", "_")
    if "organic" in c or "google_organic" in c or "bing" in c:
        return "organic_search"
    if "paid" in c or "cpc" in c or "adwords" in c or "google_ads" in c:
        return "paid_search"
    if "social" in c or "facebook" in c or "instagram" in c or "twitter" in c or "tiktok" in c:
        return "social_referral"
    if "email" in c or "newsletter" in c:
        return "email"
    if "direct" in c or "none" in c:
        return "direct"
    if "affiliate" in c:
        return "affiliate"
    return c if c in VALID_CHANNELS else "unattributed"


def validate_and_parse_csv(
    csv_content: str,
    import_type: str,
    filename: str = "uploaded.csv",
    storefront_override: str | None = None,
    default_currency: str = "USD",
) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Validates and parses CSV contents into structured, type-safe records.
    
    Returns:
        (is_valid, accepted_rows, validation_errors, summary_metrics)
    """
    if not csv_content or not csv_content.strip():
        return False, [], [{"row": 0, "column": "file", "message": "CSV content is empty."}], {}

    # Check raw size
    byte_len = len(csv_content.encode("utf-8"))
    if byte_len > MAX_CSV_BYTES:
        return False, [], [{
            "row": 0,
            "column": "file",
            "message": f"CSV size ({byte_len / (1024*1024):.1f} MB) exceeds maximum limit of {MAX_CSV_BYTES // (1024*1024)} MB."
        }], {}

    f = io.StringIO(csv_content.lstrip("\ufeff"))
    reader = csv.reader(f)

    try:
        raw_headers = next(reader)
    except StopIteration:
        return False, [], [{"row": 0, "column": "header", "message": "CSV file contains no rows."}], {}

    headers = [h.strip().lower().replace(" ", "_") for h in raw_headers]

    # Privacy Check: Scan headers for forbidden PII
    for h in headers:
        if h in FORBIDDEN_PII_KEYWORDS:
            return False, [], [{
                "row": 1,
                "column": h,
                "message": f"Privacy violation: Header '{h}' contains personal identifiable information (PII). FairCart strictly rejects PII.",
                "sample_value": h,
            }], {}

    # Required headers inspection
    if import_type == "orders":
        required = ["order_id", "product_id", "gross_line_revenue"]
        if not storefront_override and "storefront_id" not in headers:
            required.append("storefront_id")
    elif import_type == "traffic":
        required = ["event_id", "session_id", "event_type"]
        if not storefront_override and "storefront_id" not in headers:
            required.append("storefront_id")
    else:
        return False, [], [{"row": 1, "column": "import_type", "message": f"Invalid import_type '{import_type}'. Must be 'orders' or 'traffic'."}], {}

    missing_headers = [r for r in required if r not in headers]
    if missing_headers:
        return False, [], [{
            "row": 1,
            "column": "headers",
            "message": f"Missing mandatory columns: {missing_headers}. Expected: {required}",
        }], {}

    header_idx = {h: i for i, h in enumerate(headers)}
    accepted_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    detected_storefronts = set()
    detected_currencies = set()
    detected_channels = set()
    row_count = 0

    for row_idx, row in enumerate(reader, start=2):
        row_count += 1
        if row_count > MAX_CSV_ROWS:
            return False, [], [{
                "row": row_idx,
                "column": "file",
                "message": f"Exceeded maximum row capacity of {MAX_CSV_ROWS:,} rows. CSV rejected.",
            }], {}

        if not row or not any(field.strip() for field in row):
            continue  # skip blank lines

        # Row width check
        if len(row) < len(headers):
            if len(errors) < MAX_ERROR_REPORT_ROWS:
                errors.append({
                    "row": row_idx,
                    "column": "row_structure",
                    "message": f"Row has {len(row)} values, but expected {len(headers)} columns.",
                })
            continue

        # Cell length check
        has_oversize_cell = False
        for c_val in row:
            if len(c_val) > MAX_CELL_CHARS:
                has_oversize_cell = True
                break
        if has_oversize_cell:
            if len(errors) < MAX_ERROR_REPORT_ROWS:
                errors.append({
                    "row": row_idx,
                    "column": "cell_length",
                    "message": f"Row contains a cell exceeding {MAX_CELL_CHARS} characters.",
                })
            continue

        def get_val(col_name: str, default: str = "") -> str:
            idx = header_idx.get(col_name)
            return row[idx].strip() if idx is not None and idx < len(row) else default

        storefront_id = storefront_override or get_val("storefront_id")
        if not storefront_id:
            if len(errors) < MAX_ERROR_REPORT_ROWS:
                errors.append({
                    "row": row_idx,
                    "column": "storefront_id",
                    "message": "storefront_id cannot be empty.",
                })
            continue

        # Sanitize storefront ID
        clean_storefront = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", storefront_id)
        detected_storefronts.add(clean_storefront)

        # ---------------------------------------------------------------------
        # Order-Line Processing
        # ---------------------------------------------------------------------
        if import_type == "orders":
            order_id = get_val("order_id")
            if not order_id:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({"row": row_idx, "column": "order_id", "message": "order_id cannot be empty."})
                continue

            raw_ts = get_val("order_timestamp")
            if not raw_ts:
                clean_ts = datetime.now(timezone.utc).isoformat()
            else:
                clean_ts = parse_timestamp_flexible(raw_ts)
                if not clean_ts:
                    if len(errors) < MAX_ERROR_REPORT_ROWS:
                        errors.append({
                            "row": row_idx,
                            "column": "order_timestamp",
                            "message": f"Malformed timestamp '{raw_ts}'. Use ISO-8601 (YYYY-MM-DDTHH:MM:SSZ).",
                            "sample_value": raw_ts,
                        })
                    continue

            product_id = get_val("product_id") or get_val("item_id")
            if not product_id:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({"row": row_idx, "column": "product_id", "message": "product_id cannot be empty."})
                continue

            # Quantity
            raw_qty = get_val("quantity", "1")
            try:
                qty = int(raw_qty)
                if qty <= 0:
                    raise ValueError("must be > 0")
            except ValueError:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({
                        "row": row_idx,
                        "column": "quantity",
                        "message": f"Invalid quantity '{raw_qty}'. Must be an integer greater than 0.",
                        "sample_value": raw_qty,
                    })
                continue

            # Numeric Financials
            def parse_money(field: str, default: float = 0.0) -> float | None:
                raw_v = get_val(field, str(default))
                if not raw_v:
                    return default
                try:
                    val = float(raw_v.replace("$", "").replace(",", ""))
                    return val if val >= 0.0 else None
                except ValueError:
                    return None

            gross_rev = parse_money("gross_line_revenue")
            if gross_rev is None:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({
                        "row": row_idx,
                        "column": "gross_line_revenue",
                        "message": f"Invalid gross_line_revenue '{get_val('gross_line_revenue')}'. Must be non-negative numeric.",
                    })
                continue

            discount = parse_money("discount_amount", 0.0)
            if discount is None:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({
                        "row": row_idx,
                        "column": "discount_amount",
                        "message": f"Invalid discount_amount '{get_val('discount_amount')}'. Must be non-negative numeric.",
                    })
                continue

            refund = parse_money("refund_amount", 0.0)
            if refund is None:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({
                        "row": row_idx,
                        "column": "refund_amount",
                        "message": f"Invalid refund_amount '{get_val('refund_amount')}'. Must be non-negative numeric.",
                    })
                continue

            cogs = parse_money("cogs_amount", 0.0)
            if cogs is None:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({
                        "row": row_idx,
                        "column": "cogs_amount",
                        "message": f"Invalid cogs_amount '{get_val('cogs_amount')}'. Must be non-negative numeric.",
                    })
                continue

            status = get_val("order_status", "completed").lower()
            if status not in VALID_ORDER_STATUSES:
                status = "completed"

            currency = get_val("currency", default_currency).upper()
            if currency not in VALID_CURRENCIES:
                currency = default_currency
            detected_currencies.add(currency)

            channel = normalize_channel(get_val("attribution_channel"))
            detected_channels.add(channel)

            # Generate stable deterministic line identifier
            stable_seed = f"{clean_storefront}:{order_id}:{product_id}:{row_idx}:{qty}:{gross_rev}"
            line_id = f"sol-{hashlib.sha256(stable_seed.encode()).hexdigest()[:16]}"

            accepted_rows.append({
                "id": line_id,
                "storefront_id": clean_storefront,
                "order_id": order_id,
                "order_timestamp": clean_ts,
                "order_status": status,
                "currency": currency,
                "product_id": product_id,
                "quantity": qty,
                "gross_line_revenue_cents": int(round(gross_rev * 100)),
                "discount_cents": int(round(discount * 100)),
                "refund_cents": int(round(refund * 100)),
                "cogs_cents": int(round(cogs * 100)),
                "attribution_channel": channel,
            })

        # ---------------------------------------------------------------------
        # Traffic & Funnel Event Processing
        # ---------------------------------------------------------------------
        elif import_type == "traffic":
            event_id = get_val("event_id")
            if not event_id:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({"row": row_idx, "column": "event_id", "message": "event_id cannot be empty."})
                continue

            raw_ts = get_val("event_timestamp")
            if not raw_ts:
                clean_ts = datetime.now(timezone.utc).isoformat()
            else:
                clean_ts = parse_timestamp_flexible(raw_ts)
                if not clean_ts:
                    if len(errors) < MAX_ERROR_REPORT_ROWS:
                        errors.append({
                            "row": row_idx,
                            "column": "event_timestamp",
                            "message": f"Malformed timestamp '{raw_ts}'.",
                            "sample_value": raw_ts,
                        })
                    continue

            session_id = get_val("session_id")
            if not session_id:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({"row": row_idx, "column": "session_id", "message": "session_id cannot be empty."})
                continue

            raw_event_type = get_val("event_type").lower()
            normalized_type = EVENT_NORMALIZATION.get(raw_event_type, raw_event_type)
            if normalized_type not in CANONICAL_TRAFFIC_EVENTS:
                if len(errors) < MAX_ERROR_REPORT_ROWS:
                    errors.append({
                        "row": row_idx,
                        "column": "event_type",
                        "message": f"Invalid event_type '{raw_event_type}'. Must be one of {sorted(CANONICAL_TRAFFIC_EVENTS)}",
                    })
                continue

            channel = normalize_channel(get_val("acquisition_channel"))
            detected_channels.add(channel)
            product_id = get_val("product_id")
            order_id = get_val("order_id")

            stable_seed = f"{clean_storefront}:{event_id}:{session_id}:{normalized_type}"
            line_id = f"ste-{hashlib.sha256(stable_seed.encode()).hexdigest()[:16]}"

            accepted_rows.append({
                "id": line_id,
                "storefront_id": clean_storefront,
                "event_id": event_id,
                "event_timestamp": clean_ts,
                "session_id": session_id,
                "event_type": normalized_type,
                "acquisition_channel": channel,
                "product_id": product_id,
                "order_id": order_id,
            })

    total_valid = len(accepted_rows)
    total_rejected = len(errors)
    is_valid = total_valid > 0 and (total_rejected == 0 or total_valid > total_rejected)

    # Compute high-level preview stats
    summary_metrics: dict[str, Any] = {
        "total_rows_parsed": row_count,
        "accepted_rows": total_valid,
        "rejected_rows": total_rejected,
        "detected_storefronts": sorted(list(detected_storefronts)),
        "detected_currencies": sorted(list(detected_currencies)),
        "detected_channels": sorted(list(detected_channels)),
    }

    if import_type == "orders" and accepted_rows:
        unique_orders = len({r["order_id"] for r in accepted_rows})
        gross_cents = sum(r["gross_line_revenue_cents"] for r in accepted_rows)
        discount_cents = sum(r["discount_cents"] for r in accepted_rows)
        refund_cents = sum(r["refund_cents"] for r in accepted_rows)
        cogs_cents = sum(r["cogs_cents"] for r in accepted_rows)
        net_cents = gross_cents - discount_cents - refund_cents
        gross_profit_cents = net_cents - cogs_cents
        margin_pct = round((gross_profit_cents / net_cents) * 100, 2) if net_cents > 0 else 0.0

        summary_metrics.update({
            "distinct_orders": unique_orders,
            "estimated_gross_revenue": round(gross_cents / 100.0, 2),
            "estimated_discount_total": round(discount_cents / 100.0, 2),
            "estimated_refund_total": round(refund_cents / 100.0, 2),
            "estimated_net_revenue": round(net_cents / 100.0, 2),
            "estimated_gross_profit": round(gross_profit_cents / 100.0, 2),
            "estimated_gross_margin_pct": margin_pct,
        })
    elif import_type == "traffic" and accepted_rows:
        unique_sessions = len({r["session_id"] for r in accepted_rows})
        views = sum(1 for r in accepted_rows if r["event_type"] == "product_view")
        cart_adds = sum(1 for r in accepted_rows if r["event_type"] == "add_to_cart")
        checkouts = sum(1 for r in accepted_rows if r["event_type"] == "checkout_started")
        orders = sum(1 for r in accepted_rows if r["event_type"] in ("order_completed", "demo_order_completed"))

        summary_metrics.update({
            "unique_sessions": unique_sessions,
            "product_views": views,
            "cart_adds": cart_adds,
            "checkouts_started": checkouts,
            "completed_orders": orders,
        })

    return is_valid, accepted_rows, errors, summary_metrics


def aggregate_profit_intelligence(
    order_rows: list[dict[str, Any]],
    traffic_rows: list[dict[str, Any]],
    catalogue_products: list[Any] | None = None,
    currency_filter: str | None = None,
) -> dict[str, Any]:
    """Computes comprehensive multi-storefront and acquisition-channel financial intelligence.
    
    Guarantees:
    - Orders are distinctly counted by order_id (never double-counted per product line).
    - Currencies are strictly isolated.
    - Zero/negative denominators return 0.0 and emit data quality flags.
    - Observational attribution is strictly distinguished from causal inference.
    """
    cat_by_id = {p.id: p for p in (catalogue_products or [])}

    # 1. Currency identification
    all_currencies = sorted(list({r["currency"] for r in order_rows} or {"USD"}))
    selected_currency = currency_filter if (currency_filter and currency_filter in all_currencies) else all_currencies[0]

    # Filter orders to selected currency
    active_orders = [r for r in order_rows if r["currency"] == selected_currency]

    # Group orders by storefront
    orders_by_store: dict[str, list[dict[str, Any]]] = {}
    for r in active_orders:
        orders_by_store.setdefault(r["storefront_id"], []).append(r)

    # Group traffic by storefront
    traffic_by_store: dict[str, list[dict[str, Any]]] = {}
    for r in traffic_rows:
        traffic_by_store.setdefault(r["storefront_id"], []).append(r)

    all_store_ids = sorted(list(set(orders_by_store.keys()) | set(traffic_by_store.keys())))

    storefront_metrics: list[dict[str, Any]] = []
    category_totals: dict[str, dict[str, int]] = {}

    agg_gross_cents = 0
    agg_discount_cents = 0
    agg_refund_cents = 0
    agg_cogs_cents = 0
    agg_net_cents = 0
    agg_profit_cents = 0
    agg_distinct_orders: set[str] = set()
    agg_distinct_sessions: set[str] = set()

    for sid in all_store_ids:
        s_orders = orders_by_store.get(sid, [])
        s_traffic = traffic_by_store.get(sid, [])

        quality_flags: list[str] = []

        # Distinct order aggregation: Group lines by order_id
        order_line_map: dict[str, list[dict[str, Any]]] = {}
        completed_order_ids: set[str] = set()

        for l in s_orders:
            oid = l["order_id"]
            order_line_map.setdefault(oid, []).append(l)
            if l["order_status"] == "completed":
                completed_order_ids.add(oid)

        # Compute order financial sums
        gross_cents = sum(l["gross_line_revenue_cents"] for l in s_orders)
        discount_cents = sum(l["discount_cents"] for l in s_orders)
        refund_cents = sum(l["refund_cents"] for l in s_orders)
        cogs_cents = sum(l["cogs_cents"] for l in s_orders)
        units_sold = sum(l["quantity"] for l in s_orders)

        net_cents = gross_cents - discount_cents - refund_cents
        gross_profit_cents = net_cents - cogs_cents
        distinct_orders_cnt = len(completed_order_ids)

        # Track category contributions
        for l in s_orders:
            pid = l["product_id"]
            prod = cat_by_id.get(pid)
            cat = prod.category if prod else "General Goods"
            c_entry = category_totals.setdefault(cat, {"gross_cents": 0, "profit_cents": 0, "units": 0})
            c_entry["gross_cents"] += l["gross_line_revenue_cents"]
            c_entry["units"] += l["quantity"]
            line_net = l["gross_line_revenue_cents"] - l["discount_cents"] - l["refund_cents"]
            c_entry["profit_cents"] += (line_net - l["cogs_cents"])

        # Traffic metrics
        session_ids = {t["session_id"] for t in s_traffic}
        views = sum(1 for t in s_traffic if t["event_type"] == "product_view")
        rec_impr = sum(1 for t in s_traffic if t["event_type"] == "recommendation_impression")
        rec_clicks = sum(1 for t in s_traffic if t["event_type"] == "recommendation_click")
        cart_adds = sum(1 for t in s_traffic if t["event_type"] == "add_to_cart")
        checkouts = sum(1 for t in s_traffic if t["event_type"] == "checkout_started")

        unique_sessions = len(session_ids)

        # Rates & safe math
        margin_pct = round((gross_profit_cents / net_cents) * 100, 2) if net_cents > 0 else 0.0
        aov = round((net_cents / 100.0) / distinct_orders_cnt, 2) if distinct_orders_cnt > 0 else 0.0
        conversion_rate = min(1.0, round(distinct_orders_cnt / unique_sessions, 4)) if unique_sessions > 0 else 0.0
        rec_ctr = min(1.0, round(rec_clicks / rec_impr, 4)) if rec_impr > 0 else 0.0
        discount_share = round((discount_cents / gross_cents) * 100, 2) if gross_cents > 0 else 0.0
        refund_rate = round((refund_cents / gross_cents) * 100, 2) if gross_cents > 0 else 0.0

        # Data quality diagnostics
        if not s_traffic and s_orders:
            quality_flags.append("Traffic data missing: conversion rate and CTR unavailable")
        if not s_orders and s_traffic:
            quality_flags.append("Order data missing: financial metrics reflect zero sales")
        if net_cents <= 0 and gross_cents > 0:
            quality_flags.append("Discounts and refunds exceed gross revenue (net revenue non-positive)")
        if cogs_cents == 0 and gross_cents > 0:
            quality_flags.append("Wholesale COGS not provided (gross margin defaults to 100% upper bound)")
        if distinct_orders_cnt > 0 and distinct_orders_cnt < 10:
            quality_flags.append(f"Small order sample size (N={distinct_orders_cnt}): metrics may have high variance")
        unattributed_cents = sum(l["gross_line_revenue_cents"] for l in s_orders if l.get("attribution_channel") in ("unattributed", "unknown", "", None))
        if gross_cents > 0 and (unattributed_cents / gross_cents) > 0.50:
            quality_flags.append("High unattributed revenue (>50% of gross): channel attribution incomplete")

        store_name = sid.replace("-", " ").replace("_", " ").title()

        storefront_metrics.append({
            "storefront_id": sid,
            "storefront_name": store_name,
            "currency": selected_currency,
            "unique_sessions": unique_sessions,
            "product_views": views,
            "recommendation_impressions": rec_impr,
            "recommendation_clicks": rec_clicks,
            "cart_adds": cart_adds,
            "checkouts_started": checkouts,
            "distinct_orders": distinct_orders_cnt,
            "units_sold": units_sold,
            "gross_revenue": round(gross_cents / 100.0, 2),
            "discount_amount": round(discount_cents / 100.0, 2),
            "refund_amount": round(refund_cents / 100.0, 2),
            "net_revenue": round(net_cents / 100.0, 2),
            "cogs": round(cogs_cents / 100.0, 2),
            "gross_profit": round(gross_profit_cents / 100.0, 2),
            "gross_margin_pct": margin_pct,
            "aov": aov,
            "conversion_rate": conversion_rate,
            "recommendation_ctr": rec_ctr,
            "discount_share_pct": discount_share,
            "refund_rate_pct": refund_rate,
            "data_quality_flags": quality_flags,
        })

        agg_gross_cents += gross_cents
        agg_discount_cents += discount_cents
        agg_refund_cents += refund_cents
        agg_cogs_cents += cogs_cents
        agg_net_cents += net_cents
        agg_profit_cents += gross_profit_cents
        agg_distinct_orders.update(completed_order_ids)
        agg_distinct_sessions.update(session_ids)

    # -------------------------------------------------------------------------
    # Acquisition Channel Breakdown
    # -------------------------------------------------------------------------
    channel_order_map: dict[str, list[dict[str, Any]]] = {}
    for r in active_orders:
        channel_order_map.setdefault(r["attribution_channel"], []).append(r)

    channel_traffic_map: dict[str, list[dict[str, Any]]] = {}
    for r in traffic_rows:
        channel_traffic_map.setdefault(r["acquisition_channel"], []).append(r)

    all_channels = sorted(list(set(channel_order_map.keys()) | set(channel_traffic_map.keys())))

    channel_metrics: list[dict[str, Any]] = []
    for ch in all_channels:
        ch_orders = channel_order_map.get(ch, [])
        ch_traffic = channel_traffic_map.get(ch, [])

        ch_order_ids = {l["order_id"] for l in ch_orders if l["order_status"] == "completed"}
        ch_sessions = {t["session_id"] for t in ch_traffic}

        ch_gross = sum(l["gross_line_revenue_cents"] for l in ch_orders)
        ch_discount = sum(l["discount_cents"] for l in ch_orders)
        ch_refund = sum(l["refund_cents"] for l in ch_orders)
        ch_cogs = sum(l["cogs_cents"] for l in ch_orders)

        ch_net = ch_gross - ch_discount - ch_refund
        ch_profit = ch_net - ch_cogs
        ch_orders_cnt = len(ch_order_ids)
        ch_sessions_cnt = len(ch_sessions)

        ch_margin = round((ch_profit / ch_net) * 100, 2) if ch_net > 0 else 0.0
        ch_aov = round((ch_net / 100.0) / ch_orders_cnt, 2) if ch_orders_cnt > 0 else 0.0
        ch_conv = min(1.0, round(ch_orders_cnt / ch_sessions_cnt, 4)) if ch_sessions_cnt > 0 else 0.0

        label_map = {
            "organic_search": "Organic Search (SEO)",
            "paid_search": "Paid Search (Search Ads)",
            "social_referral": "Social Referrals",
            "paid_social": "Paid Social Ads",
            "direct": "Direct Navigation",
            "email": "Email Campaigns",
            "affiliate": "Affiliate Partners",
            "unattributed": "Direct / Unattributed",
        }

        channel_metrics.append({
            "channel": ch,
            "channel_label": label_map.get(ch, ch.replace("_", " ").title()),
            "currency": selected_currency,
            "unique_sessions": ch_sessions_cnt,
            "attributed_orders": ch_orders_cnt,
            "gross_revenue": round(ch_gross / 100.0, 2),
            "discount_amount": round(ch_discount / 100.0, 2),
            "net_revenue": round(ch_net / 100.0, 2),
            "cogs": round(ch_cogs / 100.0, 2),
            "gross_profit": round(ch_profit / 100.0, 2),
            "gross_margin_pct": ch_margin,
            "aov": ch_aov,
            "conversion_rate": ch_conv,
            "attribution_note": "Attributed revenue is observational; does not prove incremental causation.",
        })

    # Sort channels by net revenue desc
    channel_metrics.sort(key=lambda c: c["net_revenue"], reverse=True)

    # -------------------------------------------------------------------------
    # Category Profitability
    # -------------------------------------------------------------------------
    category_breakdown: list[dict[str, Any]] = []
    for cat, data in category_totals.items():
        g_rev = round(data["gross_cents"] / 100.0, 2)
        g_prof = round(data["profit_cents"] / 100.0, 2)
        margin = round((data["profit_cents"] / data["gross_cents"]) * 100, 2) if data["gross_cents"] > 0 else 0.0
        category_breakdown.append({
            "category": cat,
            "units_sold": data["units"],
            "gross_revenue": g_rev,
            "gross_profit": g_prof,
            "gross_margin_pct": margin,
        })
    category_breakdown.sort(key=lambda c: c["gross_profit"], reverse=True)

    # -------------------------------------------------------------------------
    # Discounting & Uneconomic Subsidization Diagnostics
    # -------------------------------------------------------------------------
    diagnostics: list[dict[str, Any]] = []
    for sm in storefront_metrics:
        if sm["discount_share_pct"] > 15.0 and sm["gross_margin_pct"] < 25.0 and sm["gross_revenue"] > 100.0:
            diagnostics.append({
                "severity": "warning",
                "storefront_id": sm["storefront_id"],
                "storefront_name": sm["storefront_name"],
                "metric": "Heavy Discounting with Compressed Margin",
                "detail": f"Discounts consume {sm['discount_share_pct']:.1f}% of gross sales, while gross margin is only {sm['gross_margin_pct']:.1f}%. Consider tightening basket margin floors.",
            })
        if sm["refund_rate_pct"] > 15.0 and sm["gross_revenue"] > 100.0:
            diagnostics.append({
                "severity": "alert",
                "storefront_id": sm["storefront_id"],
                "storefront_name": sm["storefront_name"],
                "metric": "High Refund Rate",
                "detail": f"Refunds represent {sm['refund_rate_pct']:.1f}% of gross merchandise revenue. Investigate product quality or packaging.",
            })
        if sm["conversion_rate"] < 0.015 and sm["unique_sessions"] > 200:
            diagnostics.append({
                "severity": "info",
                "storefront_id": sm["storefront_id"],
                "storefront_name": sm["storefront_name"],
                "metric": "Sub-Benchmark Session Conversion",
                "detail": f"Session-to-order conversion ({sm['conversion_rate']*100:.1f}%) is below 1.5% despite {sm['unique_sessions']} sessions. Check storefront compatibility picks.",
            })

    # Aggregated totals
    agg_margin = round((agg_profit_cents / agg_net_cents) * 100, 2) if agg_net_cents > 0 else 0.0
    agg_aov = round((agg_net_cents / 100.0) / len(agg_distinct_orders), 2) if agg_distinct_orders else 0.0
    agg_conv = min(1.0, round(len(agg_distinct_orders) / len(agg_distinct_sessions), 4)) if agg_distinct_sessions else 0.0

    aggregated_totals = {
        "currency": selected_currency,
        "total_storefronts": len(storefront_metrics),
        "total_distinct_orders": len(agg_distinct_orders),
        "total_unique_sessions": len(agg_distinct_sessions),
        "gross_revenue": round(agg_gross_cents / 100.0, 2),
        "discount_amount": round(agg_discount_cents / 100.0, 2),
        "refund_amount": round(agg_refund_cents / 100.0, 2),
        "net_revenue": round(agg_net_cents / 100.0, 2),
        "cogs": round(agg_cogs_cents / 100.0, 2),
        "gross_profit": round(agg_profit_cents / 100.0, 2),
        "gross_margin_pct": agg_margin,
        "overall_aov": agg_aov,
        "overall_conversion_rate": agg_conv,
    }

    return {
        "selected_currency": selected_currency,
        "currencies_available": all_currencies,
        "total_storefronts": len(storefront_metrics),
        "aggregated_totals": aggregated_totals,
        "storefronts": storefront_metrics,
        "channels": channel_metrics,
        "category_profitability": category_breakdown,
        "discounting_diagnostics": diagnostics,
        "methodology_disclaimer": (
            "Multi-Store Profit Intelligence aggregates imported sales line items and traffic events. "
            "Net revenue equals gross merchandise revenue minus recorded discounts and refunds. "
            "Gross profit accounts for wholesale COGS only, excluding unimported operational overhead (fulfillment, payment processing, marketing). "
            "Channel metrics reflect observational attribution, not causal incrementality."
        ),
        "data_provenance": "merchant_imported_csv",
    }
