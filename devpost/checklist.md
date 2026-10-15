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

- [ ] **5. 3-Policy Simulation Comparator (Milestone 5)**
  Becomes usable: Merchant can run a 1,000-session 3-policy simulation comparator directly from the Merchant Console to evaluate No Discount vs Blanket 15% vs FairCart AI with reproducible fixed seeds (`seed=42`).
  Why now: Demonstrates the economic superiority of margin-aware value optimization over blanket discounting.
  PRD ref: `prd.md > Feature F`, `prd.md > View 2`
  Spec ref: `spec.md > 5.5 /simulate`, `spec.md > 6. Component 6`
  Build: Implement `POST /api/v1/simulate` with fixed seeds (`seed=42`); connect simulation runner and metrics visualization in Merchant Console.
  Verify (mechanical): Verify reproducibility of simulation metrics across runs.
  Commit: `Milestone 5: Implement 3-policy economic simulation comparator`

- [ ] **6. Simulated Checkout & End-to-End Verification (Milestone 5)**
  Becomes usable: Shopper can complete simulated zero-payment checkout, receive an order receipt, and reset session.
  Why now: Closes the full shopper loop and completes the proof of concept.
  PRD ref: `prd.md > 1. Shopper Journey (Step 6)`
  Spec ref: `spec.md > 7. Testing Strategy`
  Build: Implement checkout modal and session reset; run comprehensive test pass.
  Verify (mechanical): Run full unittest suite and verify end-to-end journey.
  Commit: `Milestone 5: Implement simulated checkout and verify end-to-end system`

## Hands-on Checkpoints
- [x] Checkpoint 1 (After Slice 1): Verify backend health check and database seeding.
- [x] Checkpoint 2 (After Slice 3): Try shopping in the storefront and verify that margin floors prevent invalid discounts.
- [ ] Checkpoint 3 (After Slice 5): Run the 3-policy simulation and review comparative metrics.
- [ ] Final Review (After Slice 6): Walk through the complete 2-minute demo script before packaging for Devpost.
