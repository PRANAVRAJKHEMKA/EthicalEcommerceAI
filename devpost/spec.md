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

### 3.4 Deterministic Hybrid Recommendation Scoring Formula
For candidate accessory product $p \notin B$, where $B$ is the active shopping basket, $c$ is the active shopping context intent, and $h$ is the anonymous session interaction history, the deterministic hybrid affinity score is:
$$S_{hybrid}(p \mid B, c, h) = 0.30 C(p, B) + 0.30 A(p, B) + 0.20 U(p, c) + 0.15 E(p, h) + 0.05 P(p, B)$$

Where:
1. **Complementarity Component $C(p, B)$:**
   $$C(p, B) = \min\left(1.0, \frac{1}{\sqrt{|B|}} \sum_{b \in B} \operatorname{Comp}(b, p)\right)$$
   where $\operatorname{Comp}(b, p) \in \{0.0, 0.45, 0.50, 0.85\}$ captures direct catalog pairing, subcategory adjacency, and category affinity. Normalization by $\sqrt{|B|}$ rewards multi-item basket support without inflation.
2. **Association Rule Component $A(p, B)$:**
   Evaluated over all antecedent subsets $X \subseteq B$ with $1 \le |X| \le 3$:
   $$A(p, B) = \max_{X \subseteq B, 1 \le |X| \le 3} \left[ r_X \cdot \operatorname{confidence}_{smooth}(X \to p) \cdot L_X \right]$$
   where $r_X = \min\left(1.0, \frac{\operatorname{count}(X)}{\operatorname{minCount}}\right)$, Laplace-smoothed confidence is:
   $$\operatorname{confidence}_{smooth}(X \to p) = \frac{\operatorname{count}(X \cup \{p\}) + 1}{\operatorname{count}(X) + 2}$$
   and bounded logarithmic lift is:
   $$L_X = \frac{\max(0.0, \ln(\operatorname{lift}(X \to p)))}{1.0 + \max(0.0, \ln(\operatorname{lift}(X \to p)))}$$
3. **Context Relevance Component $U(p, c)$:**
   $$U(p, c) = \begin{cases} 0.5 & \text{if } c = \text{'all'} \\ \frac{|K_p \cap K_c|}{|K_p \cup K_c|} & \text{otherwise} \end{cases}$$
   where $K_p$ denotes the product's tags and use-case keywords, and $K_c$ is the keyword set for intent $c$.
4. **Interaction History Component $E(p, h)$:**
   With exponential time decay ($\tau = 24.0$ hours) and event weights $w(\text{cart})=1.0, w(\text{view})=0.3$:
   $$z(p, h) = \sum_{e \in h, e.product = p} w(e.type) \cdot \exp\left(-\frac{\Delta t_e}{\tau}\right)$$
   $$E(p, h) = 0.5 + 0.5 \tanh(z(p, h))$$
5. **Price Fit Component $P(p, B)$:**
   Relative to basket median reference price $m_B$:
   $$P(p, B) = \exp\left(-\frac{|\ln((price_p + 1) / (m_B + 1))|}{1.0}\right)$$

### 3.5 Supervised Machine Learning Ranker (HistGradientBoostingClassifier)
A supervised Gradient Boosted Decision Tree (GBDT) model evaluates candidate products using a 14-dimensional feature vector:
$$\mathbf{x}(p, B, c, h) = [C, A, U, E, P, \operatorname{lift}, \operatorname{conf}, \operatorname{count}, \mathbf{1}_{|B|>1}, N_{matches}, |B|, \text{price}_p, \frac{\text{price}_p}{m_B + 1}, \operatorname{cat\_code}_p]$$
- **Model Architecture:** `HistGradientBoostingClassifier(max_iter=100, learning_rate=0.08, max_leaf_nodes=15, l2_regularization=1.0, random_state=42)`.
- **Training Protocol:** Trained strictly on 1,600 synthetic training sessions (seed=42) with zero test leakage against an independent latent shopper preference simulator.
- **Online Deployment & Model Selection:** In held-out offline testing on 400 sessions, $S_{hybrid} + \text{MMR}$ achieved superior NDCG@4 (0.3018 vs 0.0415) compared to the unconstrained noisy simulator fit. Consequently, $S_{hybrid} + \text{MMR}$ serves as the primary production ranker, with HistGBM maintained as an evaluated alternative (`ranking_mode='ml'`). Sub-millisecond deterministic fallback to $S_{hybrid}$ ensures zero downtime.

### 3.6 Maximal Marginal Relevance (MMR) Diversity Re-ranking
To prevent redundant accessory suggestions (e.g. recommending multiple mousepads or multiple wrist rests), candidate recommendations are selected iteratively using MMR with trade-off parameter $\lambda = 0.75$:
$$\operatorname{MMR}(p) = \arg\max_{p \in C \setminus R} \left[ \lambda \cdot S_{base}(p) - (1 - \lambda) \cdot \max_{r \in R} \operatorname{Sim}(p, r) \right]$$
Where multi-attribute similarity between products $p_1$ and $p_2$ is defined as:
$$\operatorname{Sim}(p_1, p_2) = 0.40 \cdot \mathbf{1}_{\{cat_1 = cat_2\}} + 0.30 \cdot \mathbf{1}_{\{subcat_1 = subcat_2\}} + 0.20 \cdot \operatorname{Jaccard}(tags_1, tags_2) + 0.10 \cdot \left(1.0 - \frac{|price_1 - price_2|}{\max(price_1, price_2, 1)}\right)$$

### 3.7 Empty-Basket Recommendation Anchors & Cold-Start Scoring Model
FairCart AI evaluates recommendations even when the active basket is empty ($B = \emptyset$).

1. **Recommendation Anchor Set $A$:**
   $$A = B \cup V \cup S \cup O$$
   - $B$: Active basket items (weight $w=1.0$)
   - $S$: Saved cart items (weight $w=0.85$, $t_0=1.0\text{h}$)
   - $O$: Historical completed FairCart order items (weight $w=0.75$, $t_0=2.0\text{h}$)
   - $V$: Recent viewed items (weight $w=0.60$, $t_0=0.5\text{h}$)
   
   To prevent view-spamming, each anchor applies a logarithmic repetition dampener:
   $$\text{repetition\_guard} = \min(1.5, 1.0 + 0.2 \cdot \ln(1 + \text{view\_count}))$$
   $$\text{effective\_weight} = w \cdot \exp\left(-\frac{\text{age\_hours}}{24.0}\right) \cdot \text{repetition\_guard}$$

2. **Cold-Start Scoring Formula $S_{\text{cold}}(p \mid c)$:**
   When no anchors exist ($A = \emptyset$), candidate items are scored by a deterministic catalog balance formula:
   $$S_{\text{cold}}(p \mid c) = 0.40 U(p, c) + 0.35 \operatorname{Popularity}(p) + 0.15 \operatorname{Connectivity}(p) + 0.10 P(p, \emptyset)$$
   - $U(p, c)$: Intent use-case alignment (0.50 for general context).
   - $\operatorname{Popularity}(p)$: Catalog transaction frequency baseline.
   - $\operatorname{Connectivity}(p)$: Complement graph degree in catalog ($\frac{|\operatorname{comp}(p)|}{\max_q |\operatorname{comp}(q)|}$).
   - $P(p, \emptyset)$: Price accessibility fit relative to catalog median ($35.00).

3. **Commercial vs Historical Cart Separation:**
   Engine B strictly evaluates discounts based only on active basket $B$. When $B = \emptyset$:
   $$\text{is\_offered} = \text{False}, \quad \text{tier} = \text{"NONE"}, \quad \text{savings} = 0.0, \quad \text{final\_price} = \text{reference\_price}$$
   Items in $A \setminus B$ never trigger unearned promotional discounts.

### 3.8 Three-Policy Economic Simulation Comparator & Paired Evaluation Model
FairCart AI evaluates counterfactual e-commerce outcomes across three distinct pricing policies using paired simulation:
1. **Policies Evaluated:**
   - $\pi_{\text{NO\_DISCOUNT}}$: Organic baseline. Zero promotional markdowns.
   - $\pi_{\text{BLANKET\_15}}$: Indiscriminate 15% promotional discount on all eligible product lines in completed purchases, without margin floor verification.
   - $\pi_{\text{FAIRCART\_AI}}$: Context-aware hybrid recommendation coupled with margin-constrained incentive optimization ($gross\_margin \ge margin\_floor$).

2. **Common Random Numbers (CRN) Paired Evaluation:**
   To guarantee that comparative differences reflect causal policy effects rather than sampling variance, all policies evaluate the identical sequence of synthetic shoppers:
   - Shared seed $S$ (default 42).
   - Paired conversion draw: $u_{\text{conv}} \sim U(0, 1)$.
   - Paired recommendation acceptance draw: $u_{\text{acc}} \sim U(0, 1)$.
   - Identical base conversion propensities $p_{\text{base}}$ and price-elasticity multipliers $\Delta p_{\text{discount}}$.

3. **Shopper Archetype Distribution (9 Archetypes):**
   - Cold-Start Explorer (15%), Browse-Only Researcher (15%), Saved-Cart Returner (10%), Multi-Item Builder (15%), Gaming Enthusiast (10%), Study/Wellness/Travel Context (10%), Inelastic High-Intent (10%), Price-Sensitive Deal Seeker (10%), Low-Margin Discount-Ineligible (5%).

4. **Rigorous Accounting Invariants:**
   - $\text{net\_sales\_revenue} = \text{gross\_sales} - \text{discounts}$
   - $\text{gross\_margin} = \frac{\text{net\_sales} - \text{COGS}}{\text{net\_sales}} \quad (\text{or } 0.0 \text{ if } \text{net} \le 0)$
   - $\text{contribution\_profit} = \text{net\_sales} - \text{COGS} - (\text{completed\_orders} \times \$3.50)$
   - Margin floor violation: recorded whenever an order under policy $\pi$ completes with basket gross margin $< margin\_floor$.
   - 95% Confidence Intervals computed for conversion rates and average contribution profit per session.

---

## 4. Stack & Environment Configuration

### Backend Stack
- **Runtime:** Python `3.12.1` (installed at `C:\Users\LENOVO\AppData\Local\Programs\Python\Python312\python.exe`).
- **Web API:** `FastAPI (0.115.7)` with `uvicorn (0.34.0)`.
- **Validation:** `pydantic (2.10.6)` and `pydantic-settings (2.7.1)`.
- **Database:** Standard library `sqlite3` driver accessing `faircart.db`.
- **External Client:** `httpx (0.28.1)` for asynchronous Gemini API calls.
- **Machine Learning & Math:** `scikit-learn (1.9.1)`, `scipy (1.18.1)`, `numpy (2.2.6)`, and `joblib (1.5.3)` for association mining, feature vector extraction, and gradient-boosted candidate ranking.
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

### 5.5 `POST /api/v1/simulate` & `GET /api/v1/simulate/latest`
Executes or retrieves the reproducible 1,000-session 3-policy simulation comparator.
- **Request Body (`POST /api/v1/simulate`):**
```json
{
  "num_sessions": 1000,
  "random_seed": 42,
  "margin_floor": 0.20,
  "discount_cap": 0.20
}
```
- **Response `200 OK` (`SimulationResponse`):**
```json
{
  "simulation_id": "sim-f22b6a874e",
  "timestamp": "2026-10-15T18:07:01.123456+00:00",
  "version": "1.0",
  "parameters": {
    "num_sessions": 1000,
    "random_seed": 42,
    "margin_floor": 0.20,
    "discount_cap": 0.20,
    "variable_fulfillment_cost_per_order": 3.50
  },
  "active_merchant_settings": {
    "margin_floor": 0.20,
    "discount_cap": 0.20
  },
  "policies": {
    "NO_DISCOUNT": {
      "policy_id": "NO_DISCOUNT",
      "policy_name": "No Discount (Organic Baseline)",
      "description": "Organic shopping behavior with zero promotional markdowns.",
      "sessions_count": 1000,
      "completed_orders_count": 316,
      "conversion_rate": 0.316,
      "conversion_rate_ci_95": [0.2872, 0.3448],
      "average_order_value": 46.99,
      "total_gross_sales": 14849.00,
      "total_net_sales_revenue": 14849.00,
      "total_incentive_expense": 0.00,
      "total_cogs": 6363.00,
      "total_contribution_profit": 7380.00,
      "avg_contribution_profit_per_session": 7.38,
      "avg_contribution_profit_per_session_ci_95": [6.58, 8.18],
      "avg_contribution_profit_per_order": 23.35,
      "total_gross_margin": 0.5714,
      "order_avg_gross_margin": 0.5714,
      "margin_floor_violations_count": 0,
      "margin_floor_violation_rate": 0.0,
      "recommendations_surfaced_count": 0,
      "recommendations_accepted_count": 0,
      "recommendation_acceptance_rate": 0.0
    },
    "BLANKET_15": {
      "policy_id": "BLANKET_15",
      "policy_name": "Blanket 15% Markdown",
      "description": "Fixed 15% promotional discount on eligible completed purchases without margin floor enforcement.",
      "sessions_count": 1000,
      "completed_orders_count": 381,
      "conversion_rate": 0.381,
      "conversion_rate_ci_95": [0.3508, 0.4112],
      "average_order_value": 40.00,
      "total_gross_sales": 17930.00,
      "total_net_sales_revenue": 15240.50,
      "total_incentive_expense": 2689.50,
      "total_cogs": 7696.00,
      "total_contribution_profit": 6211.00,
      "avg_contribution_profit_per_session": 6.21,
      "avg_contribution_profit_per_session_ci_95": [5.61, 6.81],
      "avg_contribution_profit_per_order": 16.30,
      "total_gross_margin": 0.4950,
      "order_avg_gross_margin": 0.4950,
      "margin_floor_violations_count": 46,
      "margin_floor_violation_rate": 0.1207,
      "recommendations_surfaced_count": 0,
      "recommendations_accepted_count": 0,
      "recommendation_acceptance_rate": 0.0
    },
    "FAIRCART_AI": {
      "policy_id": "FAIRCART_AI",
      "policy_name": "FairCart AI (Margin-Constrained)",
      "description": "Context-aware hybrid recommendations with mathematical gross margin floors and discount caps.",
      "sessions_count": 1000,
      "completed_orders_count": 335,
      "conversion_rate": 0.335,
      "conversion_rate_ci_95": [0.3058, 0.3642],
      "average_order_value": 66.86,
      "total_gross_sales": 23762.00,
      "total_net_sales_revenue": 22396.65,
      "total_incentive_expense": 1365.35,
      "total_cogs": 10169.50,
      "total_contribution_profit": 11054.65,
      "avg_contribution_profit_per_session": 11.05,
      "avg_contribution_profit_per_session_ci_95": [9.91, 12.19],
      "avg_contribution_profit_per_order": 33.00,
      "total_gross_margin": 0.5459,
      "order_avg_gross_margin": 0.5459,
      "margin_floor_violations_count": 0,
      "margin_floor_violation_rate": 0.0,
      "recommendations_surfaced_count": 335,
      "recommendations_accepted_count": 210,
      "recommendation_acceptance_rate": 0.6269
    }
  },
  "relative_comparison": {
    "vs_no_discount": {
      "contribution_profit_delta": 3674.65,
      "contribution_profit_pct": 49.79,
      "conversion_rate_delta_pp": 1.90,
      "aov_delta": 19.87,
      "aov_pct": 42.29
    },
    "vs_blanket_15": {
      "contribution_profit_delta": 4843.65,
      "contribution_profit_pct": 77.99,
      "incentive_expense_reduction": 1324.15,
      "incentive_expense_reduction_pct": 49.23,
      "margin_floor_violations_avoided": 46,
      "gross_margin_delta_pp": 5.09
    }
  },
  "dataset_provenance": {
    "methodology": "Paired synthetic simulation evaluated via Common Random Numbers (CRN) across 9 distinct shopper archetypes.",
    "disclaimer": "All figures generated via synthetic simulation with seeded pseudo-random draws. Not live consumer A/B test results. Evaluates algorithmic guardrails and mathematical consistency.",
    "archetype_distribution": {
      "cold_start": 150,
      "browse_only": 150,
      "saved_cart": 100,
      "multi_item_builder": 150,
      "gaming_context": 100,
      "study_wellness_travel": 100,
      "inelastic_high_intent": 100,
      "price_sensitive": 100,
      "low_margin_ineligible": 50
    },
    "total_catalog_products": 32
  },
  "run_metadata": {
    "execution_latency_ms": 1072.4,
    "recommender_mode": "hybrid",
    "optimizer_margin_floor": 0.20,
    "optimizer_discount_cap": 0.20
  }
}
```

### 5.6 `GET / POST /api/v1/settings`
Retrieves or updates active merchant policy parameters (`margin_floor`, `discount_cap`) with SQLite persistence.

### 5.7 `POST / GET / DELETE /api/v1/events`
Anonymous, privacy-preserving session interaction event model (zero PII):
- `POST /api/v1/events`: Records browsing (`product_view`, `search_submitted`, `context_selected`) or purchase intent (`add_to_cart`, `remove_from_cart`, `recommendation_accepted`, `simulated_purchase_completed`).
- `GET /api/v1/events?session_id=...`: Retrieves session history for the active session.
- `DELETE /api/v1/events?session_id=...`: Wipes session events upon cart reset or checkout completion.

---

## 6. Component Architecture & Modular Layout

```text
D:\EthicalEcommerceAI\
├── backend/
│   ├── requirements.txt            # Pinned dependencies: fastapi, uvicorn, pydantic, pydantic-core, httpx, numpy
│   ├── .env.example                # GEMINI_API_KEY=
│   ├── scripts/
│   │   ├── seed_catalog.py         # Deterministic seed script (32 products)
│   │   └── evaluate_recommendations.py # Reproducible offline evaluation on synthetic holdout baskets
│   ├── app/
│   │   ├── main.py                 # FastAPI application, route mounting, & session event handlers
│   │   ├── config.py               # Settings loader
│   │   ├── db/
│   │   │   ├── database.py         # sqlite3 helper, session_events & basket_association_rules schema
│   │   │   └── repository.py       # CatalogRepository (query products, rules, stock, & session events)
│   │   ├── models/
│   │   │   └── schemas.py          # Pydantic v2 schemas for requests, responses, & session events
│   │   ├── engine/
│   │   │   ├── associations.py     # Reproducible synthetic transaction mining (support, confidence, lift)
│   │   │   ├── recommender.py      # Engine A: Whole-basket multi-stage candidate generation & hybrid ranking
│   │   │   ├── optimizer.py        # Engine B: Margin floor & incremental utility optimizer
│   │   │   └── orchestrator.py     # Engine C: Decision orchestrator
│   │   └── services/
│   │       ├── gemini_service.py   # Asynchronous Gemini client with deterministic offline fallback
│   │       └── simulation_service.py # Deterministic 3-policy simulation generator
│   └── tests/
│       ├── test_financial_invariants.py # Unit tests: margin floor, price ceiling, decimal rounding
│       ├── test_api_contracts.py       # Integration tests: FastAPI endpoints & schemas
│       └── test_context_aware_engine.py # Whole-basket synergy, association lift, and offline eval tests
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
