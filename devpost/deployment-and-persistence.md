# FairCart AI — Deployment & Persistence Architecture

> **Document Status:** Verified Production Architecture & Deployment Specification  
> **Milestone:** Milestone 6 (Ship)  
> **Hackathon Track:** Devpost "Build With AI: Basics" (October 2026)  
> **Deployment Policy:** Pre-authorization Architecture Only (Zero public infrastructure provisioned and zero charges incurred without explicit user authorization)

---

## 1. Executive Summary

FairCart AI is an explainable, margin-preserving e-commerce recommendation and incentive platform. This document specifies the production architecture for public accessibility, cloud containerization, client/server persistence, and security guardrails to ensure judges and visitors can experience FairCart AI with zero setup friction, deterministic performance, and responsible resource boundaries.

---

## 2. System Topology & Architecture

FairCart AI is architected as a cohesive, single-origin full-stack application that can operate as a unified container or decoupled cloud services:

```
+-----------------------------------------------------------------------------------+
|                                Client Browser                                     |
|  - React 19 / Vite Single Page Application                                        |
|  - localStorage: Anonymous shopping cart, shopping intent context, dismissals    |
|  - sessionStorage: Demo-safe administrative access token (never exposed in code)  |
|  - Zero tracking cookies, zero third-party telemetry, zero PII                   |
+-----------------------------------------------------------------------------------+
                                   |
                  HTTPS / REST API | (Sub-25ms local decisions; rate-limited simulation)
                                   v
+-----------------------------------------------------------------------------------+
|                           FastAPI Production Backend                              |
|  - Static SPA Hosting: Serves React dist/ at `/` with HTML5 client-side routing   |
|  - Engine A: Hybrid recommendation engine (30% Co-occ, 30% Intent, 20% View,     |
|              15% MMR Diversity, 5% Pop) with Apriori rules & HistGBM classifier  |
|  - Engine B: Margin-safe incentive optimizer (margin floor + discount cap)        |
|  - Engine C: Dual-mode explanation service (Gemini 2.5 Flash + offline fallback)  |
|  - Economic Simulator: 3-policy Monte Carlo comparator (No Discount, Blanket 15%, |
|                        FairCart AI) with sliding-window IP rate limiting          |
|  - Local SQLite DB (`faircart.db`): Auto-seeded on boot (32 products, 980 rules)  |
+-----------------------------------------------------------------------------------+
```

---

## 3. Public Cloud Hosting Options & Verified Provider Constraints

All provider specifications below have been verified against official platform documentation (accessed October 15, 2026):

| Deployment Architecture | Frontend Host | Backend Host | Database Persistence | Verified Free Tier Constraints (Official Docs, Oct 2026) | Credit Card Required? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Option A: Zero-Cost Unified Container (Recommended)** | Served via FastAPI static mount | **Render Web Service** or **Hugging Face Spaces** | Ephemeral SQLite (`faircart.db`), auto-seeded with 32 items on boot | • Render free web services spin down after 15 min inactivity (~30s cold start).<br>• Local disk is **ephemeral**; custom slider settings reset on restart.<br>• Free tier does **not** support persistent disks (`render.com/docs/disks`).<br>• 750 free instance hours/month. | **No** (Zero cost, no credit card required) |
| **Option B: Zero-Cost Decoupled with Durable Persistence** | **Vercel** (Global Edge CDN) | **Render Web Service** | **Neon Serverless PostgreSQL** (free tier) | • Vercel: 100 GB bandwidth, unlimited deployments.<br>• Neon: 1 GB storage, scale-to-zero, **never expires** (`neon.tech/docs/introduction/free-tier`).<br>• Render PostgreSQL free tier expires after 30 days; Neon does not. | **No** (Zero cost, no credit card required) |
| **Option C: Paid Persistent Cloud Volume** | Served via FastAPI static mount | **Render Starter Plan** or **Fly.io** | Persistent SSD Disk mounted to `/data/faircart.db` | • Render Starter: \$7/month compute + \$0.25/GB/month SSD.<br>• Fly.io: \$1.99/mo base + volume charges.<br>• Guarantees merchant settings and telemetry survive container restarts. | **Yes** (Paid subscription required) |

### Strict Zero-Cost Commitment
> [!IMPORTANT]
> In accordance with project instructions, **zero chargeable resources, paid compute instances, or paid databases will ever be provisioned without explicit user confirmation**. Option A and Option B represent 100% zero-cost paths with no surprise billing risks.

---

## 4. Multi-Stage Container Definition (`Dockerfile`)

A unified multi-stage container has been constructed at [`Dockerfile`](file:///d:/EthicalEcommerceAI/Dockerfile):

```dockerfile
# Stage 1: Build the React 19 SPA
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Minimal Python 3.12 Runtime
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 ENVIRONMENT=production
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt
COPY backend ./backend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

### Container Startup & Resilience
1. **Self-Healing Startup:** On boot, `backend.app.main:startup_event` inspects the catalog count in `faircart.db`. If the database is missing or contains fewer than 32 items, it executes `seed_catalog()` idempotently, restoring all 32 curated products and 980 association rules in <200ms.
2. **Dynamic Port Binding:** Supports container platforms (Render, Cloud Run, Hugging Face) that inject dynamic `$PORT` environment variables.
3. **SPA Content Negotiation:** `GET /` serves discovery JSON to API clients (`Accept: application/json`) and the compiled HTML SPA to web browsers (`Accept: text/html`). Static assets are mounted at `/assets`.

---

## 5. Security Guardrails & Demo-Safe Architecture

To safeguard public deployments against malicious tampering, resource exhaustion, and secret leaks:

1. **Sliding-Window Rate Limiting on Compute Endpoints:**
   - `POST /api/v1/simulate` executes 1,000 Monte Carlo shopping sessions.
   - An in-memory sliding-window limiter restricts each IP address to **max 15 simulations per minute**. Exceeding requests receive `HTTP 429 Too Many Requests`.
2. **Administrative Access Protection:**
   - Modifying merchant guardrails (`POST /api/v1/settings`) can be gated with `ADMIN_TOKEN`.
   - When `ADMIN_TOKEN` is set, calls require `X-Admin-Token` or `Authorization: Bearer <token>`. Unauthenticated requests receive `HTTP 403 Forbidden`.
   - The React frontend stores the administrative token exclusively in `sessionStorage` (cleared upon tab closure), ensuring zero administrative credentials exist in client bundles or Git history.
3. **Environment & Secret Isolation:**
   - All credentials and runtime toggles are defined in [`.env.example`](file:///d:/EthicalEcommerceAI/.env.example).
   - `.env`, `.env.*`, and SQLite database files (`*.db`, `*.sqlite3`) are strictly excluded in [`.gitignore`](file:///d:/EthicalEcommerceAI/.gitignore) and [`.dockerignore`](file:///d:/EthicalEcommerceAI/.dockerignore).
   - `devpost/learner-profile.md` is excluded from Git to protect personal learner context.
4. **CORS Restrictions:**
   - Production mode parses `CORS_ORIGINS` from environment variables, defaulting to local origins and production domains rather than indiscriminate wildcards.

---

## 6. Cold-Start Mitigation & Reliability Strategy

Because free cloud container tiers spin down after 15 minutes of inactivity:
1. **Operational Health Probe:** `/api/v1/health` verifies database connectivity and reports `catalog_items_loaded: 32` in <3ms.
2. **Uptime Monitor (Optional):** A free monitor (e.g., UptimeRobot, cron) pinging `GET /api/v1/health` every 14 minutes prevents container idling during competition judging.
3. **Zero-Configuration Local Reproduction:** Judges can reproduce the entire verified application locally without cloud dependencies:
   - Backend: `uvicorn backend.app.main:app --port 8000`
   - Frontend: `npm run dev` or compiled `npm run preview`
   - Single-command verification: `python -m unittest discover backend/tests` (101 tests pass in ~30s).

---

## 7. Durable Persistence Comparison

| Persistence Layer | Technology | Storage Life | Data Stored | Resets On |
| :--- | :--- | :--- | :--- | :--- |
| **Shopper State** | Browser `localStorage` | Survives refresh & browser reopen | Cart items, intent filter, dismissed recommendations, user-scoped anonymous & authenticated view history | Explicit "Reset Session" button or browser cache clear |
| **Merchant Admin Key** | Browser `sessionStorage` | Session lifetime | `faircart_admin_token` | Tab close |
| **Demo Accounts & Orders** | SQLite (`faircart.db`) | Permanent in repo/auto-seeded | 5 user personas (`users`), Argon2id password hashes, 15 synthetic past orders (`orders`), and simulated checkouts | Never (auto-seeded on startup if empty) |
| **Catalog & Rules** | SQLite (`faircart.db`) | Permanent in repo/auto-seeded | 32 products, 980 association rules, HistGBM model artifact | Never (re-seeded automatically on boot if missing) |
| **Merchant Settings (Option A)** | SQLite (`faircart.db`) | Ephemeral across cold restarts | `margin_floor` (15%), `discount_cap` (20%) | Cold container spin-down (resets to default 15%/20%) |
| **Merchant Settings (Option B/C)** | Neon PostgreSQL or Persistent Disk | Fully durable | `margin_floor`, `discount_cap`, simulation run history | Never (persisted across restarts and deploys) |

---

## 8. Verified Pre-Ship Validation Evidence

| Validation Check | Tool / Mechanism | Result | Evidence Timestamp |
| :--- | :--- | :--- | :--- |
| Backend Automated Tests | Python `unittest` | **118 / 118 tests passing** (0 failures, 0 errors in 80.8s) | 2026-10-15 |
| Frontend Production Build | Vite 6.4.4 + TypeScript 5.7 | **Built cleanly in 8.98s** (0 type errors, gzip: 99.3 kB JS, 6.6 kB CSS) | 2026-10-15 |
| Demo Authentication Security | `test_demo_auth.py` | 5 demo personas, Argon2id verification, 401 on bad password, 429 on 5 failed attempts, 403 on admin escalation | 2026-10-15 |
| Account Order Isolation | `test_account_order_history.py` | 15 synthetic orders, cross-account 404, simulated checkout persistence under authenticated account | 2026-10-15 |
| Personalized Order Anchors | `test_personalized_recommendations.py` | Gamer vs Creator recommendations diverge on empty basket ($O_{gamer} \neq O_{creator}$), zero leakage to guest | 2026-10-15 |
| Pointer Dwell Reliability | `test_hover_reliability.py` & CDP | 700ms dwell contract, touch filtering, internal child boundary protection, stale response sequence guard | 2026-10-15 |
| Content Negotiation | `TestClient(app)` | `Accept: application/json` -> 200 API JSON; `Accept: text/html` -> 200 SPA HTML | 2026-10-15 |
| Simulation Rate Limiter | `TestClient(app)` | 15 requests allowed; 16th returns `HTTP 429` | 2026-10-15 |
| Merchant Admin Guardrail | `TestClient(app)` | Unauthenticated `POST /settings` -> `HTTP 403`; with `X-Admin-Token` -> `HTTP 200` | 2026-10-15 |
| Repository Secret Hygiene | `git ls-files` check | Zero `.env` files, `.db` files, `.local` credential files, or `learner-profile.md` tracked in Git | 2026-10-15 |
