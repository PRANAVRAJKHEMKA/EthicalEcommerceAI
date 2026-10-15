# FairCart AI — Deployment & Persistence Architecture

> **Document Status:** Planning Reference & Architectural Decision Record  
> **Milestone:** Milestone 3B Preparation for Milestone 6 (Ship)  
> **Hackathon Track:** Devpost "Build With AI: Basics"  
> **Deployment Action:** Pre-authorization Architecture Only (Zero public infrastructure provisioned until explicitly authorized)

---

## 1. Executive Summary

FairCart AI is designed to demonstrate an ethical, margin-preserving e-commerce recommendation and incentive platform. This document outlines the technical strategy for public accessibility, cloud hosting, client/server persistence, and security to ensure judges and visitors can reliably experience FairCart AI without configuration friction or performance degradation.

---

## 2. System Topology & Architecture

FairCart AI consists of two distinct components:
1. **Frontend Client:** React 19 single-page application built with Vite and Tailwind CSS.
2. **Backend API:** FastAPI application running Python 3.11/3.12 with SQLite local database and optional Google Gemini 2.5 Flash SDK integration.

```
+-----------------------------------------------------------------------------------+
|                                Client Browser                                     |
|  - React 19 / Vite Single Page Application                                        |
|  - localStorage: Anonymous shopping cart, shopping intent context, dismissals    |
|  - Zero tracking cookies, zero third-party telemetry                              |
+-----------------------------------------------------------------------------------+
                                   |
                  HTTPS / REST API | (Sub-25ms local decisions)
                                   v
+-----------------------------------------------------------------------------------+
|                                FastAPI Backend                                    |
|  - Engine A: Multi-candidate deterministic recommender (affinity + diversity)     |
|  - Engine B: Margin-safe incentive optimizer (margin floor + discount cap)        |
|  - Engine C: Orchestrator & authoritative basket quote calculator                 |
|  - Local SQLite DB (`faircart.db`): 24 curated products + merchant settings      |
|  - Optional Gemini Explanation Endpoint (`/api/v1/explain`)                       |
+-----------------------------------------------------------------------------------+
```

---

## 3. Public Cloud Hosting Options Evaluated

To provide judges with a public URL during the Devpost evaluation period, three hosting topologies were analyzed:

| Hosting Option | Frontend Host | Backend Host | Cold-Start Behavior | Free-Tier Limits | Architectural Complexity |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Option A: Unified Monolith (Recommended)** | Served as static files by FastAPI | **Render / Google Cloud Run / Railway** | ~30s on Render free tier; ~3s on Cloud Run | 750 free hours/month (Render) or \$300 credit (Cloud Run) | **Lowest**: Single origin, zero CORS configuration, single container |
| **Option B: Decoupled Dual-Host** | **Vercel / Netlify / Cloudflare** | **Render / Railway / Fly.io** | Frontend instantaneous; Backend cold start 30–50s on free tier | Vercel free tier generous; backend requires keep-alive ping | **Moderate**: Requires strict CORS configuration & separate deployments |
| **Option C: Serverless Full-Stack** | Next.js on Vercel | Vercel Python Serverless Functions | 2–5s per cold lambda | Ephemeral filesystem prevents persistent SQLite writes | **High / Fragile**: Incompatible with stateful SQLite merchant settings |

### Recommended Deployment Strategy for Milestone 6: Option A (Unified Monolith Container)
- **Container Build:** A multi-stage `Dockerfile` compiles the React frontend (`npm run build`), copies the static `dist/` directory into the FastAPI app directory, and mounts static file routing at `/` while serving API routes at `/api/v1/*`.
- **Primary Advantages:**
  1. **Single Origin:** Eliminates cross-origin resource sharing (CORS) mismatch, third-party cookie blocking, or preflight `OPTIONS` latency.
  2. **Deterministic Seeding:** The container startup script automatically verifies or seeds `faircart.db` with all 24 curated items and default merchant settings.
  3. **Judge Reliability:** If deployed to **Google Cloud Run** or **Render**, the application runs identical code and database state to local development.

---

## 4. Cold-Start Mitigation & Reliability Strategy

Because free cloud container tiers (such as Render or Fly.io) spin down after 15 minutes of inactivity, FairCart AI incorporates specific cold-start mitigations:
1. **Health Check Self-Test:** `/api/v1/health` verifies database read access and returns the item count (`catalog_items_loaded: 24`).
2. **Warm-up Hook / Uptime Monitor:** A lightweight cron job or free uptime pinger (e.g., UptimeRobot, GitHub Actions cron) sends a `GET /api/v1/health` request every 14 minutes during the Devpost judging window to prevent container idling.
3. **Local Fallback for Judges:** A 1-click reproduction script (`start-dev.bat` on Windows or `start-dev.sh` on POSIX) allows judges to run the entire stack locally in under 30 seconds if cloud network access is restricted.

---

## 5. Persistence Architecture & Tradeoffs

### 5.1 Client-Side Persistence (`localStorage`)

FairCart AI deliberately avoids server-side shopper sessions, tracking cookies, or mandatory user accounts. 

- **Storage Key: `faircart_cart`**
  - Stores the shopper's active basket items: `[{ product, quantity, discountedPrice, appliedDiscountPct, appliedCondition }]`.
  - Survives page refreshes, tab closures, and brief network interruptions.
- **Storage Key: `faircart_shopping_context`**
  - Stores the selected shopping intent filter (`all`, `productivity`, `gaming`, `study`, `travel`, `wellness`).
- **Storage Key: `faircart_dismissed_recommendations`**
  - Tracks dismissed candidate IDs so shoppers are not badgered with recommendations they have rejected.
- **Privacy & Ethical Guarantee:**
  - Zero personal identifiable information (PII) is stored.
  - No fingerprinting or cross-site tracking scripts are loaded.

### 5.2 Server-Side Persistence (`SQLite` & Model Artifacts)

- **Database File:** Local `faircart.db` stored in the backend root directory.
- **Write-Ahead Logging (WAL):** Enabled via `PRAGMA journal_mode = WAL` and `PRAGMA synchronous = NORMAL` for high concurrency without database lock contention.
- **Schema Separation (5 Tables):**
  1. `products`: Curated 32-item catalog, metadata, COGS, inventory, complementary connections, tags, use cases.
  2. `merchant_settings`: Dynamic operational parameters (`margin_floor`, `discount_cap`).
  3. `basket_association_rules`: 980 Apriori co-occurrence rules with antecedent subsets, support, raw confidence, Laplace-smoothed confidence ($\alpha=1.0$), and bounded logarithmic lift.
  4. `session_events`: Privacy-preserving anonymous interaction telemetry (`product_view`, `add_to_cart`, `cart_remove`, `search_submitted`, `recommendation_accepted`, `simulated_purchase_completed`) with zero PII and full lifecycle deletion (`DELETE /api/v1/events`).
  5. `simulation_runs`: Stores completed 3-policy simulation comparator results (`run_id`, `timestamp`, `random_seed`, `num_sessions`, `margin_floor`, `discount_cap`, `results_json`, `execution_latency_ms`) indexed by timestamp for immediate retrieval and historical auditability.
- **Machine Learning Model Artifact:**
  - `backend/app/engine/artifacts/ranker_model.joblib` (195 kB): Pre-trained `HistGradientBoostingClassifier` trained on 14 candidate features across 1,600 synthetic shopping sessions. Loaded into memory at application startup (<15ms load time) with automatic deterministic fallback to $S_{hybrid}$.
- **Disk Persistence on Cloud Providers:**
  - On **Google Cloud Run / Render (free)**, disk storage is ephemeral across container restarts. To guarantee catalogue integrity, FairCart AI's application startup automatically runs `seed_catalog.py` if `faircart.db` is missing or contains fewer than 32 items.
  - On **Render with Persistent Disk** or **Railway Volumes**, `faircart.db` can be mounted to a persistent volume path (e.g., `/data/faircart.db`), preserving custom merchant settings across redeployments.

### 5.3 Long-Term Enterprise Migration Path

If scaled to enterprise e-commerce traffic:
- The abstract repository pattern implemented in [`backend/app/db/repository.py`](file:///D:/EthicalEcommerceAI/backend/app/db/repository.py) isolates SQL queries from business logic.
- Migration to managed PostgreSQL (e.g., Supabase, Neon, Cloud SQL) requires swapping the underlying connection pool in `database.py` without modifying Engine A, Engine B, or Engine C.

---

## 6. Security & Environment Configuration

| Variable Name | Purpose | Production Default / Requirement |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini 2.5 Flash API Key for Engine C explanations | Loaded from `.env` or cloud secrets manager. Deterministic fallback active if omitted. |
| `ENVIRONMENT` | Runtime mode selector | `production` (disables debug stack traces) |
| `CORS_ORIGINS` | Allowed origins for cross-domain API calls | In unified container: `["*"]` or same-origin; In decoupled: `["https://faircart-ai.vercel.app"]` |
| `DATABASE_PATH` | Absolute or relative path to SQLite database | `faircart.db` or `/data/faircart.db` |

---

## 7. Pre-Ship Checklist for Deployment Authorization

Prior to executing public deployment in Milestone 6:
- [ ] Backend tests passing (100% test pass rate across foundation, catalog, decision, and simulation suites).
- [ ] Frontend static bundle builds without warnings (`npm run build`).
- [ ] Unified `Dockerfile` validated locally (`docker build -t faircart-ai .`).
- [ ] Secrets hygiene verified (no private API keys, SQLite databases, or local credentials committed to Git).
- [ ] User authorization granted for specific cloud provider selection.
