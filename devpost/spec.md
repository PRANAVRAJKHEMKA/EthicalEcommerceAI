---
doc: spec
status: approved
---

# FairCart AI — Technical Specification

Explainable, margin-preserving e-commerce recommendation and incentive optimization engine for responsible commerce.

---

## 1. How This Works, In Plain Language

FairCart AI consists of two clean, decoupled components designed for 100% reliable local execution on Windows:
1. **The Storefront & Console (Frontend):** A responsive React + TypeScript single-page application built with Vite and Tailwind CSS. It provides the customer shopping journey on **Shop Store** (`/`) and administrative controls on **Merchant Console** (`/merchant`).
2. **The Decision Engine (Backend):** A high-performance Python application built with FastAPI. It accesses a local SQLite database (`faircart.db`), executes content-based product recommendation (Engine A), computes margin-constrained economic optimization (Engine B), and orchestrates the response (Engine C) in under 25 milliseconds.

### Architectural Decoupling of Generative AI
Crucially, **the local decision engine does not wait for Gemini.** The primary decision endpoint (`POST /api/v1/decision`) executes locally, instantly returning the recommended product, authoritative financial figures, incentive decision, and a pre-validated deterministic explanation. If Gemini is configured, the browser requests personalized explanatory copy asynchronously via a secondary endpoint (`POST /api/v1/explanation`). Gemini **never** touches prices, discounts, margins, or product identifiers.

---

## 2. The Core Journey Through the System

Implements `prd.md > 1. The Core Journey`.

```text
[ Shopper: Add to Cart ]
           │
           ▼
[ React: POST /api/v1/decision ] ──(cart_items, session_id)──► [ FastAPI Gateway ]
                                                                       │
                                      ┌────────────────────────────────┴────────────────────────────────┐
                                      ▼                                                                 ▼
                        [ Engine A: Recommender ]                                         [ Catalog Repository ]
                        - Match complementary tags                                        - Read DB wholesale COGS & ref price
                        - Compute affinity score                                          - Filter out-of-stock items
                                      │                                                                 │
                                      └────────────────────────────────┬────────────────────────────────┘
                                                                       │
                                                                       ▼
                                                         [ Engine B: Economic Optimizer ]
                                                         - Enforce: Basket Gross Margin >= Floor
                                                         - Enforce: Final Price <= Reference Price
                                                         - Calculate: Incremental Contribution Utility
                                                         - Action: BUNDLE_DISCOUNT or NO_OFFER
                                                                       │
                                                                       ▼
                                                         [ Engine C: Orchestrator ]
                                                         - Attach deterministic explanation
                                                         - Log decision telemetry to SQLite
                                                                       │
                                                                       ▼
[ React: Cart Drawer Updated ] ◄────(JSON Decision Response <25ms)─────┘
- Render recommended accessory immediately
- Display deterministic explanation copy
- Show exact pricing: reference price, discount, final price, savings
           │
           ▼ (Optional Async Request)
[ React: POST /api/v1/explanation ] ─────────────────────────► [ Gemini Service ]
                                                               - Generate natural customer copy
                                                               - (If offline/no key, return fallback)
                                                                       │
[ React: Explanatory Copy Updated ] ◄──────────────────────────────────┘
```

---

## 3. Mathematical & Economic Model

### 3.1 Basket Gross Margin
For any candidate basket action $a$, the total basket gross margin is defined strictly as:
$$\text{gross\_margin}(a) = \begin{cases} \frac{\text{net\_sales\_revenue}(a) - \text{total\_COGS}}{\text{net\_sales\_revenue}(a)} & \text{if } \text{net\_sales\_revenue}(a) > 0 \\ 0.0 & \text{if } \text{net\_sales\_revenue}(a) \le 0 \end{cases}$$

- **Input Validation:** If $\text{net\_sales\_revenue}(a) \le 0$, or if any required cost or price input is missing, the engine safely returns $\text{gross\_margin} = 0.0$ and forces action $a = \text{NO\_OFFER}$.
- **Margin Floor Constraint:** The optimizer strictly enforces:
  $$\text{gross\_margin}(a) \ge \text{configured\_margin\_floor}$$
  This is calculated across the **entire basket** (parent item + recommended accessory), preventing high-cost accessories from eroding basket profitability.

### 3.2 Contribution Profit
Contribution profit accounts for revenue, product costs, variable fulfillment, and incentive action costs:
$$\text{contribution\_profit}(a) = \text{net\_sales\_revenue}(a) - \text{total\_COGS} - \text{variable\_fulfillment\_cost} - \text{action\_costs}(a)$$
- **Accounting Invariant:** Net sales revenue is calculated *after* applying the discount ($\text{net\_sales\_revenue} = \text{reference\_price} - \text{discount}$). Therefore, discount expense is not subtracted a second time.

### 3.3 Incremental Contribution Utility
The decision objective maximizes expected incremental contribution profit over the no-incentive baseline:
$$\text{incremental\_utility}(a) = E[\text{contribution\_profit}(a)] - E[\text{contribution\_profit}(\text{no\_offer})]$$
Where:
$$E[\text{contribution\_profit}(a)] = P(\text{conversion} \mid \text{context}, a) \times \text{contribution\_profit}(a)$$

- **Decision Rule:**
  $$\text{selected\_action} = \arg\max_{a \in \mathcal{A}_{\text{eligible}}} \text{incremental\_utility}(a)$$
  Subject to:
  1. $\text{gross\_margin}(a) \ge \text{configured\_margin\_floor}$
  2. $\text{final\_price}(a) \le \text{reference\_price}$
  3. $\text{incremental\_utility}(a) > 0$
  If no discounted action satisfies these criteria, Engine B returns $\text{NO\_OFFER}$.
- **Heuristic Conversion Transparency:** Because this proof of concept operates without live production A/B traffic, conversion probabilities are explicitly documented as heuristic baseline estimates based on cart value, session dwell time, and price elasticity, rather than empirical causal claims.

---

## 4. Stack & Environment Configuration

### Backend Stack
- **Runtime:** Python `3.12.1` (installed at `C:\Users\LENOVO\AppData\Local\Programs\Python\Python312\python.exe`).
- **Web API:** `FastAPI (0.115.7)` with `uvicorn (0.34.0)`.
- **Validation:** `pydantic (2.10.6)` and `pydantic-settings (2.7.1)`.
- **Database:** Standard library `sqlite3` driver accessing `faircart.db`.
- **External Client:** `httpx (0.28.1)` for asynchronous Gemini API calls.
- **Simulation Math:** `numpy (2.2.6)` for deterministic synthetic session generation.
- **Test Runner:** Python standard library `unittest` (`python -m unittest`).

### Frontend Stack
- **Framework:** `React 19` with `TypeScript`.
- **Build & Dev Server:** `Vite`.
- **Styling:** `Tailwind CSS`.
- **Icons:** `Lucide React`.

### Windows Execution Commands (From Repository Root)

**1. Create and Seed Database:**
```powershell
.\.venv\Scripts\python.exe backend/scripts/seed_catalog.py
```
*(Idempotent: Uses `CREATE TABLE IF NOT EXISTS` and `INSERT OR REPLACE` to safely re-seed anytime).*

**2. Run Backend API Server:**
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
```

**3. Run Frontend Development Server:**
```powershell
cd frontend
npm install
npm run dev
```

**4. Run Automated Test Suite:**
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```

---

## 5. API Contracts & Schemas

### 5.1 `GET /api/v1/health`
Returns backend operational health and database readiness.
- **Response `200 OK`:**
```json
{
  "status": "healthy",
  "catalog_items_loaded": 20,
  "database": "sqlite",
  "gemini_configured": true,
  "version": "1.0.0"
}
```

### 5.2 `GET /api/v1/catalog`
Returns all 20 catalog products with authoritative pricing and stock.
- **Response `200 OK`:**
```json
[
  {
    "id": "item-001",
    "name": "Ergonomic Mechanical Keyboard",
    "category": "Keyboards",
    "description": "Split ergonomic layout with custom tactile switches.",
    "reference_price": 80.00,
    "cogs": 40.00,
    "inventory": 45,
    "complementary_ids": ["item-002", "item-006"],
    "image_url": "/images/keyboard.jpg"
  }
]
```

### 5.3 `POST /api/v1/decision`
Primary, synchronous decision endpoint (< 25 ms latency).
- **Request Body:**
```json
{
  "session_id": "sess-a1b2c3d4",
  "cart_items": [
    {
      "product_id": "item-001",
      "quantity": 1
    }
  ],
  "dwell_time_seconds": 45,
  "margin_floor": 0.20,
  "discount_cap": 0.15
}
```

- **Response `200 OK` (Offer Applied):**
```json
{
  "request_id": "req-98765",
  "session_id": "sess-a1b2c3d4",
  "decision": "OFFER_APPLIED",
  "recommendation": {
    "product_id": "item-002",
    "name": "Padded Memory Foam Wrist Rest",
    "category": "Accessories",
    "reference_price": 25.00,
    "affinity_score": 0.92,
    "compatibility_reason": "Ergonomically aligned for mechanical keyboards"
  },
  "incentive": {
    "is_offered": true,
    "tier": "BUNDLE_DISCOUNT",
    "discount_percentage": 0.10,
    "reference_price": 25.00,
    "final_price": 22.50,
    "savings": 2.50,
    "currency": "USD",
    "conditions": "Valid when bundled with Ergonomic Mechanical Keyboard"
  },
  "deterministic_explanation": "Bundle & Save: Pair your keyboard with this wrist rest for enhanced comfort while preserving store margins.",
  "decision_reason": "Eligible bundle: basket gross margin is 35.7% (exceeds 20.0% floor) with positive estimated incremental utility.",
  "basket_gross_margin": 0.3571,
  "fallback_applied": false,
  "execution_latency_ms": 12.4
}
```

- **Response `200 OK` (No Offer / Margin Floor Deficit):**
```json
{
  "request_id": "req-98766",
  "session_id": "sess-a1b2c3d4",
  "decision": "NO_OFFER",
  "recommendation": {
    "product_id": "item-002",
    "name": "Padded Memory Foam Wrist Rest",
    "category": "Accessories",
    "reference_price": 25.00,
    "affinity_score": 0.92,
    "compatibility_reason": "Ergonomically aligned for mechanical keyboards"
  },
  "incentive": {
    "is_offered": false,
    "tier": "NONE",
    "discount_percentage": 0.0,
    "reference_price": 25.00,
    "final_price": 25.00,
    "savings": 0.0,
    "currency": "USD",
    "conditions": "Standard price · No discount applied"
  },
  "deterministic_explanation": "Recommended complementary accessory for your current basket.",
  "decision_reason": "Incentive omitted: applying discount would breach the 40.0% gross margin floor.",
  "basket_gross_margin": 0.4762,
  "fallback_applied": false,
  "execution_latency_ms": 9.8
}
```

- **Error Responses:**
  - `400 Bad Request`: Empty cart items list or invalid margin floor parameters.
  - `422 Unprocessable Entity`: Schema validation errors (handled by Pydantic).
  - `500 Internal Server Error`: Safe catch-all returning structured JSON error details without leaking stack traces.

### 5.4 `POST /api/v1/explanation` (Optional Async Gemini Copy)
Enriches the recommendation card with customer-facing explanatory copy.
- **Request Body:**
```json
{
  "target_product_name": "Ergonomic Mechanical Keyboard",
  "recommended_product_name": "Padded Memory Foam Wrist Rest",
  "discount_percentage": 0.10,
  "savings": 2.50,
  "is_discounted": true
}
```
- **Response `200 OK`:**
```json
{
  "personalized_copy": "Upgrade your typing setup! Pair your new keyboard with this wrist rest to prevent strain and save $2.50 today.",
  "model_used": "gemini-1.5-flash",
  "fallback_applied": false,
  "latency_ms": 380.2
}
```
*(If the Gemini API key is missing or the call times out after 1.5s, it returns `fallback_applied: true` with pre-validated deterministic copy).*

### 5.5 `POST /api/v1/simulate`
Executes the reproducible 1,000-session 3-policy simulation comparator.
- **Request Body:**
```json
{
  "num_sessions": 1000,
  "random_seed": 42,
  "margin_floor": 0.20,
  "discount_cap": 0.15
}
```
- **Response `200 OK`:**
```json
{
  "simulation_metadata": {
    "sessions_evaluated": 1000,
    "random_seed": 42,
    "label": "Synthetic Benchmark Simulation"
  },
  "policies": {
    "no_discount": {
      "policy_name": "No Discount (Organic Baseline)",
      "total_contribution_profit": 18240.00,
      "total_incentive_spend": 0.00,
      "conversion_rate": 0.224,
      "average_order_value": 81.42
    },
    "blanket_discount": {
      "policy_name": "Blanket 15% Discount",
      "total_contribution_profit": 15410.50,
      "total_incentive_spend": 4120.00,
      "conversion_rate": 0.281,
      "average_order_value": 73.10
    },
    "faircart_ai": {
      "policy_name": "FairCart AI (Value Optimizer)",
      "total_contribution_profit": 20185.00,
      "total_incentive_spend": 1240.00,
      "conversion_rate": 0.268,
      "average_order_value": 89.20
    }
  }
}
```

---

## 6. Component Architecture & Modular Layout

```text
D:\EthicalEcommerceAI\
├── backend/
│   ├── requirements.txt            # Minimal dependencies: fastapi, uvicorn, pydantic, httpx, numpy
│   ├── .env.example                # GEMINI_API_KEY=
│   ├── scripts/
│   │   └── seed_catalog.py         # Deterministic seed script (20 products)
│   ├── app/
│   │   ├── main.py                 # FastAPI application & router mounting
│   │   ├── config.py               # Settings loader
│   │   ├── db/
│   │   │   ├── database.py         # sqlite3 helper & connection manager
│   │   │   └── repository.py       # CatalogRepository (query products & stock)
│   │   ├── models/
│   │   │   └── schemas.py          # Pydantic v2 schemas for requests & responses
│   │   ├── engine/
│   │   │   ├── recommender.py      # Engine A: Content candidate ranking & affinity scoring
│   │   │   ├── optimizer.py        # Engine B: Margin floor & incremental utility optimizer
│   │   │   └── orchestrator.py     # Engine C: Decision orchestrator
│   │   └── services/
│   │       ├── gemini_service.py   # Asynchronous Gemini client with fallback
│   │       └── simulation_service.py # Deterministic 3-policy simulation generator
│   └── tests/
│       ├── test_financial_invariants.py # Unit tests: margin floor, price ceiling, decimal rounding
│       └── test_api_contracts.py       # Integration tests: FastAPI endpoints & schemas
│
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx                 # Navigation header (Shop Store / Merchant Console)
        ├── types.ts                # TypeScript interfaces matching backend schemas
        ├── api.ts                  # Fetch wrappers for /decision, /catalog, /explanation, /simulate
        ├── components/
        │   ├── Header.tsx          # Branding & view switcher
        │   ├── ProductCard.tsx     # Catalog item card
        │   ├── CartDrawer.tsx      # Cart item list & recommendation container
        │   ├── RecommendationCard.tsx # Transparent offer card with async copy loader
        │   ├── TransparencyModal.tsx  # "How offers work" modal
        │   ├── CheckoutModal.tsx   # Simulated order receipt
        │   └── PolicySlider.tsx    # Slider for margin floor & discount cap
        └── views/
            ├── StorefrontView.tsx  # Customer shopping view
            └── MerchantView.tsx    # Live telemetry & 3-policy simulation
```

---

## 7. Testing & Verification Strategy

All checks run via standard Python `unittest`:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```

### Verified Test Invariants:
1. **Price Ceiling Invariant:** `final_price <= reference_price` across 100 randomly generated discount scenarios. Personalization can never increase prices.
2. **Gross Margin Floor Invariant:** `basket_gross_margin >= configured_margin_floor` for every accepted offer. If an offer would breach the floor, Engine B must return `NO_OFFER`.
3. **Zero Revenue & Invalid Input Handling:** Baskets with zero or negative price inputs must safely return `gross_margin = 0.0` and `NO_OFFER` without division-by-zero exceptions.
4. **No-Offer Recommendation Decoupling:** Recommender returns valid complementary product even when Engine B returns `NO_OFFER`.
5. **Deterministic Simulation Reproducibility:** Running `POST /api/v1/simulate` twice with `random_seed=42` returns identical metrics down to the cent.
6. **Gemini Offline Fallback:** If `GEMINI_API_KEY` is empty, `POST /api/v1/explanation` returns 200 OK with `fallback_applied: true` and pre-validated deterministic copy in < 5 ms.

---

## 8. Decisions and Open Issues

- **DEC-011 (Asynchronous Gemini Decoupling):** Local decision endpoint `POST /api/v1/decision` runs purely locally (<25ms) with deterministic copy. Optional `POST /api/v1/explanation` is called asynchronously by the frontend. Gemini never controls prices or blocks checkout.
- **DEC-012 (Precise Zero-Revenue Safeguards):** Strict conditional formula prevents division-by-zero errors in gross margin calculations.
- **Open Issues:** None. Specification is complete and ready for implementation.
