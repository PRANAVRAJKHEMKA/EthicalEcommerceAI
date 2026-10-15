---
doc: checklist
status: approved
---

# Build Checklist

Build mode: learn

## Slices

- [x] **1. Foundation, Database & Operational Health (Milestone 1)**
  Becomes usable: A running backend server with `/api/v1/health` verifying database connectivity and a seeded 20-product catalogue, accompanied by automated tests.
  Why now: Establishes a verifiable, reproducible foundation on Windows so every subsequent slice has a stable data and API layer to build on.
  PRD ref: `prd.md > 1. The Core Journey`, `prd.md > Feature A`
  Spec ref: `spec.md > 3. Stack`, `spec.md > 4. Where It Runs`, `spec.md > 5.1 /health`, `spec.md > 6. Component 1`
  Build: Initialize virtual environment, install backend requirements, build SQLite catalog repository, write deterministic seed script (20 products), create FastAPI app with `/api/v1/health`, scaffold minimal frontend structure, write unit tests.
  Verify (mechanical): Run `seed_catalog.py`, run `python -m unittest discover -s backend/tests`, query `GET /api/v1/health` and verify 20 items loaded.
  Learner check: Verify the health endpoint returns 20 items loaded and the test suite passes on your machine.
  Commit: `Milestone 1: Establish foundation, SQLite catalog, health API, and unit tests`

- [x] **2. Catalog API & Shopper Storefront Scaffold (Milestone 2A)**
  Becomes usable: Shopper can view the 20 products in the React storefront, add them to the cart drawer, and view line totals.
  Why now: Connects frontend to backend with real data before adding recommendation intelligence.
  PRD ref: `prd.md > 2. Screens and Layout > View 1`, `prd.md > Feature A`
  Spec ref: `spec.md > 5.2 /catalog`, `spec.md > 6. Component 1 & 7`
  Build: Implement `GET /api/v1/catalog`, create Vite/React storefront with product cards, cart drawer, Tailwind CSS entrypoint, and responsive typography/spacing.
  Verify (mechanical): Query `GET /api/v1/catalog`, verify React dev server loads products cleanly, inspect visual layout in desktop/mobile viewports via CDP screenshots.
  Commit: `Milestone 2: Catalog API and interactive shopper storefront with verified visual styling`

- [x] **3. Local Decision Engine & Transparent Offer Card (Milestone 3)**
  Becomes usable: Adding an item to the cart immediately triggers Engine A & B via `POST /api/v1/decision`, rendering either an eligible bundle discount or standard price card with transparent math.
  Why now: The unique kernel of FairCart AI—relevance + economic margin optimization.
  PRD ref: `prd.md > Feature B, C, D`
  Spec ref: `spec.md > 3. Mathematical Model`, `spec.md > 5.3 /decision`, `spec.md > 6. Component 2, 3, 4`
  Build: Implement Engine A (Recommender), Engine B (Economic Optimizer), Engine C (Orchestrator), and the React `RecommendationCard`.
  Verify (mechanical): Run invariant tests verifying `gross_margin >= floor` and `final_price <= ref_price`.
  Commit: `Milestone 3: Local decision engine, margin-preserving optimizer, and transparent offer card`

- [x] **3B. Multi-Recommendation, Consistent Pricing, & Context-Aware Optimization (Milestone 3B)**
  Becomes usable: Storefront offers 3–5 diverse complementary recommendations per basket, user-controlled shopping intent context (productivity, gaming, study, travel, wellness), authoritative basket quote API, and 100% price agreement across catalogue cards, recommendation cards, cart drawer, and checkout receipt.
  Why now: Corrects pricing drift, eliminates single-item recommendation fatigue, and guarantees complete financial consistency across the shopper journey.
  PRD ref: `prd.md > Feature B, C, D`
  Spec ref: `spec.md > 5.3 /decision, /quote`, `spec.md > 6. Component 2, 3, 4`
  Build: Expand catalog to 24 items with tags/use cases; upgrade Engine A with category/subcategory diversity; upgrade Engine B for independent candidate evaluation; implement authoritative `POST /api/v1/quote`; author `devpost/deployment-and-persistence.md`; wire `localStorage` cart persistence; verify with 7 CDP browser screenshots.
  Verify (mechanical): Run 26/26 backend unit tests, build frontend production bundle (`tsc -b && vite build`), verify CDP screenshots of 4 UI touchpoints.
  Commit: `Milestone 3B: Multi-recommendation, consistent pricing, and context-aware optimization`

- [x] **4. Product Experience Refinement, Persistent State, Gemini Explanations & Recovery (Milestone 4)**
  Becomes usable: Storefront expanded to 32 products with category-accurate photos; persistent localStorage state across refreshes (cart, intent, dismissed IDs); automatic revocation of bundle discounts when prerequisite items are removed; asynchronous Gemini explanation service (`POST /api/v1/explanation`) with attribute-grounded copy, 3.5s timeout, response caching, sub-5ms deterministic offline fallback, and strict financial immutability; full transparency disclosure modal (`TransparencyModal.tsx`); interactive Merchant Console with active policy sliders (`margin_floor`, `discount_cap`) persisted to SQLite; uvicorn reload isolation (`--reload-dir backend`) and explicit binary dependency pinning (`pydantic-core==2.27.2`).
  Why now: Delivers responsible AI transparency without blocking the critical commerce path, fixes runtime reload instabilities, guarantees reliable cross-session state, and equips the merchant console with active policy guardrails.
  PRD ref: `prd.md > Feature E, F`, `prd.md > View 2`
  Spec ref: `spec.md > 5.4 /explanation`, `spec.md > 5.6 /settings`, `spec.md > 6. Component 5 & 8`
  Build: Seed 32 catalog items; implement `GeminiExplanationService`; mount `POST /api/v1/explanation` and `GET/POST /api/v1/settings`; create `TransparencyModal.tsx`; update `MerchantView.tsx` with active sliders; wire discount revocation in `App.tsx`; isolate Uvicorn file watcher; pin `pydantic-core==2.27.2`.
  Verify (mechanical): Run 33/33 backend unit tests, build frontend production bundle (`tsc -b && vite build`), test live endpoints (`/health`, `/catalog`, `/explanation`, `/settings`), verify live browser behavior with 5 Edge CDP screenshots.
  Commit: `Milestone 4: Product experience refinement, persistent state, Gemini explanations, and runtime recovery`

- [x] **4B. Hybrid Recommendation Intelligence, Association-Rule Mining, Contextual ML Ranking, and MMR Diversity (Milestone 4B)**
  Becomes usable: Full 10-stage hybrid recommendation pipeline integrating interaction events, historical baskets, association rules, feature generation, deterministic hybrid ranking ($0.30 C + 0.30 A + 0.20 U + 0.15 E + 0.05 P$), supervised ML ranking (`HistGradientBoostingClassifier`), and MMR diversity-aware re-ranking ($\lambda=0.75$); Apriori association mining with Laplace-smoothed confidence ($\alpha=1.0$) and bounded logarithmic lift; 14-feature contextual candidate representation; rigorous offline evaluation on 400 held-out test sessions (+484% HitRate gain, +759% NDCG gain, 100% catalog coverage, diversity similarity reduced to 0.1235); ultra-low decision latency (mean 3.80ms, p95 5.98ms, <25ms SLA); full backend test suite pass (61/61 tests); clean frontend production build.
  Why now: Advances recommendation intelligence beyond static pairing into a principled, context-aware, multi-signal ranking system that prevents accessory fatigue, avoids duplicate recommendations via MMR, and strictly safeguards merchant margins.
  PRD ref: `prd.md > Feature B, C, D`, `prd.md > View 1`
  Spec ref: `spec.md > 3. Mathematical Model`, `spec.md > 5.7 /events`, `spec.md > 6. Component 2, 3, 9`
  Build: Upgrade `associations.py` (Apriori up to size 4, antecedent size $\le 3$, Laplace smoothing, bounded lift, synthetic sessions with zero test leakage); implement `ml_ranker.py` (14 candidate features, `HistGradientBoostingClassifier`, `SyntheticShopperSimulator` for ground-truth label generation, sub-millisecond fallback); upgrade `recommender.py` ($S_{hybrid}$ exact formula, multi-attribute MMR diversity re-ranking, rich grounded factual reasons); update `orchestrator.py` (session event integration, Engine B independence); expand offline evaluation `evaluate_recommendations.py`; add automated math and ranking tests.
  Verify (mechanical): Run 61/61 backend tests, verify offline metrics benchmark (HitRate@4: Baseline 0.0625 -> Hybrid 0.3650, NDCG@4: Baseline 0.0351 -> Hybrid 0.3018), compile frontend bundle (`tsc -b && vite build` in 2.48s), benchmark decision latency (3.80ms mean).
- [x] **4C. Empty-Basket Recommendations, Historical Personalization & Cold-Start Intelligence (Milestone 4C)**
  Becomes usable: FairCart AI recommends relevant products before the shopper adds anything to the cart; explicit recommendation-anchor model $A = B \cup V \cup S \cup O$ decoupling recommendation generation from active basket while strictly maintaining commercial separation (zero promotional discounts when active cart is empty); deterministic cold-start formula $S_{\text{cold}}(p \mid c) = 0.40 U(p, c) + 0.35 \operatorname{Popularity}(p) + 0.15 \operatorname{Connectivity}(p) + 0.10 P(p, \emptyset)$ with honest provenance copy ("Popular picks from our catalogue"); dynamic view tracking and reset session capability in frontend; 76/76 backend tests passing; clean frontend build; 3 Edge CDP screenshots verified.
  Why now: Eliminates the blank-screen cold-start discovery barrier while guaranteeing that shoppers cannot unlock unearned bundle discounts without an active purchase cart.
  PRD ref: `prd.md > Feature B, C, D`, `prd.md > View 1`
  Spec ref: `spec.md > 3.7 Empty-Basket & Cold-Start`, `spec.md > 5.3 /decision`
  Build: Implement `RecommendationAnchor` dataclass and $S_{\text{cold}}$ formula in `recommender.py`; upgrade `orchestrator.py` to evaluate anchors and enforce reference pricing on empty cart; update `schemas.py` and `types.ts`; wire view tracking and reset session in `App.tsx` and `StorefrontView.tsx`; write `test_empty_basket_recommendations.py` covering all 15 scenarios; capture 3 CDP screenshots.
  Verify (mechanical): Run 76/76 backend unit tests, compile frontend (`tsc -b && vite build` in 2.44s), verify CDP screenshots (`screenshot_m4c_cold_start.png`, `screenshot_m4c_context_based.png`, `screenshot_m4c_view_based.png`).
  Commit: `feat(recsys): Milestone 4C empty-basket recommendations, historical personalization, and cold-start fallback`

- [x] **5. 3-Policy Simulation Comparator (Milestone 5)**
  Becomes usable: Merchant can run a 1,000-session 3-policy simulation comparator directly from the Merchant Console to evaluate No Discount vs Blanket 15% vs FairCart AI with reproducible fixed seeds (`seed=42`) using paired Common Random Numbers (CRN) across 9 archetypes.
  Why now: Demonstrates the economic superiority of margin-aware value optimization over blanket discounting and provides empirical proof of margin-floor preservation.
  PRD ref: `prd.md > Feature F`, `prd.md > View 2`
  Spec ref: `spec.md > 5.5 /simulate`, `spec.md > 6. Component 6`
  Build: Implement `POST /api/v1/simulate` with paired CRN evaluation, 9 shopper archetypes, exact accounting formulas, 95% confidence intervals, and SQLite persistence (`simulation_runs` table); implement `GET /api/v1/simulate/latest`; build interactive simulation controls, side-by-side policy cards, SVG visual comparison charts, and comprehensive metrics table in `MerchantView.tsx`.
  Verify (mechanical): Run 13 dedicated simulation unit tests in `test_simulation_engine.py` (all passing), verify identical seed-42 outputs, verify Blanket 15% margin floor violations, compile frontend bundle (`tsc -b && vite build`), capture live Edge CDP screenshots.
  Commit: `feat(simulation): Milestone 5 three-policy economic simulation comparator and merchant intelligence console`

- [x] **5B. Frequency-Aware Interaction Signals & Deliberate Product Detail Inspection (Milestone 5B)**
  Becomes usable: Repeated legitimate product views carry monotonically increasing, time-decayed weight ($z_p$ formula with $\tau=24.0$h); intentional hover dwell threshold ($\ge 900$ms) isolates genuine interest from incidental pointer swipes; duplicate event idempotency (`INSERT OR IGNORE` with unique client `event_id`); accessible `ProductDetailModal.tsx` for deliberate inspection emitting authentic `product_view` events; bounded tanh transformation $E(p, h) \in [0.5, 1.0)$ guaranteeing repeat interactions cannot hijack recommendations; 101/101 backend unit tests passing; clean frontend build; Edge CDP real-browser verified.
  Why now: Replaces binary visit tracking with nuanced, tamper-resistant behavioral signals without compromising sub-25ms latency or merchant margin guardrails.
  PRD ref: `prd.md > Feature B, C, D`, `prd.md > View 1`
  Spec ref: `spec.md > 3.4 Interaction Scoring`, `spec.md > 5.7 /events`
  Build: Update `recommender.py` with $z_p$ decay and bounded $E(p, h)$; upgrade `repository.py` and `main.py` for idempotent event ingestion; create `ProductDetailModal.tsx`; update `ProductCard.tsx` with 900ms pointer dwell timer and episode tracking; wire async session recording in `App.tsx` and `StorefrontView.tsx`; write `test_frequency_aware_signals.py` (12 tests); execute CDP real browser verification (`verify_m5b_browser.cjs`).
  Verify (mechanical): Run 101/101 backend unit tests, compile frontend (`tsc -b && vite build` in 10.71s), verify Edge CDP real-browser automation steps and screenshots (`screenshot_m5b_quick_view_modal.png`, `screenshot_m5b_frequency_recommendations.png`).
  Commit: `feat(interactions): Milestone 5B frequency-aware interaction signals, product hover, and deliberate view modal`

- [x] **6. Simulated Checkout & End-to-End Verification (Milestone 5 & 5B)**
  Becomes usable: Shopper can complete simulated zero-payment checkout, receive an itemized order receipt, reset session, and observe continuous synchronization across all 4 UI touchpoints, SQLite persistence, and offline fallbacks.
  Why now: Closes the full shopper loop and completes the proof of concept ahead of deployment and Devpost submission.
  PRD ref: `prd.md > 1. Shopper Journey (Step 6)`
  Spec ref: `spec.md > 7. Testing Strategy`
  Build: Complete checkout modal with itemized pricing, transparent savings breakdown, and zero-payment disclosure; full backend test pass (101/101 tests passing); CDP screenshot verification across Storefront, Merchant Console, and Decision Engine.
  Verify (mechanical): Run full 101-test suite in `python -m unittest discover -s backend/tests`, verify zero TypeScript errors, verify live backend and frontend server connectivity.
  Commit: `feat(simulation): Milestone 5 three-policy economic simulation comparator and merchant intelligence console`

- [x] **7. Public Deployment Architecture, Containerization & Devpost Release Candidate (Milestone 6)**
  Becomes usable: Unified multi-stage `Dockerfile` (Node 20 + Python 3.12 slim), self-healing database seeding on startup, compute endpoint sliding-window IP rate limiting (15/min on `/api/v1/simulate`), demo-safe session administrative token for merchant guardrail modification (`POST /api/v1/settings`), content-negotiated SPA serving, verified zero-cost cloud deployment guide (`devpost/deployment-and-persistence.md`), and complete competition submission storyboard and judge notes in `devpost/judge-notes.md`.
  Why now: Delivers a competition-ready, secure, reproducible release candidate without incurring cloud charges or exposing administrative credentials.
  PRD ref: `prd.md > 1. System Topology`, `prd.md > Security`
  Spec ref: `spec.md > 4. Where It Runs`, `deployment-and-persistence.md`
  Build: Author `Dockerfile`, `.dockerignore`, `.env.example`; implement sliding-window rate limiting on `POST /api/v1/simulate`; gate `POST /api/v1/settings` with `ADMIN_TOKEN`; update `MerchantView.tsx` with session-safe admin key input; update `deployment-and-persistence.md` and `judge-notes.md`.
  Verify (mechanical): Run full 101 backend unit tests (100% pass), build frontend production bundle (`tsc -b && vite build` in 4.26s), test rate limiter (15 ok, 1 429), test admin auth (403 unauth, 200 auth), audit git secret hygiene (0 secrets in git).
  Commit: `feat(ship): Milestone 6 public deployment architecture, containerization, and security guardrails`

- [x] **8. Demo Authentication, Account-Specific Order History, Personalized Anchors & Reliable Hover Tracking (Milestone 6B)**
  Becomes usable: 5 distinct customer demonstration accounts (`demo_gamer`, `demo_student`, `demo_creator`, `demo_traveler`, `demo_office`) with Argon2id password hashing and brute-force rate limiting; 15 itemized synthetic past orders across personas; account-specific past orders act as authenticated historical order anchors ($A = B \cup V \cup S \cup O$) tailored to persona habits with zero cross-account leakage; simulated checkout persistence under active user account; user-scoped localStorage and cart isolation; reliable pointer dwell tracking (700ms threshold, touch rejection, internal child boundary protection, unmount/visibility cancellation); stale asynchronous decision response discard guard; Login modal with quick-select demo chips and show/hide password toggle; Order History modal with item details, savings, and anchor explanation; 118/118 backend unit tests passing; clean frontend build; 4 live Edge CDP screenshots verified.
  Why now: Provides evaluators with an authentic multi-account experience and itemized order history without manual data entry, while correcting hover tracking reliability and cross-account isolation.
  PRD ref: `prd.md > 1. System Topology`, `prd.md > Account & History`
  Spec ref: `spec.md > 5.8 /auth, /orders`, `devpost/deployment-and-persistence.md`
  Build: Add `users`, `user_sessions`, and `orders` tables in SQLite; implement `auth.py` (Argon2id, session tokens, sliding-window rate limit); implement `seed_demo_accounts.py`; mount `/api/v1/auth/login`, `/me`, `/logout`, `/demo-personas`, `/orders`; update `orchestrator.py` to anchor on user purchased product IDs; update `ProductCard.tsx` with 700ms dwell, pointer events, and child transition safety; build `LoginModal.tsx` and `OrderHistoryModal.tsx`; update `Header.tsx` and `App.tsx` with cart isolation and stale response guard; write 4 test suites (17 new tests); capture 4 CDP screenshots.
  Verify (mechanical): Run 118/118 backend unit tests (100% pass), build frontend bundle (`tsc -b && vite build` in 8.98s), execute browser CDP journey (`verify_m6b_browser.cjs`), verify secret hygiene (`.local/demo-credentials.local.md` gitignored).
  Commit: `feat(auth): Milestone 6B demo authentication, account order history, and reliable hover tracking`

## Hands-on Checkpoints
- [x] Checkpoint 1 (After Slice 1): Verify backend health check and database seeding.
- [x] Checkpoint 2 (After Slice 3): Try shopping in the storefront and verify that margin floors prevent invalid discounts.
- [x] Checkpoint 3 (After Slice 5): Run the 3-policy simulation and review comparative metrics.
- [x] Checkpoint 4 (After Slice 5B): Verify intentional hover dwell thresholds and deliberate modal views in live browser.
- [x] Checkpoint 5 (After Slice 8 / M6B): Verify multi-account login, order history anchors, persona differentiation, and reliable 700ms pointer dwell tracking in live browser CDP.
- [x] Final Review (After Slice 6/7/8): Walk through the complete 2-minute demo script before packaging for Devpost.

## Code Tour and App Map
- [x] Completed architectural review, system data flow diagram, and self-contained HTML app map in `devpost/app-map.html`.

