# FairCart AI — Ethical Commerce Engine

> **Explainable, margin-preserving e-commerce recommendation and incentive optimization engine for responsible commerce.**  
> *Developed for the Devpost "Build With AI: Basics" Hackathon (October 2026).*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.7-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178c6.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38bdf8.svg)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Tests-135%20Passing-brightgreen.svg)]()

---

## 1. What is FairCart AI?

Conventional e-commerce recommendation systems prioritize short-term click-through rate and extraction of consumer willingness-to-pay. This frequently leads to:
1. **Aggressive promotional discounting** that destroys merchant unit margins and cannibalizes organic purchases.
2. **Manipulative dark patterns** (fake urgency countdowns, manufactured scarcity warnings, deceptive reference prices).
3. **Opaque black-box models** that neither shoppers nor merchants can interpret or audit.

**FairCart AI reverses this paradigm.** It optimizes collaborative transaction value and merchant contribution profit under mathematical economic guardrails:
- **Non-bypassable Gross-Margin Floor:** Every discount is evaluated across the entire basket ($\text{Basket Gross Margin} \ge \text{Configured Floor}$).
- **Immutable Reference Price Ceiling:** Personalization can never increase prices above authoritative catalogue reference prices.
- **Hybrid Recommendation Pipeline:** 10-stage recommender combining Apriori basket association rules, session interaction history (views, intentional dwell hovers), context filtering, supervised ranking (`HistGradientBoostingClassifier`), and Maximal Marginal Relevance (MMR) diversity reranking.
- **Dual Explainability:** Generates plain-language customer rationale via Google Gemini (with deterministic sub-5ms offline fallback) while providing merchants with exact mathematical attribution.
- **Three-Policy Economic Simulator:** Monte Carlo comparator evaluating No Discount vs. Blanket 15% Promotion vs. FairCart AI with Common Random Numbers (CRN).

---

## 2. System Architecture

```text
                                  CLIENT BROWSER
                     ┌──────────────────────────────────────┐
                     │   React 19 / Vite Single Page App    │
                     │  - Shopper Storefront (`/`)          │
                     │  - Merchant Console (`/merchant`)    │
                     │  - localStorage: Cart & Intent       │
                     │  - HttpOnly Cookie: Customer Session │
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
                     │  Engine C: Dual Explainability       │
                     │    - Gemini 2.5 Flash + Deterministic│
                     │  Economic Simulator (3-Policy CRN)   │
                     │  Argon2id Authentication & Sessions  │
                     └──────────────────┬───────────────────┘
                                        │
                       ┌────────────────┴────────────────┐
                       ▼                                 ▼
             Local Development                 Production Persistence
          SQLite Database (faircart.db)       Neon Serverless PostgreSQL
          - Deterministic startup seed        - Permanent order history
          - 32 products, 980 rules            - Durable merchant sliders
          - 5 demo accounts, 15 orders        - Zero-cost tier compatible
```

---

## 3. Quickstart & Local Setup

### Prerequisites
- **Python 3.12+**
- **Node.js 20+** and `npm`

### 1. Clone Repository & Setup Backend
```bash
git clone https://github.com/pranavrajkhemka/EthicalEcommerceAI.git
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
# Execute the full backend test suite (131 tests)
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

FairCart AI supports two seamless database persistence modes configured via the `DATABASE_URL` environment variable:

- **Mode 1 — SQLite (Default):**  
  Zero configuration. Uses local `faircart.db`. Automatically seeded on startup with 32 curated products, 980 association rules, 5 demo accounts, and 15 itemized past orders.
- **Mode 2 — Neon Serverless PostgreSQL (Option B):**  
  Configured by setting `DATABASE_URL=postgresql://user:password@ep-xyz.neon.tech/neondb?sslmode=require`.  
  Enables 100% durable persistence of simulated checkouts, merchant policy slider adjustments, and simulation runs across cloud container cold boots. Automatic fallback to SQLite if PostgreSQL is unreachable.

---

## 6. Multi-Stage Production Container (`Dockerfile`)

FairCart AI includes a production Docker container sized for zero-cost deployment on **Render**, **Cloud Run**, or **Hugging Face Spaces**:

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
