# FairCart AI — Ethical Commerce Engine

> **Explainable, margin-preserving e-commerce recommendation and incentive optimization engine for responsible commerce.**  
> *Developed for the Devpost "Build With AI: Basics" Hackathon (October 2026).*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.7-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178c6.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38bdf8.svg)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Tests-251%20Passing-brightgreen.svg)]()

---

## 1. What is FairCart AI?

Conventional e-commerce recommendation systems prioritize short-term click-through rate and extraction of consumer willingness-to-pay. This frequently leads to:
1. **Aggressive promotional discounting** that destroys merchant unit margins and cannibalizes organic purchases.
2. **Manipulative dark patterns** (fake urgency countdowns, manufactured scarcity warnings, deceptive reference prices).
3. **Opaque black-box models** that neither shoppers nor merchants can interpret or audit.

**FairCart AI reverses this paradigm.** It optimizes collaborative transaction value and merchant contribution profit under mathematical economic guardrails:
- **Expanded Commerce Catalogue & Basket Combinations:** 96 verified products across 15 everyday categories (Desk Peripherals, Workspace, Audio, GaN Power, Pantry & Groceries, Kitchen Cookware, Food Storage, Eco Cleaning, Personal Care, Stationery, and Home Office). Discovers multi-product basket antecedents ($\{A, B\} \to C$) with verified lift while strictly enforcing cross-domain discrimination (e.g. tech peripherals never recommend food items).
- **Fair Deal Passport & Counterfactual Offer Transparency:** Every eligible bundle offer includes an inspectable, deterministic 3-scenario audit report comparing: (1) *No Discount Baseline* (standard catalogue reference price), (2) *FairCart-Approved Offer* (exact customer savings verified against merchant policy), and (3) *Aggressive Alternative* (calculated markdown such as 15% explicitly rejected when breaching active constraints like a 50% margin floor).
- **Shopper Privacy Firewall:** Confidential supplier COGS, raw cost baselines, and merchant dollar profits are strictly redacted from the customer surface, while remaining completely transparent in the Merchant Console inspector.
- **Non-bypassable Gross-Margin Floor & Margin Transparency:** Every discount is evaluated across the entire basket ($\text{Basket Gross Margin} \ge \text{Configured Floor}$). The interface clearly separates **Catalogue Base Margin** (supplier baseline) from **Verified Bundle Margin** (post-discount economics), preventing false alarms on natively low-margin items.
- **Session-Scoped Merchant Policies:** Evaluators and hackathon judges can safely adjust margin floor and discount cap sliders in the Merchant Console via isolated, per-browser session overrides without altering shared global database state or requiring administrative secrets.
- **Cart Quote Alignment & Subtotal Integrity:** Cart drawer and checkout modals strictly verify quote alignment against active basket contents, ensuring accurate line-item totals and avoiding stale or mismatched discount applications.
- **Immutable Reference Price Ceiling:** Personalization can never increase prices above authoritative catalogue reference prices.
- **Hybrid Recommendation Pipeline:** 10-stage recommender combining Apriori basket association rules, session interaction history (views, intentional dwell hovers $\ge 700\text{ms}$), context filtering, supervised ranking (`HistGradientBoostingClassifier`), and Maximal Marginal Relevance (MMR) diversity reranking.
- **Dual Explainability:** Generates plain-language customer rationale via Google Gemini 2.5 Flash when `GEMINI_API_KEY` is configured, with an instant sub-5ms deterministic offline fallback when unconfigured or offline. Merchants receive exact mathematical attribution logs.
- **Three-Policy Economic Simulator:** Monte Carlo comparator evaluating No Discount vs. Blanket 15% Promotion vs. FairCart AI with Common Random Numbers (CRN) across 1,000 synthetic sessions. Designed to validate pipeline mechanics and margin trade-offs; does not claim real-world consumer uplift or live market revenue.
- **Transaction Outcome Intelligence & Offline Causal Uplift Lab (Step 5.19):** First-party anonymous commerce event ledger and offline Two-Model T-Learner causal uplift pipeline comparing targeting strategies (Always Discount vs. Targeted vs. No Discount) using synthetic fixtures based on the Criteo Uplift benchmark schema.
- **Multi-Store Profit Intelligence & Comparative Auditing (Step 5.20):** Backend-authoritative ingestion of order line sales and traffic funnel CSV data across multiple owned storefronts. Aggregates distinct completed orders, net revenue, wholesale COGS, gross profit ($), gross margin %, and observational channel attribution while strictly isolating currencies and rejecting PII. Features automated diagnostic detection for uneconomic discounting subsidies (discounts > 15% with gross margin < 25%) and customer refund leakage.

---

## 2. System Architecture

```text
                                  CLIENT BROWSER
                     ┌──────────────────────────────────────┐
                     │   React 19 / Vite Single Page App    │
                     │  - Shopper Storefront (`/`)          │
                     │  - Merchant Console (`/merchant`)    │
                     │  - localStorage: Cart & Policy State │
                     │  - HttpOnly Cookie: Customer Session │
                     │  - AbortController Request Cancel    │
                     └──────────────────┬───────────────────┘
                                        │
                       HTTPS / REST API │ Sub-25ms synchronous decision pipeline
                                        ▼
                            FASTAPI BACKEND RUNTIME
                     ┌──────────────────────────────────────┐
                     │  Engine A: Hybrid Candidate RecSys   │
                     │    - Apriori Association Rules       │
                     │    - HistGradientBoostingClassifier  │
                     │    - MMR Diversity Reranking         │
                     │  Engine B: Margin-Safe Optimizer     │
                     │    - Margin Floor + Discount Cap     │
                     │    - Session Policy Overrides        │
                     │  Engine C: Dual Explainability       │
                     │    - Gemini 2.5 Flash + Deterministic│
                     │  Economic Simulator (3-Policy CRN)   │
                     │  Argon2id Authentication & Sessions  │
                     │  In-Memory Catalog & Settings Cache  │
                     └──────────────────┬───────────────────┘
                                        │
                       ┌────────────────┴────────────────┐
                       ▼                                 ▼
             Local Development                 Production Persistence
          SQLite Database (faircart.db)       Neon Serverless PostgreSQL
          - Deterministic startup seed        - PostgresConnectionPool
          - 96 products across 15 categories  - Permanent order history
          - Multi-item basket rules           - Connection reuse (250-480ms)
          - 5 demo accounts, 15 orders        - Zero-cost tier compatible
          - Zero-cost tier compatible
```

---

## 3. Quickstart & Local Setup

### Prerequisites
- **Python 3.12+**
- **Node.js 20+** and `npm`

### 1. Clone Repository & Setup Backend
```bash
git clone https://github.com/PRANAVRAJKHEMKA/EthicalEcommerceAI.git
cd EthicalEcommerceAI

# Create and activate Python virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Seed catalogue and demonstration accounts into faircart.db
python backend/scripts/seed_catalog.py
python backend/scripts/seed_demo_accounts.py

# Launch FastAPI development server (port 8000)
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
```

### 2. Setup & Launch Frontend
```bash
# Open a new terminal window
cd frontend
npm install
npm run dev
# Vite runs at http://localhost:5173
```

### 3. Run Automated Tests
```bash
# Execute the full backend test suite (240 tests passing across 15 everyday categories and multi-store intelligence)
python -m unittest discover -s backend/tests -p "test_*.py"

# Verify frontend production build
cd frontend
npm run build
```

---

## 4. Evaluation Demonstration Accounts

For judges and evaluators, FairCart AI includes **five distinct synthetic customer personas**, each with ~3 realistic past itemized orders that personalize empty-basket recommendations:

| Demo Persona | Tag | Shopping Persona & Personalization Focus |
| :--- | :--- | :--- |
| `demo_gamer` | **Gamer** | Esports peripherals, ultra-low latency mice, coiled cables, high-refresh display connectivity |
| `demo_student` | **Student** | Compact study nook, screenbar lighting, laptop stands, posture and eye comfort |
| `demo_creator` | **Creator** | 4K streaming capture cards, boom mic arms, studio acoustics, GaN desktop power |
| `demo_traveler` | **Traveler** | Ultra-compact travel chargers, 65W GaN adapters, tech pouches, braided cables |
| `demo_office` | **Office Pro** | Ergonomic vertical mice, dual-arm monitor mounts, wrist rests, cable management |

> [!TIP]
> **One-Click Demo Sign-In:** Click the **Sign In** button in the top navigation bar. Click any persona chip to inspect their profile and click **Quick Demo Sign-In** to authenticate instantly without manual password entry.

---

## 5. Dual Persistence: SQLite vs. Neon PostgreSQL

FairCart AI supports two database persistence runtimes configured via the `DATABASE_URL` environment variable:

- **Mode 1 — SQLite (Default Local Development):**  
  Zero external configuration. Uses local `faircart.db`. Automatically seeded on startup with 96 curated products across 15 categories, multi-item basket association rules, 5 demo accounts, and 15 itemized past orders. Designed for offline development, local unit tests, and self-contained demonstrations.
- **Mode 2 — Neon Serverless PostgreSQL (Durable Cloud Persistence):**  
  Configured by setting `DATABASE_URL=postgresql://user:password@ep-xyz.neon.tech/neondb?sslmode=require`.  
  Enables permanent persistence of simulated checkouts, merchant policy slider adjustments, and simulation runs across cloud container cold boots.
  - **Connection Pooling & Latency:** Utilizes `PostgresConnectionPool` to eliminate repeated TLS connection overhead to cloud endpoints, keeping query latency between 250–480ms.
  - **Production Fail-Safe Protection:** When production is configured (`ENVIRONMENT=production` or `allow_fallback=False`), a failed PostgreSQL connection raises a `RuntimeError` halting startup or reports `HTTP 503 Service Unavailable` on `/api/v1/health`. It **never** silently switches to ephemeral SQLite in production, ensuring operators are alerted rather than experiencing silent data loss upon container sleep.
  - **Credential Masking:** Connection credentials are automatically scrubbed (`postgresql://***:***@host:port/db`) in all system logs and exceptions.
  - **Permitted Development Fallback:** In non-production development environments where `allow_fallback=True` is explicitly permitted, the engine falls back to local SQLite with a logged warning for offline convenience.

---

## 6. Multi-Stage Production Container (`Dockerfile`)

FairCart AI includes a multi-stage production Docker container sized for zero-cost deployment on **Render**, **Cloud Run**, or **Hugging Face Spaces**:

- **Hosting & Durability Architecture:** Free-tier container hosts (e.g., Render free web services) feature an ephemeral filesystem that resets on container sleep. Pairing the stateless container with **Neon Serverless PostgreSQL** (permanent free tier, 1 GB storage, scale-to-zero) guarantees 100% durable persistence without requiring paid compute plans or persistent disk add-ons.

```bash
# Build the unified container
docker build -t faircart-ai .

# Run container locally on port 8000
docker run -p 8000:8000 -e ENVIRONMENT=production faircart-ai
```

---

## 7. Devpost Hackathon Deliverables

This project was built following the official Devpost **Build With AI: Basics** Learn Skill Pack workflow:

- [`devpost/scope.md`](devpost/scope.md) — Problem framing, unique kernel, economic invariants, and boundary.
- [`devpost/prd.md`](devpost/prd.md) — Product requirements, shopper/merchant core journeys, and state machines.
- [`devpost/spec.md`](devpost/spec.md) — Technical blueprint, 10-stage ranking math, and API contract.
- [`devpost/checklist.md`](devpost/checklist.md) — Verified milestone implementation log.
- [`devpost/app-map.html`](devpost/app-map.html) — Interactive HTML component and route topology visualization.
- [`devpost/judge-notes.md`](devpost/judge-notes.md) — Comprehensive technical review and milestone history.
- [`devpost/submission-readiness.md`](devpost/submission-readiness.md) — Formal submission audit and evidence verification.

---

## 8. License

This project is licensed under the [MIT License](LICENSE).
