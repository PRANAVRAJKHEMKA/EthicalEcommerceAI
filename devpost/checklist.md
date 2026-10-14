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

- [ ] **3. Local Decision Engine & Transparent Offer Card (Milestone 2B)**
  Becomes usable: Adding an item to the cart immediately triggers Engine A & B via `POST /api/v1/decision`, rendering either an eligible bundle discount or standard price card with transparent math.
  Why now: The unique kernel of FairCart AI—relevance + economic margin optimization.
  PRD ref: `prd.md > Feature B, C, D`
  Spec ref: `spec.md > 3. Mathematical Model`, `spec.md > 5.3 /decision`, `spec.md > 6. Component 2, 3, 4`
  Build: Implement Engine A (Recommender), Engine B (Economic Optimizer), Engine C (Orchestrator), and the React `RecommendationCard`.
  Verify (mechanical): Run invariant tests verifying `gross_margin >= floor` and `final_price <= ref_price`.
  Commit: `Milestone 2B: Implement local decision engine and transparent offer card`

- [ ] **4. Asynchronous Gemini Copy & Transparency Modal (Milestone 3)**
  Becomes usable: Recommendation card asynchronously enriches its copy via Gemini, with instant offline template fallback if the key is missing.
  Why now: Delivers responsible AI transparency without blocking the critical commerce path.
  PRD ref: `prd.md > Feature E`
  Spec ref: `spec.md > 5.4 /explanation`, `spec.md > 6. Component 5`
  Build: Implement `POST /api/v1/explanation` with timeout protection and template fallback; add "How offers work" modal.
  Verify (mechanical): Test endpoint with and without `GEMINI_API_KEY`.
  Commit: `Milestone 3: Add asynchronous Gemini explanation service and transparency disclosure`

- [ ] **5. Merchant Console & 3-Policy Simulation (Milestone 4)**
  Becomes usable: Merchant can adjust margin floors in real time, view live decision audit logs, and run a 1,000-session 3-policy simulation comparator.
  Why now: Demonstrates the economic superiority of margin-aware value optimization over blanket discounting.
  PRD ref: `prd.md > Feature F`, `prd.md > View 2`
  Spec ref: `spec.md > 5.5 /simulate`, `spec.md > 6. Component 6 & 8`
  Build: Implement `POST /api/v1/simulate` with fixed seeds (`seed=42`); build Merchant Console view.
  Verify (mechanical): Verify reproducibility of simulation metrics across runs.
  Commit: `Milestone 4: Add merchant console, policy sliders, and 3-policy simulator`

- [ ] **6. Simulated Checkout & End-to-End Verification (Milestone 5)**
  Becomes usable: Shopper can complete simulated zero-payment checkout, receive an order receipt, and reset session.
  Why now: Closes the full shopper loop and completes the proof of concept.
  PRD ref: `prd.md > 1. Shopper Journey (Step 6)`
  Spec ref: `spec.md > 7. Testing Strategy`
  Build: Implement checkout modal and session reset; run comprehensive test pass.
  Verify (mechanical): Run full unittest suite and verify end-to-end journey.
  Commit: `Milestone 5: Implement simulated checkout and verify end-to-end system`

## Hands-on Checkpoints
- [ ] Checkpoint 1 (After Slice 1): Verify backend health check and database seeding.
- [ ] Checkpoint 2 (After Slice 3): Try shopping in the storefront and verify that margin floors prevent invalid discounts.
- [ ] Checkpoint 3 (After Slice 5): Run the 3-policy simulation and review comparative metrics.
- [ ] Final Review (After Slice 6): Walk through the complete 2-minute demo script before packaging for Devpost.
