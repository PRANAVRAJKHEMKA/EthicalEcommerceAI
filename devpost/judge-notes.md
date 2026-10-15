# FairCart AI — Judge Notes & Project Decision Log

**Hackathon:** Devpost Build With AI: Basics  

**Target Deadline:** October 26, 2026, 5:00 PM ET (October 27, 2026, 2:30 AM IST)  

**Maintained Continuously Across:** Scope → PRD → Spec → Build → Testing → Ship



---



## 1. Confirmed Decisions Log



### DEC-001: Focus on Transaction Value Optimization over Price Extraction

- **What We Decided:** Optimize recommendations and incentives for incremental merchant contribution profit while offering legitimate savings, rather than estimating maximum consumer willingness-to-pay to extract the highest price.

- **Why We Decided It:** Solves the ethical dilemma of dynamic price discrimination and profit-cannibalizing blanket discounts.

- **Alternatives Considered:** Standard e-commerce personalization (frequently uses surge pricing and countdown timers). Rejected as manipulative and predatory.

- **Impact:** Core algorithms in Engine B maximize $E[\Delta \text{Contribution}]$ subject to margin floors, rather than maximizing revenue at consumer expense.

- **How to Explain to Judges:** "Most e-commerce AI tries to figure out the highest price you're willing to pay. FairCart AI flips that: it finds products you'll genuinely like and only offers a discount if the store can afford it without losing money."

- **Status:** **Confirmed & Approved (in Scope & PRD)**.



---



### DEC-002: Cohesive Single Web Application with Two Dedicated Views

- **What We Decided:** Build one unified web application featuring a persistent top navigation bar toggling between **Shop Store** (`/`) and **Merchant Console** (`/merchant`), sharing a single FastAPI backend and SQLite database.

- **Why We Decided It:** Keeps demonstration seamless for judges without requiring two distinct running servers or confusing multi-tab setups, while maintaining strict architectural boundaries.

- **Alternatives Considered:** Two completely separate frontend repositories/apps. Rejected due to setup friction and redundant code.

- **Impact:** Unified React frontend with client-side routing; shared backend API; immediate side-by-side verification during live demos.

- **How to Explain to Judges:** "Judges can experience FairCart AI as a normal customer in the Storefront, then click one button to peek behind the curtain in the Merchant Console to see the live math and AI decisions."

- **Status:** **Confirmed & Approved (in PRD)**.



---



### DEC-003: Decoupled Recommendation (Engine A) and Incentive Optimization (Engine B)

- **What We Decided:** Engine A (product relevance) and Engine B (economic incentive) operate independently. If an accessory is relevant and in-stock, it is displayed even if Engine B returns `NO_OFFER`.

- **Why We Decided It:** A good recommendation provides customer value even at standard price. Suppressing recommendations whenever discounts aren't viable deprives shoppers of useful accessory discovery.

- **Alternatives Considered:** Only recommending products when a discount can be given. Rejected because it trains shoppers to expect discounts and hides relevant products.

- **Impact:** When `NO_OFFER` occurs, UI displays the product at standard reference price with a restrained *"Standard price · No discount applied"* label and factual compatibility note. No fake crossed-out prices or banners.

- **How to Explain to Judges:** "Just because a store can't afford a discount doesn't mean it shouldn't suggest a helpful accessory. We recommend the right product regardless, and only discount when the economics work."

- **Status:** **Confirmed & Approved (in PRD)**.



---



### DEC-004: Deterministic Backend Authority for Financial Invariants

- **What We Decided:** All financial calculations, price ceilings, discount percentages, and gross margin floors are computed exclusively by deterministic Python backend logic. Gemini is strictly confined to generating natural language explanations and copy.

- **Why We Decided It:** Large Language Models can hallucinate, produce non-deterministic math, or be prompted to bypass financial constraints. The business logic must be mathematically foolproof.

- **Alternatives Considered:** Asking the LLM to decide the discount percentage or calculate the margin. Rejected as dangerous and unreliable for commerce.

- **Impact:** Backend API acts as an uncompromisable gatekeeper. Pydantic schemas validate all outputs. Automated unit tests enforce financial boundaries.

- **How to Explain to Judges:** "We never let a generative AI touch store prices or discounts. Our Python engine does the hard math and margin checks, and Gemini simply explains the decision in friendly, natural language."

- **Status:** **Confirmed & Approved (in Scope & PRD)**.



---



### DEC-005: Offline-Resilient Gemini Fallback Architecture

- **What We Decided:** Implement a server-side Gemini integration with an automatic, deterministic local template fallback if the API key is missing, rate-limited, or offline.

- **Why We Decided It:** Ensures that network issues, missing API keys, or upstream outages never break the storefront or block a customer checkout during testing or evaluation.

- **Alternatives Considered:** Blocking the checkout until Gemini responds, or hard-failing without an API key. Rejected because core commerce must never fail due to an auxiliary copy service.

- **Impact:** Merchant console displays "Gemini Connected" vs "Fallback Mode Active" telemetry badge. Local decision latency is decoupled from LLM latency.

- **How to Explain to Judges:** "If the internet drops or an API key isn't provided, FairCart AI doesn't crash—it seamlessly uses built-in smart templates so the store keeps running."

- **Status:** **Confirmed & Approved (in Scope & PRD)**.



---



### DEC-006: Hard Consumer Protection Invariants

- **What We Decided:**

  1. **Reference Price Ceiling:** $\text{Final Personalized Price} \le \text{Base Reference Price}$. Personalization can never raise prices.

  2. **Basket Gross Margin Floor:** $\text{Basket Gross Margin} = \frac{\text{Net Revenue} - \text{COGS}}{\text{Net Revenue}} \ge \text{Configured Floor}$.

  3. **Anti-Dark-Patterns:** No fake urgency countdowns, false scarcity alerts, or manufactured original prices.

  4. **Data Minimization:** Zero PII collected; anonymous ephemeral UUID session tokens only.

- **Why We Decided It:** Embeds core responsible AI principles directly into the code contracts rather than treating ethics as a superficial disclaimer.

- **Alternatives Considered:** Relying on frontend warnings or terms-of-service disclaimers. Rejected because code-enforced guardrails are verifiable.

- **Impact:** Unit test suite explicitly asserts these mathematical invariants across all edge cases (empty cart, low margin products, invalid inputs).

- **How to Explain to Judges:** "Our code makes price gouging mathematically impossible: a customer's personalized price can never exceed the base price, and store margin floors are hard-coded in the backend."

- **Status:** **Confirmed & Approved (in Scope & PRD)**.



---



### DEC-007: Transparent Labeling of Simulated Metrics vs Real Results

- **What We Decided:** All 3-policy simulation benchmarks (No Discount vs. Blanket 15% vs. FairCart AI) must be explicitly labelled as simulated synthetic benchmarks with documented assumptions and fixed random seeds (`seed=42`).

- **Why We Decided It:** Prevents misleading claims about real-world conversion rates or ROI that cannot be verified from synthetic hackathon data.

- **Alternatives Considered:** Claiming FairCart AI increases conversion by 25% based on demo results. Rejected as unsubstantiated and dishonest.

- **Impact:** Merchant console and Devpost submission materials clearly state: "Simulated benchmark results on 1,000 synthetic shopping sessions."

- **How to Explain to Judges:** "We believe in honest AI. Our 3-policy comparison uses reproducible math and synthetic sessions to demonstrate the concept without making unverified claims about real-world conversion."

- **Status:** **Confirmed & Approved (in Scope & PRD)**.



---



### DEC-008: SQLite Embedded Database with Python's Built-in sqlite3 & Repository Pattern

- **What We Decided:** Store the 20-product catalogue in a local SQLite file (`faircart.db`) managed via Python's standard library `sqlite3` driver with a clean, decoupled Repository pattern (`CatalogRepository`), seeded deterministically via `backend/scripts/seed_catalog.py`.

- **Why We Decided It:** Ensures zero external database installation, runs natively on Windows without Docker or external services, provides sub-millisecond local query latency, and keeps SQL queries explicit, clean, and educational.

- **Alternatives Considered:** SQLAlchemy ORM, PostgreSQL, or client-side JSON files. Rejected ORM/PostgreSQL due to package overhead and Windows configuration complexity; rejected raw JSON because relational indexing, constraints, and transactions are vital for commerce data integrity.

- **Impact:** Complete isolation of database access from business logic. SQLite file ignored in `.gitignore` while deterministic seed script recreates the database cleanly on any checkout.

- **How to Explain to Judges:** "Instead of requiring a complicated cloud database or external server, FairCart AI uses Python's built-in SQLite engine. It boots up instantly on any computer with zero configuration, runs queries in less than a millisecond, and is completely reproducible."

- **Status:** **Confirmed & Approved (in Spec)**.



---



### DEC-009: Standardized Engine Nomenclature (Engine A, B, C)

- **What We Decided:** Establish strict, uniform nomenclature across all documentation, source code, and judge presentations:

  - **Engine A — Recommender:** Content-based candidate generation and affinity scoring.

  - **Engine B — Economic Incentive Optimizer:** Constrained utility maximization and gross margin floor enforcement.

  - **Engine C — Decision Orchestrator:** Validates requests, coordinates Engines A & B, calls Gemini with fallbacks, and enforces response contracts.

- **Why We Decided It:** Eliminates ambiguity and ensures that both technical evaluators and the learner have a crystal-clear mental model of the pipeline stages.

- **Alternatives Considered:** Merging recommendation and discount calculations into one black-box function. Rejected because decoupling relevance from economic viability is FairCart AI's central architectural thesis.

- **Impact:** Direct modular mapping in `backend/app/engine/`: `recommender.py` (Engine A), `optimizer.py` (Engine B), and `orchestrator.py` (Engine C).

- **How to Explain to Judges:** "Engine A finds the right product. Engine B checks if the store can afford a discount. Engine C ties them together with an explanation."

- **Status:** **Confirmed & Approved (in Spec)**.



---



### DEC-011: Asynchronous Decoupling of Gemini Copy from Critical Decision Path

- **What We Decided:** `POST /api/v1/decision` is a purely local, synchronous endpoint executing in < 25ms, returning the product recommendation, financial numbers, margin checks, and a deterministic fallback explanation. If Gemini is configured, the frontend calls a separate endpoint `POST /api/v1/explanation` asynchronously to replace only the copy text.

- **Why We Decided It:** Prevents external LLM latency (typically 400ms–2000ms) or API outages from blocking customer checkout or slowing down cart operations.

- **Alternatives Considered:** Calling Gemini synchronously inside the decision endpoint. Rejected because external network delays would violate our sub-100ms decision benchmark and crash if the API key is missing.

- **Impact:** Shopper gets instantaneous cart feedback. Local decision latency is measured cleanly and independently from Gemini latency.

- **How to Explain to Judges:** "We never make an e-commerce checkout wait for an AI language model. Our local decision engine does the math instantly, and Gemini runs in the background to provide a friendly, personalized sentence."

- **Status:** **Confirmed & Approved (in Spec)**.



---



### DEC-012: Strict Zero-Revenue and Invalid-Input Mathematical Safeguards

- **What We Decided:** Enforce that $\text{gross\_margin} = \frac{\text{net\_sales\_revenue} - \text{COGS}}{\text{net\_sales\_revenue}}$ strictly when $\text{net\_sales\_revenue} > 0$. If $\text{net\_sales\_revenue} \le 0$ or any price/cost input is missing, the engine safely returns $\text{gross\_margin} = 0.0$ and forces action $\text{NO\_OFFER}$.

- **Why We Decided It:** Eliminates division-by-zero crashes (`ZeroDivisionError`) and guarantees that free, negative-priced, or corrupt items cannot be exploited.

- **Alternatives Considered:** Allowing negative margins to pass to utility calculations. Rejected because negative margins violate the merchant's fundamental solvency constraints.

- **Impact:** Robust unit test coverage for edge cases (zero price, negative quantity, corrupt catalog items).

- **How to Explain to Judges:** "We built mathematical air-tightness into the financial formulas. If an item has invalid data or zero price, the engine immediately shuts down discounts to protect the store from glitches or exploits."

- **Status:** **Confirmed & Approved (in Spec)**.



---



### DEC-013: Direct Virtual Environment Python Executable Invocations on Windows

- **What We Decided:** Document and execute all backend commands via `.\.venv\Scripts\python.exe -m ...` instead of relying on PowerShell script activation (`activate.ps1`).

- **Why We Decided It:** Windows PowerShell execution policy frequently blocks `.ps1` script execution (`Execution_Policies`), causing unexpected setup friction for judges. Invoking the virtual environment's Python binary directly works 100% reliably regardless of system execution policy.

- **Alternatives Considered:** Running `Set-ExecutionPolicy RemoteSigned -Scope Process`. Rejected because it requires elevated user permissions and can still fail on managed machines.

- **Impact:** Rock-solid, reproducible run commands documented in README and Spec.

- **How to Explain to Judges:** "To make sure our project runs flawlessly on any Windows computer without permission errors, we invoke the local virtual environment Python directly."

- **Status:** **Confirmed & Approved (in Spec)**.



---



### DEC-014: Explicit SQLite Connection Closure to Prevent Windows File Locking

- **What We Decided:** Ensure that all database access in `CatalogRepository`, `init_db()`, and CLI seed scripts wraps connection handling in explicit `try ... finally: conn.close()` blocks rather than relying on Python's `with sqlite3.connect(...)` alone.

- **Why We Decided It:** In Python's standard `sqlite3` library, the context manager `with conn:` only manages transaction commit/rollback; it does **not** close the connection handle. On Windows, unclosed handles retain OS-level file locks that trigger `WinError 32 (The process cannot access the file because it is being used by another process)` during re-seeding or database recreation.

- **Alternatives Considered:** Using a long-lived global singleton connection. Rejected because multi-threaded FastAPI workers sharing a single raw SQLite connection can lead to thread-safety errors (`sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`).

- **Impact:** Complete elimination of Windows file-locking errors across all backend endpoints, test cases, and seeding tools.

- **How to Explain to Judges:** "Windows treats open file handles very strictly. We wrote our database repository with bulletproof connection teardown so our SQLite database never locks up during live testing or grading."

- **Status:** **Implemented & Tested (in Milestone 2)**.



---



### DEC-015: Entrypoint CSS Pipeline Hookup & Visual Layout Verification

- **What We Decided:** Create `frontend/src/index.css` declaring `@tailwind base; @tailwind components; @tailwind utilities;`, import it directly in `frontend/src/main.tsx`, configure font families (Inter and JetBrains Mono) in `index.html` and `tailwind.config.js`, enforce fixed aspect ratios (`h-44 object-cover`) across all product cards, and implement automated visual verification using headless Edge via Chrome DevTools Protocol (CDP).

- **Why We Decided It:** Solved a critical visual defect where the storefront rendered unstyled with default browser typography, raw unstyled buttons, and massive full-resolution unconstrained images. Although `tailwindcss` and `postcss.config.js` were present in the repo, Vite's PostCSS pipeline was never invoked because no CSS file containing `@tailwind` directives existed or was imported into `main.tsx`.

- **Beginner-Friendly Explanation (Why builds succeed while styling is broken):** Compilers like `tsc` (TypeScript) and bundlers like `vite build` only check whether source files contain valid JavaScript syntax and whether modules can be packaged. If a CSS stylesheet is omitted from the import tree, the compiler considers that completely valid (many libraries have no CSS). The build exits cleanly with code 0 and bundles 0 CSS bytes. Without inspecting the actual rendered page in a browser, a "successful build" is completely blind to missing stylesheets and visual layout defects.

- **Alternatives Considered:** Loading Tailwind via CDN `<script>` tag. Rejected because production builds should use pre-compiled, tree-shaken CSS bundles (`dist/assets/*.css`) rather than runtime CDN parsers.

- **Impact:** Production Vite build now compiles and outputs a dedicated, tree-shaken ~25 kB CSS bundle (`dist/assets/*.css`). All 20 product cards render with identical vertical geometry, crisp typography, responsive category navigation, and full cart drawer styling.

- **How to Explain to Judges:** "A clean code build only proves the syntax is valid—not that the store looks good to customers. We caught and fixed a missing CSS entrypoint, then verified our visual design using real browser screenshots across desktop and mobile devices."

- **Status:** **Implemented & Tested (in Milestone 2)**.

---

### DEC-016: Decision Engine Implementation, Integer-Cent Precision, and Option 1 Fallback

- **What We Decided:**
  1. Built Engine A (`recommender.py`), Engine B (`optimizer.py`), and Engine C (`orchestrator.py`) under `backend/app/engine/`.
  2. Implemented Option 1 behavior: when Engine B returns `NO_OFFER` due to margin floor constraints, Engine A continues recommending the compatible accessory at standard reference price with the restrained disclosure *"Standard price · No discount applied"*, zero crossed-out prices, and zero artificial pressure.
  3. Enforced integer-cent arithmetic (`reference_price_cents`, `cogs_cents`) internally across domain entities and optimizer math to eliminate floating-point rounding errors and division-by-zero crashes.
  4. Enforced strict financial invariants:
     - Basket gross margin floor: $\text{gross\_margin} \ge \text{margin\_floor}$ across the entire affected basket.
     - Price ceiling: $\text{final\_price} \le \text{reference\_price}$.
     - Non-negative customer savings: $\text{savings} \ge 0$.
     - Boundary protections: zero or negative prices safely force $\text{NO\_OFFER}$ and $0.0$ margin.
     - Non-double-counting of discounts in contribution profit calculations.
  5. Mounted `POST /api/v1/decision` with synchronous, 100% local execution (< 25ms SLA, measured ~3.5ms).
  6. Implemented `RecommendationCard.tsx` in React with two distinct visual states (Bundle Deal with savings badge vs. Standard Price with factual disclosure), "Why this item?" expandable transparency drawer, and wired it into both Storefront and Cart Drawer.

- **Why We Decided It:** Solves the core e-commerce dilemma of either offering margin-cannibalizing blanket discounts or offering nothing. Keeps customer recommendations useful and relevant while ensuring the merchant never loses money on unprofitable incentives.

- **Alternatives Considered:**
  - Hiding the recommendation entirely when no discount is eligible. Rejected because the shopper benefits from seeing compatible accessories (Option 1).
  - Floating-point prices (`float`). Rejected due to IEEE-754 rounding inaccuracies (`$19.999999999999996`).

- **Impact:** 21/21 backend tests passing (including margin floor bounds, discount cap caps, zero revenue guards, and latency benchmarks). Frontend builds cleanly and displays live bundle discounts ($20.00 instead of $25.00, saving $5.00) in both the Storefront and the Cart Drawer.

- **How to Explain to Judges:** "When you add a mechanical keyboard to your cart, FairCart AI doesn't give you a blanket 15% off everything. It finds the matching wrist rest, checks if the store can afford a 20% discount without violating its 20% gross margin floor, and shows you the math right in the cart drawer. If the store can't afford a discount, it still recommends the item at standard price without fake countdowns or pressure."

- **Status:** **Implemented & Tested (in Milestone 3)**.

---

### DEC-017: Multi-Candidate Complementary Recommendations, End-to-End Consistent Pricing, and Context-Aware Intent Ranking

- **What We Decided:**
  1. **Multi-Candidate Complementary Recommendations:** Upgraded Engine A (`recommender.py`) to return 3–5 diverse complementary recommendations per cart state, enforcing category/subcategory diversity so shoppers receive a balanced set of complementary choices (e.g., cables, wrist rests, keycaps, and stands) rather than duplicate items from a single category.
  2. **End-to-End Authoritative Pricing Consistency:** Established the FastAPI backend as the single authoritative source of financial truth. When an item qualifies for a bundle deal, the exact same final price, savings amount, percentage discount, and conditions are displayed across all four UI touchpoints: the catalogue card (`ProductCard`), the recommendation card (`RecommendationCard`), the cart drawer line item (`CartDrawer`), and the checkout receipt modal (`CheckoutModal`). No React component performs independent pricing math.
  3. **Independent Candidate Incentive Optimization:** Engine B (`optimizer.py`) independently evaluates each recommendation candidate against merchant gross margin floors and discount caps. Items that satisfy merchant constraints receive bundle savings; items that would violate margin floors are presented transparently at standard reference price with "Standard price · No discount applied".
  4. **Context-Aware Intent Ranking Without Tracking:** Enriched all 24 catalogue items with `subcategory`, `tags`, and `use_cases`. Added a user-controlled Shopping Intent context selector (`all`, `productivity`, `gaming`, `study`, `travel`, `wellness`) on the storefront. Intent matching awards an explainable +0.25 affinity boost without invasive tracking cookies, third-party trackers, or personal data collection.
  5. **Authoritative Basket Quotes (`/api/v1/quote`):** Created a dedicated integer-cent quote calculation engine that returns exact line totals, subtotals, bundle savings, and basket gross margin for any cart state and applied discounts.
  6. **Deployment & Persistence Planning:** Authored `devpost/deployment-and-persistence.md` detailing public accessibility options (unified container vs decoupled hosts) and persistence architecture (localStorage client state + local SQLite DB with WAL mode).

- **Why We Decided It and What Problem It Solves:**
  - Solves the pricing discrepancy where recommendation cards showed discounted prices while the corresponding catalogue cards still displayed standard prices, eliminating shopper confusion.
  - Solves recommendation fatigue caused by single-item suggestions by providing 3–5 diverse options tailored to the shopper's active setup intent.
  - Solves the cold-start intent problem ethically by providing user-selected intent filters rather than invasive surveillance.

- **Alternatives Considered:**
  - *Client-side price calculation in React:* Rejected because floating-point drift and separate business logic in the browser cause rounding discrepancies and destroy financial auditability.
  - *Single-candidate recommendations:* Rejected because shoppers frequently reject the first recommendation; 3–5 diverse candidates significantly increase relevance without cluttering the UI.
  - *Browser cookies or user tracking:* Rejected in alignment with FairCart AI's ethical commerce mission.

- **Impact:**
  - Catalogue expanded to 24 items in SQLite with full tag and use-case metadata.
  - 26/26 backend automated unit tests passing in 0.22s.
  - Frontend production build succeeds cleanly (`tsc -b && vite build`) in 9.1s.
  - 7 comprehensive browser screenshots verified via Chrome DevTools Protocol.

- **How to Explain to Judges:**
  "In typical e-commerce, recommendations either push a single high-margin item or blanket-discount the entire store. In FairCart AI, when you add a mechanical keyboard, Engine A finds 3 to 4 diverse complements—from wrist rests to coiled cables and laptop stands—aligned with your chosen shopping setup. Engine B checks each one individually against store profit margins. And crucially, whatever bundle price FairCart offers is guaranteed identical whether you look at the recommendation card, the catalogue grid, your cart drawer, or your final receipt. Everything is calculated in exact cents by the backend with zero dark patterns."

- **Status:** **Implemented & Tested (in Milestone 3B)**.

---

## 2. Pending Decisions

- **PEN-001 (Spec Stage):** Specific Scikit-Learn Model architecture for purchase propensity ranking (Heuristic Baseline for MVP; scikit-learn classifier designed as optional pluggable extension).

- **PEN-003 (Build Stage):** Exact Gemini model selection (`gemini-1.5-flash` or `gemini-2.0-flash` for fastest sub-second copy generation).



---



## 3. Latest System Architecture



```text

[ Shopper Browser (Storefront) ]  <--->  [ React + Vite + Tailwind UI ]

[ Merchant Browser (Console)   ]  <--->  [ React + Vite + Tailwind UI ]

                                                   |

                             +---------------------+---------------------+

                             | (Sync: <25ms)                             | (Async: Optional)

                             v                                           v

                 POST /api/v1/decision                      POST /api/v1/explanation

                             │                                           │

                             ▼                                           ▼

                 [ FastAPI Backend Gateway ]                     [ Gemini Service ]

                             │                                   - Customer copy

            +----------------+----------------+                  - Offline fallback

            ▼                                 ▼                          │

 [ Engine A: Recommender ]       [ Engine B: Optimizer ]                 │

 - Content matching              - Basket margin floor (>=20%)           │

 - Affinity scoring              - Incremental utility                   │

            │                                 │                          │

            +----------------+----------------+                          │

                             ▼                                           │

                 [ Engine C: Orchestrator ]                              │

                 - Authoritative decision                                │

                 - Deterministic copy                                    │

                 - Telemetry log (faircart.db)                           │

                             │                                           │

                             ▼                                           ▼

                 [ Immediate Cart Update ] <─────────────────────────────+

```



---



## 4. Feature Traceability & Implementation Status

| Feature | Scope / PRD Ref | Implementation State | Verification State |
| :--- | :--- | :--- | :--- |
| **Realistic 24-Product Catalog** | PRD §4.A | **Implemented (SQLite)** | **Passed (Seeded 24 items with tags & use cases)** |
| **Catalog Repository Layer** | Spec §6.1 | **Implemented** | **Passed (6 Unittest checks)** |
| **Operational Health API (`/api/v1/health`)**| Spec §5.1 | **Implemented (FastAPI)** | **Passed (HTTP 200 Schema Check: 24 items)** |
| **Catalog API (`/api/v1/catalog`)** | Spec §5.2 | **Implemented (FastAPI)** | **Passed (5 Unittest checks)** |
| **Interactive Cart & Drawer** | PRD §4.A | **Implemented (React)** | **Passed (State & UI verified with localStorage)** |
| **Storefront & Category Filters** | PRD §2 (View 1) | **Implemented (React)** | **Passed (Dynamic categories & search)** |
| **Shopping Intent Context Selector** | PRD §4.B | **Implemented (React)** | **Passed (Productivity, Gaming, Study, etc.)** |
| **Simulated Zero-Payment Checkout** | PRD §1.6 | **Implemented (React Modal)** | **Passed (Itemized receipt & reset verified)** |
| **Merchant Console Scaffold** | PRD §2 (View 2) | **Implemented (React Preview)** | **Passed (Catalog stats & sliders)** |
| **Engine A: Multi-Candidate Recommender** | PRD §4.B | **Implemented (`recommender.py`)** | **Passed (3-5 ranked candidates with diversity)** |
| **Engine B: Margin-Constrained Optimizer** | PRD §4.C | **Implemented (`optimizer.py`)** | **Passed (Independent candidate evaluation)** |
| **Engine C: Decision API (`/api/v1/decision`)**| PRD §4.C | **Implemented (`orchestrator.py`)** | **Passed (Synchronous < 25ms SLA)** |
| **Authoritative Basket Quotes (`/api/v1/quote`)**| Spec §5.3 | **Implemented (`orchestrator.py`)** | **Passed (Exact cents line totals & margin)** |
| **End-to-End Consistent Pricing** | PRD §4.D | **Implemented (Frontend & Backend)** | **Passed (Verified across 4 UI touchpoints)** |
| **Gemini Explanation & Copy** | PRD §4.E | Planned (Milestone 4) | Not Run |
| **Deterministic Offline Fallback** | PRD §4.E | **Implemented (`orchestrator.py`)** | **Passed (Option 1 factual copy)** |
| **Transparent Shopper Offer Card** | PRD §4.D | **Implemented (`RecommendationCard.tsx`)** | **Passed (CDP screenshots verified)** |
| **"How Offers Work" Disclosure Modal** | PRD §1.5 | Planned (Milestone 4) | Not Run |
| **Merchant Policy Sliders (Interactive)** | PRD §2 | Planned (Milestone 5) | Not Run |
| **Live Decision Audit Log Table** | PRD §2 | Planned (Milestone 5) | Not Run |
| **3-Policy Synthetic Simulation Engine**| PRD §4.F | Planned (Milestone 5) | Not Run |
| **Automated Financial Invariant Tests** | PRD §7 | **Implemented (`test_decision_engine.py`)** | **Passed (26/26 suite tests)** |

---

## 5. Testing & Verification Evidence
*Status: Milestone 1 Foundation, Milestone 2 Catalog Storefront, and Milestone 3 Decision Engine executed and verified.*

- [x] **Database Initialization & Seeding:** `test_database_has_twenty_products` passed (verified exactly 20 items loaded into `faircart.db`).
- [x] **Product Financial Positivity & COGS Invariant:** `test_product_schema_and_financial_positivity` passed (verified 0 < COGS < RefPrice and positive inventory for all 20 products).
- [x] **Single-Item & Batch Repository Queries:** `test_repository_get_by_id` and `test_repository_get_by_ids` passed with exact integer-cent precision.
- [x] **API Health Contract:** `test_health_endpoint` passed (verified HTTP 200 OK, `status="healthy"`, `catalog_items_loaded=20`, `database="sqlite"`).
- [x] **Root Discovery Endpoint:** `test_root_endpoint` passed (verified HTTP 200 OK with doc links).
- [x] **Catalog API Endpoint:** `test_catalog_api.py` passed (4 tests passed: 20 validated items, API schema conformance, exact cents-to-dollars price conversion, and deterministic catalog order).
- [x] **Interactive Cart Drawer & Quantity State:** Implemented in `CartDrawer.tsx` with dynamic item addition, increment/decrement controls, live subtotal computation, and empty-state messaging.
- [x] **Responsive Storefront & Filters:** Implemented in `StorefrontView.tsx` with dynamic category pills, real-time client-side search, skeleton loading state, and error recovery retry action.
- [x] **Simulated Zero-Payment Checkout:** Implemented in `CheckoutModal.tsx` providing an itemized order receipt, transparent zero-payment disclosure, and cart reset.
- [x] **Frontend TypeScript & Vite Build:** `npm --prefix frontend run build` passed in 11.42s with zero TypeScript compilation errors, compiling 1,598 modules and outputting a dedicated 26.5 kB CSS bundle (`dist/assets/index-*.css`).
- [x] **Tailwind PostCSS Pipeline Hookup:** Fixed root cause by creating `frontend/src/index.css` with `@tailwind` directives and importing it in `main.tsx`. Verified that the Vite build now outputs full stylesheets.
- [x] **Headless Edge Desktop Visual Verification:** Captured and visually inspected `screenshot_desktop.png` (1280x900 viewport) via CDP. Verified 4-column aligned product grid, fixed-aspect image containers (`h-44 object-cover`), clean typography hierarchy, and FastAPI 20-item status badge.
- [x] **Headless Edge Mobile Visual Verification:** Captured and visually inspected `screenshot_mobile.png` (390x844 viewport, mobile touch emulation) via CDP. Verified responsive header, horizontal category scrollbar hidden, hero section wraps cleanly, and product cards fit 100% of the mobile viewport.
- [x] **Cart Drawer Interaction Verification:** Captured and visually inspected `screenshot_cart_open.png` via automated item addition. Verified backdrop blur, 64x64px item thumbnail, quantity increment/decrement controls, line item total, subtotal ($80.00), ethical trust banner, and checkout simulation CTA.
- [x] **Merchant Console Preview Verification:** Captured and visually inspected `screenshot_merchant.png` via hash routing (`#merchant`). Verified live catalog statistics (20 items, $50.75 avg price, $12-$140 range), category inventory table, and locked policy sliders preview.
- [x] **Engine A Recommender Invariants:** `test_recommender_never_recommends_item_already_in_cart`, `test_recommender_filters_out_of_stock_items`, and `test_recommender_prioritizes_explicit_complementary_link` passed cleanly.
- [x] **Engine B Financial Invariants:** `test_optimizer_strictly_enforces_gross_margin_floor` (fails discounts that breach margin floor), `test_optimizer_respects_discount_cap` (caps max discount), `test_optimizer_price_ceiling_and_non_negative_savings` (`final_price <= ref_price`, `savings >= 0`), and `test_optimizer_zero_revenue_safeguard` passed.
- [x] **Engine C End-to-End Orchestrator & API:** `test_orchestrator_sub_25ms_latency` (< 25ms SLA, recorded 3.5ms on live API), `test_orchestrator_empty_cart_returns_safe_no_offer`, `test_independent_recommendation_and_incentive` (Option 1 verified: candidate shown with *"Standard price · No discount applied"* when margin floor is violated), and `test_api_endpoint_post_decision` passed.
- [x] **Consolidated Backend Test Suite:** All 21 unit tests in `backend/tests/` passed in 0.426s (`test_foundation.py` + `test_catalog_api.py` + `test_decision_engine.py`).
- [x] **Live Storefront Recommendation Card Verification:** Captured and visually inspected `screenshot_m3_storefront_recommendation.png` via CDP. Verified prompt display of `RECOMMENDED BUNDLE DEAL` on `Padded Memory Foam Wrist Rest` with `$20.00` price, `$25.00` strikethrough, `Save $5.00 (20% OFF)` badge, and `+ Add Bundle for $20.00` CTA.
- [x] **Live Cart Drawer Bundle Offer Verification:** Captured and visually inspected `screenshot_m3_cart_recommendation.png` via CDP. Verified seamless rendering of the recommendation card inside the open cart drawer alongside cart items.
- [x] **Transparency Disclosure Verification:** Captured and visually inspected `screenshot_m3_transparency_expanded.png` via CDP. Verified expandable "Why this item?" drawer detailing factual affinity (75%) and economic margin floor compliance (satisfies 20% floor).
- [ ] Gemini Asynchronous Service & Fallback: (Scheduled for Milestone 4).
- [ ] 3-Policy Simulation Comparator: (Scheduled for Milestone 5).

---

## 6. Technical Explanations for Judges (Plain Language)



### How does FairCart AI calculate whether to offer a discount?

"Think of FairCart AI like a smart store manager standing next to the checkout. When you put a mechanical keyboard in your cart, it notices that a wrist rest would go great with it. But before offering you $2.50 off, it checks two things:

1. **Can the store afford it?** It calculates the profit on the keyboard *plus* the wrist rest and ensures the total profit margin stays above the owner's safety floor (say, 20%).

2. **Does it make business sense?** It estimates whether the discount will actually encourage you to bundle the item, compared to leaving it at full price.

If both are yes, you get a transparent discount. If not, you still see the wrist rest at standard price without any deceptive tricks."



### Why not use AI to dynamically raise prices when demand is high?

"Dynamic price surges alienate shoppers and destroy long-term trust. FairCart AI operates on a fundamental principle: **the base price is an unbreakable ceiling.** Personalization can only help you discover products and save money—it can never make an item more expensive for you than for someone else."



---



## 7. Demonstration Script & Storyboard (2–3 Minutes)



- **0:00 – 0:30 (The Problem & The Storefront):** Introduce FairCart AI. Open the Storefront. Show a clean, dark-pattern-free catalog of 20 products. Add an *Ergonomic Mechanical Keyboard* ($80.00) to the cart.

- **0:30 – 1:00 (The FairCart Recommendation & Gemini Explanation):** Open the Cart Drawer. FairCart AI suggests the *Padded Wrist Rest* with a 10% bundle discount ($2.50 savings, $22.50 final price). Highlight the Gemini-generated explanation ("Paired with your keyboard to support natural ergonomics"). Show the transparent savings breakdown and click the "How offers work" transparency modal.

- **1:00 – 1:40 (The Merchant Console & Margin Guardrail):** Switch to the Merchant Console. Point to the live decision log verifying the exact math: keyboard ($80) + wrist rest ($22.50) yields 34% gross margin, safely above the 20% floor. Now, drag the Margin Floor slider up to 45%. Return to the cart—watch FairCart AI instantly transition the wrist rest to *"Standard price · No discount applied"* ($25.00) because a discount would now breach the merchant's 45% floor.

- **1:40 – 2:20 (The 3-Policy Simulation):** In the Merchant Console, run the 1,000-session simulation. Show side-by-side results comparing No Discount vs Blanket 15% vs FairCart AI. Explain how FairCart protects merchant contribution profit while avoiding margin cannibalization.

- **2:20 – 2:40 (Simulated Checkout & Wrap-up):** Complete simulated checkout without credit cards. Show the order receipt and recap: transparent savings for shoppers, guaranteed margin protection for merchants.



---



## 8. Judge-Facing Project Story



### Inspiration

Online shopping has become an obstacle course of deceptive countdown clocks, artificial "Only 1 left!" warnings, and opaque algorithms that track shoppers across the web to extract maximum prices. Meanwhile, independent merchants struggle with blunt, margin-destroying sales (like 15% off everything) that cut into profits without building loyalty. We asked: *Can AI optimize e-commerce value collaboratively—protecting merchant margins while giving shoppers genuine, transparent value?*



### What It Does

FairCart AI is an ethical commerce decision engine. It combines real-time product recommendations with constrained economic optimization. When a shopper adds an item to their cart, FairCart AI recommends complementary products and evaluates whether a discount can be offered safely without breaching the merchant's profit floor. Gemini provides clear, honest explanations of why recommendations and discounts are offered, and a built-in merchant console provides complete transparency into every financial decision.



### How It Was Built

- **Backend:** Python 3.12, FastAPI, Pydantic v2, and SQLite for high-performance, deterministic decision logic.

- **Frontend:** React 19, TypeScript, Vite, and Tailwind CSS for a modern, responsive, accessible single-page application.

- **AI/LLM:** Google Gemini API for natural-language customer-facing offer explanations, backed by deterministic offline fallbacks.

- **Optimization:** Constrained incremental contribution utility modeling enforcing immutable reference price ceilings and basket gross-margin floors.

