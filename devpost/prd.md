---
doc: prd
status: approved
---

# FairCart AI — Product Requirements Document (PRD)

Explainable, margin-preserving e-commerce recommendation and incentive optimization engine for responsible commerce.
Source: `scope.md > The Unique Kernel`, `scope.md > Who It's For`, `scope.md > The Core Loop`.

---

## 1. The Core Journey

The application delivers a single, cohesive web application with two accessible views toggled via a persistent top navigation bar: **Shop Store** and **Merchant Console**.

### Shopper Journey (Storefront)
1. **Catalog Browsing:** Shopper lands on the Storefront and browses a curated catalogue of 20 realistic consumer tech, workspace, and lifestyle products with genuine reference prices, specifications, and inventory availability.
2. **Basket Addition:** Shopper adds a primary item (e.g., *Ergonomic Mechanical Keyboard*, reference price $80.00, wholesale COGS $40.00) to their cart.
3. **Automated Decision Evaluation:** The backend evaluates the session context:
   - **Engine A (Recommendation):** Identifies relevant, in-stock complementary accessories (e.g., *Padded Wrist Rest*, reference price $25.00, wholesale COGS $10.00).
   - **Engine B (Economic Optimization):** Evaluates whether an incentive is permissible under the merchant's gross-margin floor ($G \ge \text{Floor}$) and estimates whether it produces positive incremental contribution utility ($\Delta \text{Contribution} > 0$).
4. **Offer Presentation:**
   - **Eligible Incentive:** A transparent recommendation card appears presenting the *Padded Wrist Rest* with a verified bundle discount (e.g., 10% off the accessory = $2.50 savings, final price $22.50). The card displays original reference price, discount percentage, final price, exact savings, conditions, and a Gemini-generated customer-facing explanation ("Bundle & Save: Paired with your ergonomic keyboard to support healthy typing posture").
   - **No-Offer State:** If offering a discount would breach the gross-margin floor or fail to yield positive incremental utility, the accessory is displayed at its standard reference price ($25.00) with a restrained notice: *"Standard price · No discount applied"* and a factual compatibility reason. No crossed-out prices, artificial urgency, or fake discount badges appear.
5. **Transparency Disclosure:** Shopper can click a discreet *"How recommendations and offers work"* link at any time to open an accessible modal explaining automated offer selection, Gemini copy generation, anonymous session processing, and the strict guarantee that prices are never raised above the base reference price.
6. **Optional Acceptance & Simulated Checkout:** Shopper may accept the recommendation or proceed with only their original item. They click "Simulate Checkout" to view an itemized order summary with total savings and zero payment collection, followed by a one-click "Reset Session" button.

### Merchant Journey (Intelligence Console)
1. **Policy Inspection & Tuning:** Merchant or hackathon judge opens the **Merchant Console** to inspect the live catalog, wholesale COGS, unit margins, and active policy guardrails.
2. **Interactive Controls:** Merchant adjusts the **Minimum Gross Margin Floor** slider (default 20%, range 10%–50%) and **Maximum Discount Cap** slider (default 15%, range 5%–30%).
3. **Live Decision Telemetry:** Console displays real-time decision logs showing incoming session requests, Engine A candidate scores, Engine B margin checks, exact financial arithmetic, fallback status, and decision reasons.
4. **Honest 3-Policy Simulation:** Merchant triggers the built-in simulation runner to evaluate 1,000 reproducible synthetic shopper sessions comparing:
   - **Policy 1:** No Discount (baseline organic purchases)
   - **Policy 2:** Blanket 15% Discount (promotional price-cutting)
   - **Policy 3:** FairCart AI (margin-constrained, targeted value optimization)
   The console displays honest, unmanipulated metrics: Total Contribution Profit ($), Incentive Expense ($), Simulated Conversion Rate (%), and Average Order Value ($), explicitly labelled as simulated benchmark results.

---

## 2. Screens and Layout

A single responsive web application with two core views:

### View 1: Shopper Storefront (`/`)
- **Top Header:** Branding ("FairCart AI — Ethical Commerce"), session status pill ("Anonymous Session Active"), "How offers work" transparency link, Cart drawer toggle button with item badge, and View Switcher toggle ("Shop Store" / "Merchant Console").
- **Product Grid:** Responsive 3-to-4 column grid displaying 20 catalog products with product image placeholder, category badge, title, short description, reference price, stock status, and "Add to Cart" button.
- **Cart Drawer / Slide-Over:** Displays current basket items with quantity controls, unit price, line totals, subtotal, shipping fee calculation, and:
  - **Complementary Recommendation Card:** Positioned prominently inside the drawer. Displays recommended item image, title, transparent price breakdown, plain-language reason, and a single "Add to Cart" button.
  - **Checkout Summary:** Subtotal, discount applied, final total, and a "Simulate Checkout (Demo)" button.
- **Transparency Modal:** Accessible modal dialog detailing FairCart AI's ethical principles, anonymous session processing, and anti-price-discrimination policy.
- **Simulated Checkout Modal:** Order confirmation showing itemized receipt, applied savings, and session reset action.

### View 2: Merchant Intelligence Console (`/merchant`)
- **Policy Control Bar:** Sliders and inputs for Gross Margin Floor (%) and Max Discount Cap (%).
- **Live Decision Inspector (Audit Log):** Table showing the latest session decisions: Session ID, Target Item, Recommended Item, Decision (`OFFER_APPLIED` vs. `NO_OFFER`), Basket Margin %, Savings $, and Execution Latency.
- **3-Policy Comparative Simulation Panel:** Side-by-side comparison cards for No Discount, Blanket 15%, and FairCart AI, displaying Contribution Profit, Conversion Rate, Incentive Spend, and AOV, with a "Re-run Simulation" button.
- **System Health & Latency Metric Strip:** Status badges showing Database Status, Local Decision Latency (p50/p95 ms), and Gemini API Connection / Fallback Mode.

---

## 3. Look and Feel
- **Visual Style:** Minimalist, high-contrast, modern commerce UI inspired by Shopify Polaris, Stripe, and Linear.
- **Palette:** Slate/zinc neutrals (`#0f172a`, `#f8fafc`), deep emerald accent for ethical savings (`#059669`), and calm indigo for interactive elements (`#4f46e5`).
- **Typography:** Clean system sans-serif (Inter/SF Pro).
- **Prohibited Elements:** Flashing red banners, countdown clocks, artificial "Only 1 left in stock!" tags, or manipulative pop-up overlays.

---

## 4. Features and Behavior

### Feature A: Product Catalog & Cart Management
- **Description:** 20 coherent consumer electronics and lifestyle products with established wholesale costs (COGS), base reference prices, and complementary relationships.
- **User Story:** As a shopper, I want to add items to my cart and see exact price totals update instantly.
- **Acceptance Criteria:**
  - Adding an item increments cart count and recalculates subtotal accurately.
  - Removing an item recalculates subtotal and triggers re-evaluation of recommendations.
  - Quantities and prices maintain 2-decimal precision without rounding drift.

### Feature B: Recommendation Engine (Engine A)
- **Description:** Evaluates cart contents against catalog metadata to retrieve relevant, in-stock complementary accessories with cold-start fallbacks.
- **User Story:** As a shopper, I want to see helpful accessories compatible with my selected products.
- **Acceptance Criteria:**
  - When keyboard is in cart, compatible wrist rest or desk mat is recommended.
  - Items already present in the cart are never recommended.
  - Out-of-stock items are excluded from candidate generation.
  - Outputs are labelled as "Affinity Scores", not purchase probabilities.

### Feature C: Economic Incentive Optimization (Engine B)
- **Description:** Evaluates permissible actions against the merchant's gross margin floor and incremental contribution utility.
- **User Story:** As a merchant, I want to ensure that no discount ever causes a basket's gross margin to fall below my configured floor.
- **Acceptance Criteria:**
  - Evaluates: $\text{Basket Gross Margin} = \frac{\text{Net Revenue} - \text{Total COGS}}{\text{Net Revenue}} \ge \text{Configured Floor}$ when $\text{Net Revenue} > 0$. If $\text{Net Revenue} \le 0$ or input is invalid, returns margin 0.0 and `NO_OFFER`.
  - If margin satisfies the floor and estimated incremental utility $> 0$, an eligible bundle discount (e.g., 5% or 10%) is applied.
  - If margin would breach the floor or utility $\le 0$, the engine returns `NO_OFFER`.
  - Final price can never exceed the base reference price under any circumstance.
  - The backend is the sole authority on all financial calculations.

### Feature D: Transparent Shopper Disclosure & No-Offer Handling
- **Description:** Displays the recommendation clearly, whether discounted or at standard price.
- **User Story:** As a shopper, I want to know why an item is recommended and understand the exact pricing breakdown.
- **Acceptance Criteria:**
  - On eligible discount: displays Reference Price, Discount %, Final Price, Savings $, and reason.
  - On `NO_OFFER`: displays standard Reference Price with *"Standard price · No discount applied"* and a factual compatibility note.
  - No fake crossed-out prices or deceptive promotional tags on undiscounted recommendations.
  - Shopper can proceed to checkout with or without accepting the recommendation.

### Feature E: Gemini API Explanation & Copy Generation
- **Description:** Server-side Gemini integration generates customer-facing explanatory copy and offer text asynchronously, decoupled from the critical decision path.
- **User Story:** As a shopper, I want a natural, clear explanation of why an accessory pairs well with my purchase.
- **Acceptance Criteria:**
  - Primary decision endpoint returns immediately (<25ms) with deterministic copy; Gemini copy is fetched asynchronously without blocking checkout or cart updates.
  - Calls Gemini model server-side using environment-configured API key.
  - Never passes private customer data or allows Gemini to alter financial amounts.
  - If Gemini call fails, times out, or API key is absent, the deterministic template fallback copy is displayed without failing the decision.
  - Local decision path latency is measured independently of Gemini response time.

### Feature F: Merchant Console & 3-Policy Simulation
- **Description:** Administrative view providing real-time auditability and reproducible policy simulations.
- **User Story:** As a merchant or hackathon evaluator, I want to compare FairCart AI against standard discounting policies on consistent synthetic data.
- **Acceptance Criteria:**
  - Evaluates 1,000 synthetic shopping sessions using fixed random seeds (`seed=42`).
  - Reports Contribution Profit ($), Incentive Spend ($), Simulated Conversion (%), and AOV ($) across all 3 policies.
  - All simulation results are clearly labelled as synthetic benchmark data.
  - Margin floor and discount cap sliders dynamically adjust backend policy thresholds.

---

## 5. States and Boundaries

- **First Use / Cold Start:** Empty cart shows a clear empty state with a call to browse the catalogue; when an item is first added without interaction history, Engine A uses deterministic popularity-weighted category affinity.
- **No-Offer State:** Recommended complementary product displayed with *"Standard price · No discount applied"*, preserving recommendation value without financial distortion.
- **Zero-Candidate State:** If all complementary items are out of stock or already in the cart, the recommendation card gracefully collapses with no blank gaps.
- **Gemini Offline / Fallback State:** Backend serves pre-validated deterministic explanation copy; system health badge in Merchant Console indicates "Fallback Mode Active".
- **Session Reset:** One-click reset wipes client session storage and backend session cache, restoring initial clean demo state.

---

## 6. Product Decisions

1. **Single Application, Two Dedicated Views:** Decided to host Storefront and Merchant Console within one responsive app with top navigation, ensuring immediate demonstration without multi-site setup friction.
2. **Decoupled Recommendation and Incentive:** Decided that a `NO_OFFER` decision does not suppress a valid recommendation; the item is shown at its standard price with full transparency.
3. **Deterministic Backend Authority:** Decided that all pricing, discounts, and margins are computed exclusively by Python backend logic; Gemini is strictly limited to natural language copy generation.
4. **Honest Simulation Labeling:** Decided that all 3-policy evaluation metrics are explicitly labelled as simulated synthetic benchmarks, preserving ethical credibility.
5. **Anonymous Ephemeral Sessions:** Decided to use client-generated UUIDs without collecting email, name, or payment details.

---

## 7. What We're Building (Proof of Concept)
- 20-product catalog in embedded SQLite with COGS, reference prices, and complementary relationships.
- Complete React (TypeScript + Vite + Tailwind) storefront with catalog, cart drawer, and simulated checkout.
- FastAPI backend implementing Engine A, Engine B, Engine C, and `/api/v1/decision`.
- Server-side Gemini API integration with offline deterministic fallback.
- Merchant Console with policy sliders, decision audit logs, and reproducible 3-policy simulation.
- Automated tests verifying financial invariants (gross margin floor, reference price ceiling, decimal arithmetic).

## 8. Deferred From the POC
- Multi-merchant tenancy and persistent merchant logins (out to keep local demo friction-free).
- Live Stripe / Shopify webhook payment processing (out to avoid payment overhead and real transactions).
- Deep neural collaborative filtering models (out to preserve explainability and sub-100ms local latency).

## 9. Non-Goals
- Will NOT collect or store customer PII, credit cards, or tracking cookies.
- Will NOT support personalized upward price markups (base price is an immutable ceiling).
- Will NOT use deceptive countdown timers, fake stock counts, or artificial urgency triggers.
- Will NOT require paid cloud infrastructure to execute.
