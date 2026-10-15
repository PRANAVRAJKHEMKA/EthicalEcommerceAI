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

### DEC-018: Milestone 4 Product Refinement, Gemini Explanations, State Persistence, and Reload Isolation

- **What We Decided & Issues Resolved:**
  1. **Uvicorn Reload Isolation (`--reload-dir backend`):**
     - *Issue:* Default Uvicorn `--reload` watched the root project directory `D:\EthicalEcommerceAI`, including `.venv\Lib\site-packages\pydantic_core`. Any file modification or cache access in `.venv` triggered an unwanted reload loop.
     - *Fix:* Replaced generic `--reload` with `--reload --reload-dir backend`, explicitly confining the file watcher to the application code directory and preventing file contention in `.venv`.
  2. **Strict Pydantic / pydantic-core Binary Pinning:**
     - *Issue:* Competing Python processes caused Windows file locking on `.pyd` dynamic libraries, causing `ImportError: cannot import name 'validate_core_schema' from 'pydantic_core'`.
     - *Fix:* Explicitly pinned `pydantic-core==2.27.2` in `backend/requirements.txt` to match `pydantic==2.10.6`. Terminated all competing orphan processes and verified zero broken dependencies with `pip check`.
  3. **Verified Explanation Endpoint (`POST /api/v1/explanation`):**
     - Mounted independently of the primary sub-25ms synchronous decision pipeline (`/api/v1/decision`).
     - Implemented `GeminiExplanationService` with prompt grounded in SQLite catalogue attributes, response caching, 3.5s timeout, and instant deterministic fallback (sub-5ms latency).
     - Confirmed absolute financial immutability: the explanation schema contains zero pricing or discount fields, preventing generative AI from modifying commercial rules.
  4. **Catalogue Expansion (32 Products) & Intent Grounding:**
     - Expanded catalogue from 24 to 32 verified products across 7 categories with unique, curated Unsplash imagery.
     - Upgraded Engine A factual compatibility reasons to articulate concrete technical pairings (e.g. wrist extension relief on mechanical keyboards, 100W PD / 4K HDMI multi-monitor routing).
  5. **State Persistence & Automatic Discount Revocation:**
     - Persisted `faircart_cart`, `faircart_shopping_context`, and `faircart_dismissed_ids` in `localStorage`.
     - Implemented a reactive revalidation effect that automatically revokes bundle discounts back to standard price when prerequisite parent items are removed from the basket.
  6. **Transparency Modal & Interactive Merchant Console:**
     - Created `TransparencyModal.tsx` disclosing the dual-engine architecture, zero price hikes, and Gemini boundary.
     - Created interactive policy sliders (`margin_floor`, `discount_cap`) in `MerchantView.tsx` with live SQLite persistence via `GET/POST /api/v1/settings`.

- **Verification Evidence:**
  - 33/33 backend automated unit tests pass in 0.89s.
  - Frontend production build (`tsc -b && vite build`) compiles cleanly in 4.27s.
  - Live Edge CDP screenshots captured: `screenshot_m4_storefront_32_items.png`, `screenshot_m4_transparency_modal.png`, `screenshot_m4_recommendations_explained.png`, `screenshot_m4_merchant_console.png`, `screenshot_m4_revoked_bundle_discount.png`.

- **Status:** **Implemented, Tested & Recovered (in Milestone 4)**.

---

### DEC-019: Context-Aware Whole-Basket Recommender, Multi-Item Association Rules, and Privacy-Preserving Session Event Architecture

- **What We Decided & Implemented:**
  1. **Whole-Basket Multi-Stage Recommendation Pipeline (`recommender.py`):**
     - Replaced static 1-to-1 pairing rules with a multi-stage whole-basket ranker evaluating all items in the shopper's active cart.
     - **Stage 1 (Candidate Generation):** Union of direct complements across all cart items, mined multi-item association rules, category affinity, and anonymous session browsing history.
     - **Stage 2 (Multi-Signal Scoring):**
       $$S = 0.35 \times S_{\text{comp}} + 0.30 \times S_{\text{assoc}} + 0.20 \times S_{\text{context}} + 0.05 \times S_{\text{session}} + \text{base\_vis}$$
       where $S_{\text{assoc}} = \min(1.0, \frac{\text{lift} - 1.0}{3.0}) \times \text{confidence}$ (derived from mined association co-occurrence).
     - **Stage 3 (Factual Synergy Explanation):** Multi-parent factual reasons articulating concrete pairings (e.g., *"Complements Ergonomic Mechanical Keyboard and Precision Vertical Wireless Mouse simultaneously"*), association co-occurrence lift, and user-selected setup intent.
     - **Stage 4 (Diversity Enforcement):** Strict subcategory diversity (maximum 1 item per subcategory) and category diversity (maximum 2 items per category) across top-$K$ recommendations.
  2. **Reproducible Association Rule Mining (`associations.py`):**
     - Mined 401 association rules from 600 synthetic transactions generated across 10 desk setup archetypes (seed=42).
     - Evaluated support, confidence, and lift metrics, supporting multi-item antecedents ($\{A, B\} \to C$).
     - Handled zero-denominator boundary conditions ($P(B) \le 0 \implies \text{lift} = 1.0$) and multi-item antecedent validation.
     - Stored rules deterministically in SQLite `basket_association_rules` table.
  3. **Privacy-Preserving Anonymous Session Event Model:**
     - Created `session_events` table in SQLite with zero PII (anonymous `session_id`, `event_type`, `product_id`, `shopping_context`, `metadata_json`, `timestamp`).
     - Exposed `POST /api/v1/events`, `GET /api/v1/events`, and `DELETE /api/v1/events`.
     - Supports full session lifecycle: cart additions/removals log anonymous interaction events; cart reset or order completion invokes `DELETE /api/v1/events` to wipe session records.
     - Distinguishes browsing intent (`product_view`, `search_submitted`) from purchase intent (`add_to_cart`, `recommendation_accepted`).
  4. **Engine B Independence & Authority:**
     - Engine B economic optimizer remains completely independent and authoritative over all monetary values.
     - Dynamically formats multi-item prerequisite condition strings (*"Valid when bundled with Ergonomic Mechanical Keyboard and Precision Vertical Wireless Mouse"*).
     - Automatically revokes bundle discounts back to standard price when prerequisite parent items are removed.
  5. **Offline Model Evaluation Framework (`evaluate_recommendations.py`):**
     - Evaluated whole-basket ranker against 1-to-1 baseline across held-out synthetic baskets ($N=200+$, seed=100, $K=4$).
     - Quantitative results:
       - **HitRate@4:** 0.1579 (baseline) $\to$ 0.5526 (improved) [**+0.3947**]
       - **Recall@4:** 0.1579 (baseline) $\to$ 0.5526 (improved) [**+0.3947**]
       - **NDCG@4:** 0.0886 (baseline) $\to$ 0.4952 (improved) [**+0.4066**]
       - **Catalog Coverage:** 142.1% $\to$ 152.6% [**+10.5%**]
       - **Avg Category Diversity:** 2.24 $\to$ 2.94 categories [**+0.70**]
     - *Ethical Grounding Note:* Synthetic transactions are explicitly labeled as algorithmic demonstrations, not real-world consumer behavior.
  6. **UI Integration & Visual Verification:**
     - Added `✨ Multi-Item Match` and `📈 X.Xx Lift` badges to `RecommendationCard.tsx`.
     - Updated transparency drawer with association co-occurrence lift, confidence, and basket synergy explanation.
     - Verified live in browser via Edge CDP screenshots: `screenshot_context_aware_multi_item_recommendations.png` and `screenshot_context_aware_transparency_details.png`.
  7. **Automated Testing:**
     - 43/43 automated backend tests pass in 0.93s (`test_context_aware_engine.py` covering multi-item synergy, context shifts, association metrics, cart exclusions, diversity, session events lifecycle, quote agreement, and offline evaluation).
     - Frontend production build compiles cleanly in 8.4s.

- **Status:** **Implemented, Tested & Verified (in Context-Aware Engine Upgrade)**.

---

### DEC-020: Hybrid Recommendation Intelligence, Association-Rule Mining, Contextual ML Ranking, and MMR Diversity Re-ranking (Milestone 4B)

- **What We Decided & Implemented:**
  1. **Full 10-Stage Recommendation Pipeline:**
     - Upgraded the recommendation engine into an end-to-end 10-stage hybrid architecture:
       (1) Session Context Extraction $\to$ (2) Hard Constraint Candidate Filtering $\to$ (3) Co-Occurrence Association Mining $\to$ (4) Multi-Signal Candidate Generation $\to$ (5) Contextual Feature Vector Extraction $\to$ (6) Supervised HistGradientBoosting ML Ranking $\to$ (7) Deterministic Hybrid Scoring Fallback ($S_{hybrid}$) $\to$ (8) Maximal Marginal Relevance (MMR) Diversity Re-ranking $\to$ (9) Dynamic Factual Copy Grounding $\to$ (10) Independent Engine B Margin Optimization.
  2. **Apriori Basket Association Mining (`associations.py`):**
     - Mined itemsets up to size 4 with minimum support count threshold $\operatorname{minCount} = \max(3, \lceil 0.005 N \rceil) = 8$ across 2,000 synthetic shopping sessions (1,600 train / 400 test) generated with fixed seed (`seed=42`).
     - Generated 980 validated association rules with antecedent sizes $1 \le |X| \le 3$.
     - Evaluated support, raw confidence, Laplace-smoothed confidence ($\alpha=1.0$):
       $$\operatorname{confidence}_{smooth}(X \to p) = \frac{\operatorname{count}(X \cup \{p\}) + 1}{\operatorname{count}(X) + 2}$$
     - Computed lift with safe positive-denominator safeguards: $\operatorname{lift}(X \to p) = \frac{\operatorname{conf}_{smooth}(X \to p)}{\max(1, \operatorname{count}(p)) / N}$.
     - Bounded association score $A(p, B) = \max_{X \subseteq B, 1 \le |X| \le 3} [r_X \cdot \operatorname{confidence}_{smooth} \cdot L_X]$ where $r_X = \min(1, \frac{\text{count}}{\text{minCount}})$ and $L_X = \frac{\max(0, \ln(\text{lift}))}{1 + \max(0, \ln(\text{lift}))}$.
  3. **Exact Deterministic Hybrid Scoring Formula (`recommender.py`):**
     $$S_{hybrid}(p \mid B, c, h) = 0.30 C(p, B) + 0.30 A(p, B) + 0.20 U(p, c) + 0.15 E(p, h) + 0.05 P(p, B)$$
     - **Complementarity $C(p, B)$:** $\frac{1}{\sqrt{|B|}} \sum_{b \in B} \operatorname{Comp}(b, p)$, normalized to $[0, 1]$, rewarding multi-basket compatibility without duplicate inflation.
     - **Association $A(p, B)$:** Laplace-smoothed confidence $\times$ bounded logarithmic lift over all antecedent subsets $X \subseteq B$ ($|X| \le 3$).
     - **Context Intent $U(p, c)$:** Jaccard tag/use-case overlap $\frac{|K_p \cap K_c|}{|K_p \cup K_c|}$, neutral $0.5$ when context is 'all'.
     - **Interaction History $E(p, h)$:** Event decay $\sum_i w(e_i) \exp(-\Delta t_i / \tau)$ ($\tau = 24.0$h) mapped through $0.5 + 0.5 \tanh(z)$.
     - **Price Fit $P(p, B)$:** Geometric price distance $\exp\left(-\frac{|\ln((price_p + 1) / (m_B + 1))|}{1.0}\right)$.
  4. **Supervised ML Ranker (`HistGradientBoostingClassifier` in `ml_ranker.py`):**
     - Trained a supervised GBDT ranker (`max_iter=100`, `learning_rate=0.08`, `max_leaf_nodes=15`, `l2_regularization=1.0`, `random_state=42`) on 14 candidate features with zero cross-session test leakage.
     - Synthetic training labels generated using an independent latent shopper utility simulator (modeling ergonomic, aesthetic, performance, and budget preferences with Gaussian noise).
     - Persisted trained model artifact to `backend/app/engine/artifacts/ranker_model.joblib` (195 kB).
     - Sub-millisecond deterministic fallback to $S_{hybrid}$ when uninitialized or upon runtime exception.
  5. **Maximal Marginal Relevance (MMR) Diversity Re-Ranking ($\lambda=0.75$):**
     $$\operatorname{MMR}(p) = \arg\max_{p \in C \setminus R} \left[ \lambda \cdot S_{base}(p) - (1 - \lambda) \cdot \max_{r \in R} \operatorname{Sim}(p, r) \right]$$
     - Multi-attribute similarity: $\operatorname{Sim}(p_1, p_2) = 0.40 \cdot \mathbf{1}_{cat} + 0.30 \cdot \mathbf{1}_{subcat} + 0.20 \cdot Jaccard(tags) + 0.10 \cdot (1 - \frac{|price_1 - price_2|}{\max(price_1, price_2)})$.
     - Eliminates redundant recommendations (e.g., offering three wrist rests or two mousepads) while preserving top-tier relevance.
  6. **Scientific Offline Model Selection:**
     - Rigorous offline evaluation on 400 held-out co-purchase test sessions:
       - **HitRate@4:** Baseline `0.0625` $\to$ Learned HistGBM `0.0725` $\to$ Hybrid $S_{hybrid}+\text{MMR}$ **`0.3650`** (+484% gain)
       - **NDCG@4:** Baseline `0.0351` $\to$ Learned HistGBM `0.0415` $\to$ Hybrid $S_{hybrid}+\text{MMR}$ **`0.3018`** (+759% gain)
       - **Catalog Coverage:** Baseline `90.62%` $\to$ Hybrid **`100.0%`**
       - **Pairwise Attribute Similarity:** Baseline `0.2148` $\to$ Hybrid **`0.1235`** (significantly more diverse recommendations)
     - *Scientific Selection:* Because deterministic hybrid scoring ($S_{hybrid} + \text{MMR}$) vastly outperforms both the baseline and the noisy synthetic simulator model on held-out ranking quality, $S_{hybrid} + \text{MMR}$ is established as the primary production online ranker. The supervised model is preserved as an evaluated experimental alternative (`ranking_mode='ml'`).
  7. **Ultra-Low Latency & Test Verification:**
     - Measured decision latency: **mean 3.80ms, p50 3.18ms, p95 5.98ms** (far exceeding the <25ms SLA).
     - **61/61 backend automated unit tests passing** (`test_foundation.py`, `test_catalog_api.py`, `test_decision_engine.py`, `test_context_aware_engine.py`, `test_associations_math.py`, `test_hybrid_ml_recommender.py`).
     - Frontend production build compiles cleanly in 2.48s with zero TypeScript warnings.

- **Status:** **Implemented, Verified & Documented (in Milestone 4B)**.

---

## 2. Pending Decisions

- **PEN-001 (Spec Stage):** Specific Scikit-Learn Model architecture for purchase propensity ranking (Resolved in DEC-020: Evaluated `HistGradientBoostingClassifier` with 14 features against deterministic hybrid scoring $S_{hybrid}$; $S_{hybrid} + \text{MMR}$ selected as default online ranker based on held-out NDCG@4 superiority).

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

### DEC-021: Empty-Basket Recommendations, Historical Personalization & Cold-Start Intelligence (Milestone 4C)

- **What We Decided & Implemented:**
  1. **Recommendation Anchor Model ($A = B \cup V \cup S \cup O$):**
     - Decoupled recommendation generation from active basket presence. Recommendations can now anchor on:
       - $B$: Active basket items (weight 1.0)
       - $V$: Recent viewed items (weight 0.60)
       - $S$: Saved-cart items (weight 0.85)
       - $O$: Historical FairCart order items (weight 0.75)
     - Implemented logarithmic repetition dampening to prevent spamming:
       $$\text{repetition\_guard} = \min(1.5, 1.0 + 0.2 \cdot \ln(1 + \text{view\_count}))$$
  2. **Commercial vs Historical Cart Separation (Zero Unearned Bundle Discounts):**
     - Active cart $B$ is the sole basis for pricing quotes, checkout subtotals, and bundle discounts.
     - Historical or viewed items in $A \setminus B$ must **never** trigger promotional bundle pricing. When $B = \emptyset$, all candidates receive `is_offered = False`, standard reference price, zero savings, and condition *"Standard price · Add items to cart to unlock bundle deals"*.
  3. **Deterministic Cold-Start Scoring Formula ($S_{\text{cold}}$):**
     - For shoppers with empty carts and zero history, FairCart AI returns top catalog picks scored by:
       $$S_{\text{cold}}(p \mid c) = 0.40 U(p, c) + 0.35 \operatorname{Popularity}(p) + 0.15 \operatorname{Connectivity}(p) + 0.10 P(p, \emptyset)$$
     - Avoids zero-candidate screens and prevents cold-start abandonment.
  4. **Modest, Honest Provenance Labels:**
     - Cold-start items are explicitly labeled *"Popular picks from our catalogue"*, never claiming false personalization.
     - Context-aligned items display *"Recommended for your selected [Context] setup"*.
     - History-anchored items state *"Inspired by products you've viewed"*, *"Based on items in your saved cart"*, or *"Based on items in your previous FairCart order"*.
  5. **Interactive Storefront & Session Reset:**
     - Storefront displays 4 discovery picks immediately on first visit before any product is added to cart.
     - Product interactions dynamically update recent views.
     - Added a "Reset Session" button allowing judges to wipe browsing history and return to cold start instantly.
  6. **Automated Verification:**
     - 76/76 backend tests pass in 19.95s, including 15 dedicated tests in `test_empty_basket_recommendations.py`.
     - Frontend production build (`tsc -b && vite build`) compiles in 2.44s.
     - Live Edge CDP visual screenshots captured: `screenshot_m4c_cold_start.png`, `screenshot_m4c_context_based.png`, `screenshot_m4c_view_based.png`.

- **How to Explain to Judges:**
  "Most recommendation engines show a blank screen or spam generic ads until you add an item to your cart. FairCart AI introduces an anchor model that recommends relevant accessories based on products you've inspected, saved items, or your selected setup goal. But ethically, we strictly separate discovery from pricing: you can never get an unearned bundle discount without actually buying the parent item in your active basket. And when a shopper is completely new, our cold-start formula recommends popular, versatile catalog staples with full honesty—never pretending to know them."

---

### DEC-022: Three-Policy Economic Simulation Comparator & Merchant Analytics (Milestone 5)

- **What We Decided & Implemented:**
  1. **Three-Policy Counterfactual Comparator (`POST /api/v1/simulate`):**
     - Implemented an economic simulation engine comparing three distinct pricing and recommendation policies:
       1. `NO_DISCOUNT`: Organic baseline shopping behavior with zero promotional markdowns.
       2. `BLANKET_15`: Indiscriminate 15% promotional markdown across all completed order items, without margin floor verification.
       3. `FAIRCART_AI`: Context-aware hybrid recommendation engine coupled with the margin-constrained economic incentive optimizer.
  2. **Paired Evaluation with Common Random Numbers (CRN):**
     - Evaluates 1,000 paired customer shopping sessions with deterministic pseudo-random seed (default `42`).
     - Employs Common Random Numbers (CRN) so all three policies confront the exact same synthetic shoppers, cart builds, price sensitivity draws, and stochastic purchase acceptance thresholds ($u_{\text{conv}}, u_{\text{acc}}$).
     - Isolates the causal economic impact of the policy and eliminates cross-cohort sampling variance.
  3. **9 Realistic Shopper Archetypes:**
     - Simulates an authentic e-commerce population across 9 distinct behavioral archetypes:
       - Cold-Start Explorer (15%), Browse-Only Researcher (15%), Saved-Cart Returner (10%), Multi-Item Setup Builder (15%), Gaming Enthusiast (10%), Study/Wellness/Travel Context Shopper (10%), Inelastic High-Intent Buyer (10%), Price-Sensitive Deal Seeker (10%), Low-Margin Discount-Ineligible Shopper (5%).
  4. **Strict Financial Accounting & Statistical Invariants:**
     - Enforces rigorous e-commerce accounting formulas:
       $$\text{net\_sales\_revenue} = \text{gross\_sales} - \text{discounts}$$
       $$\text{gross\_margin} = \frac{\text{net\_sales} - \text{COGS}}{\text{net\_sales}} \quad (\text{or } 0.0 \text{ if } \text{net} \le 0)$$
       $$\text{contribution\_profit} = \text{net\_sales} - \text{COGS} - (\text{orders} \times \$3.50 \text{ variable fulfillment})$$
     - Zero double-counting of discounts; complete safeguard against `ZeroDivisionError` on empty cohorts.
     - Computes two-sided 95% Confidence Intervals for both conversion rates and session contribution profits.
  5. **Empirical Findings from 1,000-Session Evaluation (Seed 42):**
     - **Contribution Profit:** FairCart AI delivered **$11,054.65** (95% CI: [$9.91, $12.19]/session), outperforming Blanket 15% (**$6,211.00**, +78.0%) and No Discount (**$7,380.00**, +49.8%).
     - **Margin Floor Preservation:** Blanket 15% markdown caused **46 margin floor breaches (12.1% of completed orders)**, severely destroying merchant profit on low-margin products. FairCart AI incurred **0 violations (0.0% · 100% compliant)**.
     - **Promotional Efficiency:** FairCart AI reduced promotional waste by **$1,324.15 (-49.2%)** compared to Blanket 15%, while expanding Average Order Value from $46.99 (organic) and $40.00 (blanket) to **$66.86 (+42.3%)**.
  6. **Interactive Merchant Console UI (`MerchantView.tsx`):**
     - Built interactive simulation controls: configurable session count (250–2,500), seed input, and active margin floor / discount cap indicators.
     - Side-by-side policy comparison cards displaying contribution profits, conversion rates, AOVs, margins, and violation alerts.
     - Embedded responsive SVG charts comparing contribution profits and conversion rates alongside margin safety indicators.
     - Comprehensive 11-row metric comparison matrix and transparent synthetic methodology disclosure.
  7. **Automated Verification:**
     - 89/89 backend unit tests pass in 81s, including 13 dedicated simulation tests in `test_simulation_engine.py`.
     - In-memory anchor extraction in `orchestrator.py` reduces decision latency to sub-millisecond execution.
     - Live Edge CDP screenshots captured: `screenshot_m5_merchant_simulation.png`, `screenshot_m5_simulation_charts.png`, and `screenshot_m5_merchant_console_full.png`.

- **How to Explain to Judges:**
  "Merchants usually face a painful dilemma: either offer no discounts and lose price-sensitive shoppers, or run a blunt 15% storewide sale that erodes profits and loses money on low-margin items. In our 1,000-session paired simulation, we show that Blanket 15% caused 46 margin-floor violations, cutting total merchant profit down to $6,211. FairCart AI lifted contribution profit to $11,054—a 78% increase over blanket discounting—by recommending high-synergy products and offering discounts only when the merchant's margin floor was mathematically safe. Zero margin floor breaches, less promotional waste, and higher average order value."

- **Status:** **Implemented, Tested & Verified (in Milestone 5)**.

---

### DEC-023: Frequency-Aware Interaction Signals & Deliberate Product Detail Interaction (Milestone 5B)

- **What We Decided & Implemented:**
  1. **Exact Frequency-Aware, Time-Decayed Interaction Scoring:**
     - Replaced unweighted binary product visit flags with an exponential time-decayed interest accumulator:
       $$z_p = \sum_{e \in H_p} w_{\operatorname{type}(e)} \exp\left(-\frac{\Delta t_e}{\tau}\right)$$
       with half-life parameter $\tau = 24.0$ hours and documented action weights:
       - `simulated_purchase_completed` / `order_completed`: $1.00$
       - `add_to_cart`: $0.80$
       - `cart_saved`: $0.65$
       - `product_view`: $0.35$
       - Qualifying hover ($\ge 900$ms): $0.10$
       - Brief hover ($< 700$ms): $0.00$
       - Impression / catalogue display: $0.00$
     - Bounded monotonically increasing transformation:
       $$E(p, h) = 0.5 + 0.5 \tanh(\ln(1 + \max(0.0, z_p))) \in [0.5, 1.0)$$
       - Neutral baseline ($z_p = 0$): $E = 0.50$
       - 1 view ($z_p = 0.35$): $E \approx 0.6457$
       - 5 views ($z_p = 1.75$): $E \approx 0.8832$
       - 1 qualifying hover ($z_p = 0.10$): $E \approx 0.5475$
       - 5 qualifying hovers ($z_p = 0.50$): $E \approx 0.6923$
       - 50 hovers ($z_p = 5.00$): $E \approx 0.9723 < 1.0$ (diminishing returns guarantee strictly bounded evidence)
  2. **Product Card Pointer Dwell Threshold & Episode Isolation:**
     - Fixed previous bug where any mouse swipe triggered a full `product_view`.
     - Pointer dwell threshold ($\ge 900$ms) enforced via React `useRef` timer. Pointer departure prior to 900ms immediately cancels the event without emissions.
     - Episode identifiers (`hov-{pid}-{ts}-{rand}`) restrict emissions to at most 1 hover event per continuous dwell episode, while allowing new episodes on intentional return.
     - Full keyboard accessibility: 900ms `onFocus` tracking emitting `product_focus`.
  3. **Deliberate Product Detail Inspection Modal (`ProductDetailModal.tsx`):**
     - Clicking a product card or Quick View button opens an accessible modal dialog (`role="dialog"`), presenting rich product specifications, category badges, reference price/bundle offer status, inventory, and Add to Cart action.
     - Emits authentic `product_view` event upon intentional inspection.
  4. **Event Idempotency & SQLite Persistence:**
     - Enforced `INSERT OR IGNORE` with unique client/server `event_id` primary key in SQLite.
     - Browser refresh verified: viewed interaction history survives page reload in localStorage and SQLite.
  5. **100% Automated & Real-Browser Verification:**
     - 101/101 backend unit tests pass in 28.5s (12 dedicated frequency-aware signal tests in `test_frequency_aware_signals.py`).
     - Real-browser Edge CDP automated journey (`verify_m5b_browser.cjs`) verified 0 events for 350ms brief hover, 1 event for 1100ms qualifying hover, 2 events for separate episodes, modal inspection, and quote consistency.
     - Live visual artifacts: `screenshot_m5b_quick_view_modal.png` and `screenshot_m5b_frequency_recommendations.png`.

- **How to Explain to Judges:**
  "In real shopping, seeing someone inspect a keyboard five times or open its detail modal indicates much stronger interest than someone accidentally glancing at it once. FairCart AI models interaction frequency with exponential time decay: five views carry strictly more weight than one, and a 900ms intentional hover contributes a small, bounded signal. But crucially, our mathematical tanh bound ensures repeat visits can never be gamed to hijack the recommendation engine or override merchant margin safety."

- **Status:** **Implemented, Tested & Verified (in Milestone 5B)**.

### DEC-024: Public Deployment Architecture, Unified Multi-Stage Container & Self-Healing Startup (Milestone 6)

- **What We Decided & Implemented:**
  1. **Unified Single-Origin Container vs Decoupled Topology:**
     - Evaluated three hosting options: Option A (Unified container on Render / Cloud Run / Hugging Face Spaces), Option B (Decoupled Vercel frontend + Render backend + Neon Serverless PostgreSQL), and Option C (Paid persistent SSD disk).
     - Standardized on Option A as the primary zero-cost deployment pattern: eliminating cross-origin CORS mismatches, preflight latency, and third-party cookie restrictions by serving compiled React static assets (`frontend/dist`) directly from FastAPI at `/` and `/assets`.
     - Option B documented as a verified zero-credit-card persistent alternative using Neon Serverless Postgres (which never expires, unlike Render's 30-day PostgreSQL).
     - Strict adherence to zero-cost boundaries: no chargeable resources or credit cards required.
  2. **Multi-Stage Container Definition (`Dockerfile`):**
     - Stage 1: `node:20-alpine` builds the Vite/React 19 bundle (`npm ci && npm run build`).
     - Stage 2: `python:3.12-slim` minimal runtime, installs pinned requirements, mounts static assets, and exposes dynamically configurable `$PORT`.
     - Health check directive: `HEALTHCHECK --interval=30s CMD curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1`.
  3. **Self-Healing Container Startup:**
     - In ephemeral container environments (e.g., Render free tier), container reboots restore the filesystem to image baseline.
     - Added an automatic startup check in `backend/app/main.py:startup_event`: if `faircart.db` is missing or contains fewer than 32 items, it executes `seed_catalog()` idempotently on boot, guaranteeing that catalogue items and association rules are always available.
  4. **Content-Negotiated Discovery:**
     - `GET /` inspects the HTTP `Accept` header: API and test clients receiving `application/json` get discovery metadata (docs, health), while web browsers receiving `text/html` are served the SPA `index.html`.

- **How to Explain to Judges:**
  "Deploying full-stack AI applications often creates brittle multi-service dependencies. For FairCart AI, we designed a unified multi-stage container that builds the React application and embeds it into a high-performance Python 3.12 FastAPI service. It binds dynamically to cloud port standards, seeds its SQLite database automatically on boot if empty, and incurs zero hosting charges—allowing judges to experience the live application or spin it up locally in 30 seconds."

- **Status:** **Implemented, Tested & Verified (in Milestone 6)**.

### DEC-025: Production Security Guardrails: Sliding-Window IP Rate Limiting & Demo-Safe Admin Key (Milestone 6)

- **What We Decided & Implemented:**
  1. **Compute Endpoint Protection (Sliding-Window IP Rate Limiting):**
     - Running 1,000 Monte Carlo sessions with 9 archetypes on `POST /api/v1/simulate` is computationally intensive (~100-200ms of CPU).
     - Implemented an in-memory sliding-window rate limiter restricting each remote IP to **max 15 simulations per minute**. Exceeding requests immediately return `HTTP 429 Too Many Requests` with a clear explanation, preventing CPU denial-of-service on free-tier containers.
  2. **Administrative Access Protection for Merchant Settings:**
     - Gated `POST /api/v1/settings` with `ADMIN_TOKEN`.
     - When `ADMIN_TOKEN` is configured on the host, requests must provide `X-Admin-Token` or `Authorization: Bearer <token>`. Unauthenticated requests receive `HTTP 403 Forbidden`.
     - When `ADMIN_TOKEN` is left empty (local demo mode), local updates proceed seamlessly.
  3. **Demo-Safe Frontend Credential Handling:**
     - The merchant administration key input in `MerchantView.tsx` stores the entered token exclusively in browser `sessionStorage` (`faircart_admin_token`).
     - Zero hardcoded tokens or administrative credentials exist in client source code, build bundles, or Git commits.
  4. **Strict Repository Hygiene:**
     - Created `.env.example` documenting all configuration keys.
     - `.gitignore` and `.dockerignore` audited and verified: `.env*`, `*.db`, `*.sqlite3`, and `devpost/learner-profile.md` (personal learner context) are strictly excluded from Git. Zero secrets exist in Git history.

### DEC-026: Multi-Account Demonstration Authentication & Argon2id Security (Milestone 6B)

- **What We Decided & Implemented:**
  1. **5 Believable Customer Personas:**
     - Provisioned five distinct personas representing diverse shopping styles:
       1. `demo_gamer` (Alex Mercer): Competitive gamer seeking low-latency peripherals and mechanical gear.
       2. `demo_student` (Maya Lin): University student optimizing a compact study nook for focus and eye comfort.
       3. `demo_creator` (Devon Reed): Audio/video streamer prioritizing 4K capture and studio acoustics.
       4. `demo_traveler` (Jordan Hayes): Digital nomad valuing compact GaN power banks and travel cases.
       5. `demo_office` (Sarah Jenkins): Corporate knowledge worker prioritizing posture health and dual-monitor ergonomics.
  2. **Argon2id Password Derivation & Salt Security:**
     - Pinned `argon2-cffi==25.1.0`. All passwords hashed with state-of-the-art Argon2id ($m=65536, t=3, p=4$).
     - High-entropy, cryptographically random 20-character credentials generated per persona.
  3. **Strict Credential Boundary:**
     - Zero plaintext passwords committed to Git, tracked files, or judge notes.
     - Generated credentials stored strictly in local, gitignored file (`.local/demo-credentials.local.md`).
     - Evaluation helper endpoint (`GET /api/v1/auth/demo-personas`) dynamically reads local credentials only when present locally, enabling quick-select chip pre-filling in the frontend without leaking secrets.
  4. **Brute-Force Rate Limiting:**
     - In-memory sliding-window tracker enforcing max 5 failed attempts per 60 seconds per IP/username, immediately responding with `HTTP 429 Too Many Requests`.
  5. **Session Management & Administrative Isolation:**
     - Session tokens (256-bit cryptographically secure strings) stored in SQLite `user_sessions` with 7-day validity.
     - Extracted via Bearer header, `X-Session-Token`, or HttpOnly cookie.
     - Customer account logins have **zero** merchant administrative privileges: customer tokens passed to `POST /api/v1/settings` return `HTTP 403 Forbidden`.

- **How to Explain to Judges:**
  "To let judges evaluate FairCart AI across different shopping styles without creating accounts from scratch, we built 5 realistic demo accounts backed by industry-standard Argon2id hashing. The frontend features one-click persona chips that pre-fill credentials for evaluation convenience, but execute the real cryptographic authentication flow and issue genuine session tokens. Customer accounts have zero administrative access to merchant settings, and brute-force attempts are locked out after 5 failures."

- **Status:** **Implemented, Tested & Verified (in Milestone 6B)**.

---

### DEC-027: Account-Specific Order Histories & Recommendation Anchor Integration (Milestone 6B)

- **What We Decided & Implemented:**
  1. **Itemized Past Synthetic Orders:**
     - Provisioned 15 itemized historical orders (3 per persona) spanning legitimate catalog products with dates, status (`completed_simulated`), provenance (`synthetic_demonstration`), line savings, and paid totals.
  2. **Personalized Anchor Set Expansion ($A = B \cup V \cup S \cup O$):**
     - Sourced authenticated user past order items into candidate anchor pool $O$ via `repository.get_user_purchased_product_ids(user_id)` with weight $0.75$.
     - Empty-basket recommendations for `demo_gamer` vs `demo_creator` surface distinct, defensible recommendations without requiring cart contents.
  3. **Strict Cross-Account Isolation:**
     - User A cannot access User B's order by ID (`GET /api/v1/orders/{order_id}` returns `HTTP 404`).
     - Guest requests have zero user order anchors ($O = \emptyset$).
  4. **Simulated Checkout Persistence:**
     - Completing simulated checkout while signed in calls `POST /api/v1/orders`, saving the order to SQLite under the active user's ID and incrementing their order count.
  5. **User-Scoped Cart & Storage Isolation:**
     - Cart and viewed products are partitioned in localStorage by user ID (`faircart_cart_${userId}`, `faircart_viewed_ids_${userId}`), ensuring zero cross-persona leakage when switching accounts.

- **How to Explain to Judges:**
  "When you log in as Alex Mercer (Gamer), FairCart AI incorporates your past purchases into its candidate pool, highlighting gaming accessories and desk gear. Switch to Devon Reed (Creator), and the recommendations instantly pivot toward studio microphones and 4K webcams. Past orders are strictly isolated in SQLite: no customer can peek into another user's purchases, and completing a checkout immediately appends the new order to your personal history."

- **Status:** **Implemented, Tested & Verified (in Milestone 6B)**.

---

### DEC-028: Reliable Pointer Dwell Tracking & Stale Asynchronous Response Guards (Milestone 6B)

- **What We Decided & Implemented:**
  1. **High-Precision 700ms Pointer Dwell Threshold:**
     - Reduced dwell threshold from 900ms to 700ms based on human-computer interaction ergonomics for deliberate hover inspection.
     - Switched from synthetic mouse events to native `onPointerEnter` and `onPointerLeave`.
  2. **Touch Device Noise Filtering:**
     - Explicitly checks `e.pointerType !== 'touch'`, filtering out mobile taps that synthesize incidental hover events.
  3. **Internal Child Boundary Transition Protection:**
     - Guarded hover departure using `e.currentTarget.contains(e.relatedTarget)`. Moving the cursor between text, buttons, or badges inside a card does **not** cancel or restart the dwell timer.
  4. **Unmount & Visibility Cancellation:**
     - Added React unmount cleanup and a `visibilitychange` window listener to cancel timers if the user switches tabs or navigates away.
  5. **Stale Asynchronous Decision Response Guard:**
     - Implemented an incremental sequence ID ref (`decisionRequestIdRef`) in `App.tsx`. Earlier slow asynchronous decision responses that resolve out of order are discarded if a newer response has already arrived.

- **How to Explain to Judges:**
  "Tracking hovers in web apps is notoriously brittle: accidental swipes generate noise, moving over a button inside a card can cancel the timer, and mobile taps trigger fake mouse events. We re-engineered hover tracking with pointer events, an ergonomic 700ms dwell threshold, touch filtering, and boundary containment checks. We also added an incremental request sequence guard so slow network responses can never overwrite newer recommendations."

- **Status:** **Implemented, Tested & Verified (in Milestone 6B)**.

---

## 4. Feature Traceability & Implementation Status

| Feature | Scope / PRD Ref | Implementation State | Verification State |
| :--- | :--- | :--- | :--- |
| **Realistic 32-Product Catalog** | PRD §4.A | **Implemented (SQLite)** | **Passed (Seeded 32 items with tags, imagery & use cases)** |
| **Catalog Repository Layer** | Spec §6.1 | **Implemented** | **Passed (6 Unittest checks)** |
| **Operational Health API (`/api/v1/health`)**| Spec §5.1 | **Implemented (FastAPI)** | **Passed (HTTP 200 Schema Check: 32 items)** |
| **Catalog API (`/api/v1/catalog`)** | Spec §5.2 | **Implemented (FastAPI)** | **Passed (5 Unittest checks)** |
| **Interactive Cart & Drawer** | PRD §4.A | **Implemented (React)** | **Passed (State & UI verified with localStorage)** |
| **Storefront & Category Filters** | PRD §2 (View 1) | **Implemented (React)** | **Passed (Dynamic categories & search)** |
| **Shopping Intent Context Selector** | PRD §4.B | **Implemented (React)** | **Passed (Productivity, Gaming, Study, Travel, Wellness)** |
| **Empty-Basket & Cold-Start Discovery** | Spec §3.7 | **Implemented (`recommender.py`)** | **Passed ($S_{cold}$ formula, anchors $A = B \cup V \cup S \cup O$, 15 tests)** |
| **Simulated Zero-Payment Checkout** | PRD §1.6 | **Implemented (React Modal)** | **Passed (Itemized receipt & reset verified)** |
| **Merchant Console Interactive Sliders** | PRD §2 (View 2) | **Implemented (React & SQLite)** | **Passed (Live slider updates persisted via `/api/v1/settings`)** |
| **Apriori Association Rule Mining** | Spec §3.4 | **Implemented (`associations.py`)** | **Passed (980 rules mined from synthetic sessions, Laplace-smoothed)** |
| **Supervised ML Ranker (HistGBM)** | Spec §3.5 | **Implemented (`ml_ranker.py`)** | **Passed (Trained on 14 features, offline benchmarked)** |
| **Deterministic Hybrid Recommender ($S_{hybrid}$)** | Spec §3.4 | **Implemented (`recommender.py`)** | **Passed (0.3650 HitRate@4, +484% over baseline)** |
| **Maximal Marginal Relevance (MMR)** | Spec §3.6 | **Implemented (`recommender.py`)** | **Passed (Diversity similarity reduced to 0.1235, 100% coverage)** |
| **Engine B: Margin-Constrained Optimizer** | PRD §4.C | **Implemented (`optimizer.py`)** | **Passed (Independent candidate evaluation)** |
| **Engine C: Decision API (`/api/v1/decision`)**| PRD §4.C | **Implemented (`orchestrator.py`)** | **Passed (Mean 3.80ms latency, well under <25ms SLA)** |
| **Authoritative Basket Quotes (`/api/v1/quote`)**| Spec §5.3 | **Implemented (`orchestrator.py`)** | **Passed (Exact cents line totals & margin)** |
| **End-to-End Consistent Pricing** | PRD §4.D | **Implemented (Frontend & Backend)** | **Passed (Verified across 4 UI touchpoints)** |
| **Gemini Explanation & Copy** | PRD §4.E | **Implemented (`explanation.py`)** | **Passed (Attribute-grounded copy, 3.5s timeout)** |
| **Deterministic Offline Fallback** | PRD §4.E | **Implemented (`orchestrator.py`)** | **Passed (Sub-5ms factual fallback copy)** |
| **Transparent Shopper Offer Card** | PRD §4.D | **Implemented (`RecommendationCard.tsx`)** | **Passed (CDP screenshots verified)** |
| **"How Offers Work" Disclosure Modal** | PRD §1.5 | **Implemented (`TransparencyModal.tsx`)** | **Passed (Full dual-engine transparency)** |
| **Anonymous Session Interaction Events** | Spec §5.7 | **Implemented (`POST/GET/DELETE /api/v1/events`)** | **Passed (Zero-PII session lifecycle logging)** |
| **3-Policy Synthetic Simulation Engine**| PRD §4.F | **Implemented (`simulator.py`)** | **Passed (1,000 paired CRN sessions, 13 unittests, Edge CDP verified)** |
| **Frequency-Aware Interaction Signals**| Spec §3.4, §5.7 | **Implemented (`recommender.py`, `ProductDetailModal.tsx`)** | **Passed (12 dedicated unittests, 900ms hover dwell, Edge CDP verified)** |
| **Automated Test Suite (Full Backend)** | PRD §7 | **Implemented (`backend/tests/`)** | **Passed (101/101 backend unit tests passing in ~30.8s)** |
| **Multi-Stage Production Container**  | Spec §4, ADR §3 | **Implemented (`Dockerfile`, `.dockerignore`)** | **Passed (Node 20 build + Python 3.12 slim runtime)** |
| **Simulation Rate Limiting (IP Window)** | ADR §5.1 | **Implemented (`main.py` sliding window)** | **Passed (15 req/min allowed; 16th blocked with HTTP 429)** |
| **Merchant Admin Key Guardrail**     | ADR §5.2 | **Implemented (`main.py`, `MerchantView.tsx`)** | **Passed (HTTP 403 without token; 200 with X-Admin-Token; sessionStorage safe)** |
| **Content-Negotiated Root & SPA Mount** | ADR §4.3 | **Implemented (`main.py` Accept header)** | **Passed (JSON for API clients, HTML SPA for web browsers)** |
| **Self-Healing Startup Catalog Seeding**| ADR §4.1 | **Implemented (`main.py:startup_event`)** | **Passed (32 items & 980 rules seeded automatically on empty boot)** |
| **Demonstration Authentication (Argon2id)** | Spec §5.8 | **Implemented (`auth.py`)** | **Passed (7 unittests, Argon2id, sliding-window rate limit, bearer/cookie)** |
| **Account Order History & Isolation** | Spec §5.8 | **Implemented (`repository.py`)** | **Passed (4 unittests, 15 synthetic orders, cross-account 404, simulated checkout persistence)** |
| **Personalized Order Anchors ($A = B \cup V \cup S \cup O$)** | Spec §3.7 | **Implemented (`orchestrator.py`)** | **Passed (3 unittests, distinct gamer vs creator picks, zero leakage)** |
| **Reliable 700ms Pointer Dwell & Stale Guards** | Spec §3.4 | **Implemented (`ProductCard.tsx`, `App.tsx`)** | **Passed (3 unittests, Edge CDP verified, touch rejection, child transition safe)** |

---

## 5. Testing & Verification Evidence
*Status: Milestone 1 Foundation, Milestone 2 Catalog Storefront, Milestone 3 Decision Engine, Milestone 4 Product Refinement, Milestone 4B Hybrid ML & RecSys Pipeline, Milestone 4C Cold-Start Intelligence, Milestone 5 Economic Simulation Comparator, Milestone 5B Frequency-Aware Signals, Milestone 6 Public Deployment Architecture, and Milestone 6B Demo Authentication & Order History executed and verified.*

- [x] **Database Initialization & Seeding:** `test_database_has_twenty_products` and 32-item catalog seed passed (verified 32 validated items loaded into `faircart.db`).
- [x] **Product Financial Positivity & COGS Invariant:** `test_product_schema_and_financial_positivity` passed (verified 0 < COGS < RefPrice and positive inventory for all products).
- [x] **Single-Item & Batch Repository Queries:** `test_repository_get_by_id` and `test_repository_get_by_ids` passed with exact integer-cent precision.
- [x] **API Health Contract:** `test_health_endpoint` passed (verified HTTP 200 OK, `status="healthy"`, `catalog_items_loaded=32`, `database="sqlite"`).
- [x] **Root Discovery Endpoint:** `test_root_endpoint` passed (verified HTTP 200 OK with doc links).
- [x] **Catalog API Endpoint:** `test_catalog_api.py` passed (4 tests passed: validated items, API schema conformance, exact cents-to-dollars price conversion, and deterministic catalog order).
- [x] **Interactive Cart Drawer & Quantity State:** Implemented in `CartDrawer.tsx` with dynamic item addition, increment/decrement controls, live subtotal computation, and empty-state messaging.
- [x] **Responsive Storefront & Filters:** Implemented in `StorefrontView.tsx` with dynamic category pills, real-time client-side search, skeleton loading state, and error recovery retry action.
- [x] **Simulated Zero-Payment Checkout:** Implemented in `CheckoutModal.tsx` providing an itemized order receipt, transparent zero-payment disclosure, and cart reset.
- [x] **Frontend TypeScript & Vite Build:** `npm --prefix frontend run build` passed cleanly in 8.98s with zero TypeScript compilation errors (`tsc -b && vite build`), compiling 1,602 modules.
- [x] **Tailwind PostCSS Pipeline Hookup:** Fixed root cause by creating `frontend/src/index.css` with `@tailwind` directives and importing it in `main.tsx`. Verified that the Vite build now outputs full stylesheets.
- [x] **Headless Edge Desktop Visual Verification:** Captured and visually inspected `screenshot_desktop.png` (1280x900 viewport) via CDP. Verified 4-column aligned product grid, fixed-aspect image containers, clean typography hierarchy, and FastAPI status badge.
- [x] **Headless Edge Mobile Visual Verification:** Captured and visually inspected `screenshot_mobile.png` (390x844 viewport, mobile touch emulation) via CDP. Verified responsive header, horizontal category scrollbar hidden, hero section wraps cleanly, and product cards fit 100% of the mobile viewport.
- [x] **Cart Drawer Interaction Verification:** Captured and visually inspected `screenshot_cart_open.png` via automated item addition. Verified backdrop blur, quantity increment/decrement controls, line item total, subtotal, ethical trust banner, and checkout simulation CTA.
- [x] **Merchant Console Interactive Sliders:** Captured and visually inspected `screenshot_m4_merchant_console.png`. Verified live catalog statistics, category inventory table, and active policy sliders (`margin_floor`, `discount_cap`) persisted to SQLite.
- [x] **Engine A Recommender Invariants:** `test_recommender_never_recommends_item_already_in_cart`, `test_recommender_filters_out_of_stock_items`, and `test_recommender_prioritizes_explicit_complementary_link` passed cleanly.
- [x] **Engine B Financial Invariants:** `test_optimizer_strictly_enforces_gross_margin_floor` (fails discounts that breach margin floor), `test_optimizer_respects_discount_cap` (caps max discount), `test_optimizer_price_ceiling_and_non_negative_savings` (`final_price <= ref_price`, `savings >= 0`), and `test_optimizer_zero_revenue_safeguard` passed.
- [x] **Engine C End-to-End Orchestrator & API:** `test_orchestrator_sub_25ms_latency` (< 25ms SLA, recorded mean 3.80ms latency), `test_orchestrator_empty_cart_returns_safe_no_offer`, `test_independent_recommendation_and_incentive` (Option 1 verified: candidate shown with *"Standard price · No discount applied"* when margin floor is violated), and `test_api_endpoint_post_decision` passed.
- [x] **Gemini Asynchronous Service & Fallback (Milestone 4):** Implemented `POST /api/v1/explanation` with `GeminiExplanationService`. Verified attribute-grounded factual copy, 3.5s timeout protection, response caching, strict financial immutability (zero price/margin fields in explanation schema), and sub-5ms deterministic offline fallback.
- [x] **Product Experience Refinement & Persistence (Milestone 4):** Expanded catalogue to 32 verified products in SQLite with curated imagery. Added Shopping Intent selector with factual compatibility explanations. Implemented `TransparencyModal.tsx` and interactive `MerchantView.tsx` with active sliders (`margin_floor`, `discount_cap`) persisted to SQLite. Implemented automatic bundle discount revocation upon parent item removal in cart.
- [x] **Apriori Basket Association Mining Math (Milestone 4B):** `test_associations_math.py` verified hand-calculated support, raw confidence, Laplace-smoothed confidence ($\alpha=1.0$), bounded logarithmic lift, multi-item antecedent subsets ($|X| \le 3$), zero-denominator safeguards, and session-grouped 80/20 train/test splitting with zero cross-session leakage.
- [x] **Hybrid ML Recommender & MMR Diversity (Milestone 4B):** `test_hybrid_ml_recommender.py` passed 15 automated checks verifying $S_{hybrid}$ exact component weighting, non-cart exclusivity, interaction event exponential decay ($\tau=24.0$h), multi-attribute MMR diversity re-ranking, candidate feature vector extraction (14 features), HistGradientBoostingClassifier training/persistence, sub-millisecond fallback, and sub-25ms synchronous latency.
- [x] **Offline Recommendation Benchmark (Milestone 4B):** Evaluated across 400 held-out synthetic test sessions ($K=4$): HitRate@4 (`0.0625` baseline $\to$ `0.3075` hybrid, +392%), Recall@4 (`0.0625` $\to$ `0.3075`), NDCG@4 (`0.0351` $\to$ `0.2669`, +660%), catalog coverage (`90.62%` $\to$ `100.0%`), and average pairwise attribute similarity (`0.2148` $\to$ `0.1196`, confirming significantly more diverse sets).
- [x] **Three-Policy Simulation Comparator (Milestone 5):** `test_simulation_engine.py` passed 13 automated checks verifying 1,000 paired Common Random Numbers sessions, 9 distinct shopper archetypes, exact profit accounting, 0 margin floor breaches under FairCart AI vs 46 under Blanket 15%, and responsive embedded SVG visualization.
- [x] **Frequency-Aware Interaction Signals & Deliberate View (Milestone 5B):** `test_frequency_aware_signals.py` passed 12 automated checks verifying 5 views > 1 view ($0.8832$ vs $0.6457$), time decay, hover < view ($0.5475$ vs $0.6457$), bounded 50 hovers ($0.9723 < 1.0$), brief hover (<700ms) = 0.00, idempotency deduplication (`INSERT OR IGNORE`), and modal inspection.
- [x] **Production Multi-Stage Container Build (Milestone 6):** Created `Dockerfile` (Node 20 alpine builder + Python 3.12 slim runtime) and `.dockerignore`. Validated clean frontend bundle build outputting 99.3 kB gzip JS bundle.
- [x] **Content-Negotiated Root & SPA Static Mount (Milestone 6):** Verified via `TestClient(app)`: `Accept: application/json` returns API discovery status (`HTTP 200`), while `Accept: text/html` returns compiled `index.html` (`HTTP 200`). Client-side routes (e.g. `/merchant`) fallback cleanly to `index.html`.
- [x] **Compute Endpoint IP Rate Limiting (Milestone 6):** Validated in-memory sliding-window limiter on `POST /api/v1/simulate`: exactly 15 requests permitted within 60 seconds; 16th request rejected with `HTTP 429 Too Many Requests`.
- [x] **Administrative Guardrail & Session Token (Milestone 6):** Validated on `POST /api/v1/settings`: requests without valid `X-Admin-Token` or Bearer header return `HTTP 403 Forbidden`; requests with valid token return `HTTP 200 OK`. Verified that React frontend persists token exclusively in browser `sessionStorage`.
- [x] **Repository Secret Hygiene Audit (Milestone 6):** Audited `git ls-files` and git log: zero `.env` files, `.db` files, `.local` credential files, or `learner-profile.md` (private learner context) tracked in Git history.
- [x] **Demonstration Authentication & Session Security (Milestone 6B):** `test_demo_auth.py` passed 7 automated checks verifying 5 personas authenticate via Argon2id, invalid password rejection (401), session invalidation on logout, failed login rate limiting (5 failures -> 429), and zero customer privilege escalation on `/api/v1/settings` (403).
- [x] **Account Order History & Cross-Account Isolation (Milestone 6B):** `test_account_order_history.py` passed 4 automated checks verifying 3 itemized synthetic orders per persona, schema validity (status, provenance, items, savings), strict isolation (User A cannot access User B's order -> 404), and authenticated simulated checkout order persistence.
- [x] **Personalized Recommendations via Historical Order Anchors (Milestone 6B):** `test_personalized_recommendations.py` passed 3 automated checks verifying empty-basket recommendations for `demo_gamer` vs `demo_creator` surface distinct, defensible recommendations from their respective order history ($O_{gamer} \neq O_{creator}$), while guest requests have zero leaked order anchors.
- [x] **Pointer Dwell Reliability & Stale Response Discard (Milestone 6B):** `test_hover_reliability.py` passed 3 automated checks verifying dwell metadata capture, duplicate event deduplication, and 700ms contract. `App.tsx` incremental request sequence ref prevents out-of-order stale decision responses from overwriting newer recommendations.
- [x] **Consolidated Backend Test Suite:** All 118 unit tests in `backend/tests/` passed cleanly in 80.8s (100% pass rate, 0 failures, 0 errors).
- [x] **Real-Browser Edge CDP Automated Journey (Milestone 6B):** `verify_m6b_browser.cjs` executed full live browser test: verified 0 brief hover events (<700ms), 1 qualifying hover (>=700ms), quick-select pre-filling and show/hide password toggle, Alex Mercer signed-in header badge, Order History modal with 3 orders (8 items), account switch to Devon Reed with dynamic persona update, simulated checkout appending 4th order in history, and clean logout. Captured 4 screenshots: `screenshot_m6b_signed_in_gamer.png`, `screenshot_m6b_gamer_order_history.png`, `screenshot_m6b_signed_in_creator.png`, and `screenshot_m6b_new_checkout_in_order_history.png`.

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

This script is structured for a concise, compelling 2–3 minute video presentation:

- **0:00 – 0:35 (The Problem & Cold-Start Discovery):**
  - *Narration:* "Traditional e-commerce traps shoppers in deceptive countdown clocks and surveillance pricing, while independent merchants bleed profits on blunt 15%-off-everything sales. FairCart AI fixes this with ethical, margin-preserving intelligence."
  - *Screen Action:* Open the FairCart AI Storefront (`http://localhost:5173` or public URL). Note the empty cart. Show that FairCart AI immediately displays honest cold-start recommendations labeled *"Popular picks from our catalogue"*, respecting that with zero items in the cart, all products remain at standard price. Select the **"Productivity"** intent chip; observe the recommendations seamlessly re-rank around work essentials.

- **0:35 – 1:10 (Intentional Interaction & Deliberate Inspection):**
  - *Narration:* "Most recommendation systems treat an accidental mouse swipe the same as genuine interest. FairCart AI isolates genuine intent."
  - *Screen Action:* Hover over the *Ergonomic Mechanical Keyboard* ($80.00) for more than 900ms. Click the card or "Quick View" button to open the `ProductDetailModal`. Show rich product specs and category tags. Click "Add to Cart" directly from the modal.

- **1:10 – 1:45 (The FairCart Recommendation & Gemini Explanation):**
  - *Narration:* "Now that the basket has an item, FairCart AI's dual-engine pipeline activates."
  - *Screen Action:* Open the Cart Drawer. FairCart AI suggests the *Padded Wrist Rest* with a 10% bundle discount ($2.50 savings, $22.50 final price). Highlight the customer-facing Gemini explanation: *"Paired with your keyboard to support natural ergonomics and wrist alignment during long typing sessions."* Click the "How offers work" link to open `TransparencyModal.tsx`, showing shoppers the exact mathematical criteria behind their offer. Click "Add to Cart" to accept the bundle.

- **1:45 – 2:20 (The Merchant Console & Margin Guardrail Protection):**
  - *Narration:* "Now let's switch to the merchant's perspective. How does the store owner maintain control?"
  - *Screen Action:* Navigate to the Merchant Console. Point to the live catalog metrics (32 products, 980 association rules). Click "Admin Key" and demonstrate session-stored authentication. Drag the **Margin Floor** slider from 15% up to 45% and click "Save Policy Guardrails". Return to the cart drawer: watch the wrist rest dynamically update to *"Standard price · No discount applied"* ($25.00) because the discount would violate the merchant's new 45% profit floor!

- **2:20 – 2:45 (Three-Policy Economic Simulation Comparator):**
  - *Narration:* "Does this actually make business sense? Let's prove it with data."
  - *Screen Action:* In the Merchant Console, scroll to the Three-Policy Simulation Comparator. Run 1,000 synthetic shopping sessions across 9 shopper archetypes. Point to the comparative metrics and SVG chart:
    - *No Discount:* Safe margins, but low basket conversion.
    - *Blanket 15%:* 46 margin-floor violations and eroded profits.
    - *FairCart AI:* **Zero margin-floor breaches**, +$1,200 higher contribution profit, and higher customer conversion.

- **2:45 – 3:00 (Transparent Checkout & Closing):**
  - *Narration:* "Shoppers get genuine savings and complete transparency. Merchants protect their bottom line. That's FairCart AI."
  - *Screen Action:* Click "Proceed to Checkout". Show the itemized zero-payment receipt with transparent savings and ethical trust disclosure. Conclude presentation.

---

## 8. Judge-Facing Project Story (Devpost Submission Copy)

### Inspiration
Online shopping has become an obstacle course of deceptive countdown clocks, artificial "Only 1 left in stock!" alerts, and predatory surveillance pricing algorithms that track shoppers across the web to extract maximum prices. Meanwhile, independent merchants struggle with blunt, margin-destroying sales (like blanket "15% off everything" coupon codes) that cannibalize revenue without building customer loyalty.

We asked a fundamental question: **Can artificial intelligence optimize e-commerce value collaboratively—protecting merchant profit margins while giving shoppers genuine, transparent, and unmanipulated value?**

### What It Does
FairCart AI is an ethical, margin-preserving e-commerce recommendation and incentive optimization engine. Rather than optimizing for maximum short-term extraction, FairCart AI pairs product discovery with mathematically constrained economic incentives:

1. **Hybrid Discovery Intelligence:** Integrates Apriori association-rule mining, explicit shopping intent context, time-decayed interaction signals, a supervised HistGradientBoostingClassifier, and Maximal Marginal Relevance (MMR) diversity reranking across 32 curated products.
2. **Cold-Start & Empty-Basket Discovery:** Recommends relevant catalog items before the cart is filled, with clear provenance badges ("Popular picks from our catalogue"), while strictly guaranteeing zero unearned discounts on empty baskets.
3. **Mathematically Guaranteed Margin Floors:** The merchant sets an immutable profit floor (e.g., 20%) and discount cap. FairCart AI will *never* offer a discount that breaches this floor, treating the base catalog price as an unbreakable ceiling.
4. **Explainable AI with Gemini:** Google Gemini 2.5 Flash explains why each product was recommended using grounded physical attributes (with sub-5ms deterministic offline fallback and response caching).
5. **Interactive Merchant Console:** Allows store owners to inspect live catalog statistics, adjust policy guardrails in real time, and audit algorithmic decisions.
6. **Three-Policy Economic Simulator:** A built-in Monte Carlo comparator that evaluates 1,000 shopper sessions across 9 behavioral archetypes, proving that FairCart AI protects gross margins and generates higher contribution profit than blanket discounts.

### How It Was Built
- **Backend & Decision Engines:** Built with **Python 3.12**, **FastAPI**, **Pydantic v2**, and **SQLite**. The system executes full multi-candidate ranking and margin optimization in under 5ms (well below our 25ms SLA).
- **Machine Learning & RecSys:** Implemented custom Apriori association mining (980 rules), exponential time-decay interest modeling ($\tau = 24.0$h), a 14-feature contextual candidate representation, and scikit-learn's `HistGradientBoostingClassifier` with MMR diversity reranking ($\lambda = 0.75$).
- **Frontend & User Experience:** Built with **React 19**, **TypeScript**, **Vite**, and **Tailwind CSS**. Features responsive desktop/mobile layouts, accessible modals, intentional hover dwell detection ($\ge 900$ms), and browser-persisted state.
- **Generative AI:** Google Gemini 2.5 Flash API for customer-facing natural language explanations, paired with sub-5ms factual fallbacks and strict financial schema immutability.
- **Production Architecture:** Unified multi-stage container (`Dockerfile`) compiling React into a Python 3.12 runtime with self-healing startup seeding, content-negotiated routing, and sliding-window IP rate limiting.

### Challenges We Ran Into
- **Binary Dependency Incompatibilities:** During Milestone 4, FastAPI and Pydantic encountered binary schema mismatches with `pydantic-core`. We resolved this by explicitly pinning `pydantic-core==2.27.2` and isolating Uvicorn reload directories (`--reload-dir backend`).
- **Incidental Pointer Noise:** Early hover tracking triggered events whenever a user moved their mouse across cards. We engineered a 900ms pointer dwell accumulator with episode IDs and keyboard focus support to isolate genuine inspection from noise.
- **Mathematical Multi-Item Optimization:** Ensuring that bundle discounts never breach the basket margin floor required rigorous closed-form equations where line-item contribution profits are checked holistically against reference prices.
- **Ephemeral Cloud Storage vs Data Durability:** Free container platforms wipe local files on idle sleep. We engineered an idempotent self-healing startup hook in FastAPI that validates and re-seeds catalog items and rules in <200ms on cold boot.

### Accomplishments That We're Proud Of
- **101 Automated Unit Tests:** 100% pass rate across database, catalog, recommender math, economic optimizer, simulation engine, and frequency-aware signals.
- **Sub-5ms Decision Latency:** Achieved a mean execution time of 3.80ms for hybrid ML scoring and margin optimization.
- **Empirical RecSys Uplift:** Held-out benchmark tests demonstrated a +392% HitRate@4 improvement and +660% NDCG@4 improvement over 1-to-1 baseline recommendations, with 100% catalog coverage.
- **Zero-Breach Simulation:** 1,000-session Monte Carlo evaluation proved 0 margin-floor breaches under FairCart AI versus 46 breaches under Blanket 15% discounting.
- **Responsible AI Architecture:** Clear ethical boundaries: zero tracking cookies, zero PII, base price ceiling guarantee, and full transparency disclosures.

### What We Learned (Devpost Learn Reflections)
Building FairCart AI through the Devpost Learn framework reinforced the value of a **plan-first workflow**:
- Taking time to define the core journey and economic kernel in `scope.md` and `prd.md` before writing code prevented scope creep and architectural rework.
- Separating recommendation scoring (Engine A) from economic margin optimization (Engine B) kept the system modular and testable.
- Real AI in commerce must be governed by deterministic business rules: while generative models like Gemini excel at communication, financial boundaries must be enforced by immutable code.

### What's Next for FairCart AI
- **Shopify & WooCommerce App Extension:** Packaging the FairCart AI engine as a turnkey plug-in for independent merchants.
- **Online Contextual Bandits:** Extending the offline HistGBM ranker with LinUCB or Thompson Sampling for safe online exploration.
- **Federated Privacy-Preserving Personalization:** Training cross-merchant interaction embeddings using differential privacy without sharing customer interaction logs.

### Built With
- Python 3.12 & FastAPI
- React 19 & TypeScript
- Google Gemini 2.5 Flash
- scikit-learn & NumPy
- SQLite (WAL Mode) & Neon Serverless PostgreSQL (Dual Drivers)
- Vite & Tailwind CSS
- Docker (Multi-Stage Container)

---

## 9. Milestone 6C: Security Hardening, Public Deployment & Devpost Submission Readiness Audit

> **Checkpoint:** Milestone 6C Release Candidate  
> **Verification Date & Time:** October 15, 2026, 23:05 IST  
> **Automated Backend Tests:** **131 / 131 tests passing** (0 failures, 0 errors in 89.5s)  
> **Frontend Production Build:** Built cleanly in 8.62s (0 type errors, 99.55 kB gzip JS)  
> **Open Source License:** Verified MIT License ([`LICENSE`](../LICENSE))  
> **Documentation:** Complete production [`README.md`](../README.md) and [`devpost/submission-readiness.md`](submission-readiness.md)

### 9.1 Security Audit & Credential Hygiene Remediation
1. **Demo Credential Redaction:**
   - Modified `GET /api/v1/auth/demo-personas` to return strictly public persona metadata (`id`, `username`, `display_name`, `tag`, `persona_description`).
   - Removed `.local/demo-credentials.local.md` file reading entirely from the API response layer. Plaintext passwords, hashes, and session tokens are never returned.
2. **Dedicated Whitelisted Demo Authentication:**
   - Implemented `POST /api/v1/auth/demo-login` taking payload `{"persona": "demo_gamer"}`.
   - Enforces a strict whitelist: `{"demo_gamer", "demo_student", "demo_creator", "demo_traveler", "demo_office"}`. Rejects all arbitrary usernames with `HTTP 400 Bad Request`.
   - Protected by sliding-window rate limiting (max 15 requests per minute per IP) returning `HTTP 429 Too Many Requests`.
   - Guaranteed zero merchant-administrative privileges.
3. **Session Security & Transport:**
   - Standardized on secure HttpOnly cookies (`faircart_session`) with `SameSite=Lax` and `Secure=True` in production HTTPS as the primary security layer against XSS token harvesting.
   - `extract_session_token` prioritizes HttpOnly cookies, followed by standard `Authorization: Bearer <token>` for API evaluation.
   - Explicit session termination in `POST /api/v1/auth/logout` deletes server session records and clears client cookies.
4. **Merchant Administrative Guardrail Defense-in-Depth:**
   - In `POST /api/v1/settings`: explicitly detects customer session tokens and rejects with `HTTP 403 Forbidden` ("Customer session tokens cannot be used to modify merchant policies").
   - Requires independent merchant `ADMIN_TOKEN` when configured; blocks unauthenticated modifications in production.
5. **Build Context & Repository Secret Hygiene:**
   - Updated `.dockerignore` and `.gitignore` to strictly exclude `.local/`, `*.local.md`, `.env*`, and `devpost/learner-profile.md`.
   - Scanned full Git history: zero committed API keys (`AIza...`), zero credentials, zero `.db` files.

### 9.2 Persistence Architecture: Dual-Driver Engine (SQLite + Neon PostgreSQL)
- **Zero-Cost Constraint:** No paid compute, no paid database plans, no credit card required.
- **Dual Runtimes:**
  * **SQLite (Default):** Zero configuration. Auto-seeded on startup with 32 curated products, 980 association rules, 5 demo accounts, and 15 itemized past orders.
  * **Neon Serverless PostgreSQL (Option B):** Connected via `DATABASE_URL=postgresql://...`. Translates SQLite dialect (`?` placeholders to `%s`, `INSERT OR REPLACE` to `ON CONFLICT DO UPDATE`, `INSERT OR IGNORE` to `ON CONFLICT DO NOTHING`).
- **Restart & Failure Resilience:**
  * Verified data survival across simulated restarts in `test_database_persistence.py`.
  * Verified graceful fallback to local SQLite when PostgreSQL is unreachable (`test_unreachable_postgres_url_falls_back_gracefully_to_sqlite`).

### 9.3 Devpost Deliverables Audit Summary

| Deliverable | Path | Status | Verification Note |
| :--- | :--- | :--- | :--- |
| **Scope Document** | `devpost/scope.md` | **PASS** | Approved frontmatter; defines Unique Kernel and Margin Invariants. |
| **Product Requirements** | `devpost/prd.md` | **PASS** | Approved frontmatter; details Shopper & Merchant journeys and features. |
| **Technical Blueprint** | `devpost/spec.md` | **PASS** | Approved frontmatter; specifies 10-stage ranking and decoupled Gemini API. |
| **Build Checklist** | `devpost/checklist.md` | **PASS** | Tracks all 8 build slices with git commit checkpoints. |
| **App Map** | `devpost/app-map.html` | **PASS** | 340 lines standalone interactive HTML route & component visualizer. |
| **Deployment Architecture** | `devpost/deployment-and-persistence.md` | **PASS** | Specifies zero-cost cloud containerization and persistence models. |
| **Submission Audit** | `devpost/submission-readiness.md` | **PASS** | Complete forensic audit against Devpost Build With AI: Basics rules. |
| **README** | `README.md` | **PASS** | Full architectural overview, quickstart, demo guide, and container specs. |
| **Open Source License** | `LICENSE` | **PASS** | Permissive MIT License in root. |
| **Protected Files** | `devpost/learner-profile.md`, `.local/` | **PROTECTED** | Strictly excluded from Git and Docker images. |

### 9.4 Verified Test Suite Results (Milestone 6C)

```text
Ran 131 tests in 89.530s

OK (131/131 tests passing, 0 failures, 0 errors)
- test_demo_auth.py (12 tests): Redacted credentials, 5 demo logins, 400 rejection, 429 rate limit, 403 admin isolation.
- test_database_persistence.py (8 tests): SQL dialect translation, DictRowCompat, restart persistence, connection fallback.
- test_account_order_history.py (4 tests): 15 synthetic orders, cross-account 404, simulated checkout persistence.
- test_personalized_recommendations.py (3 tests): Persona divergence (Gamer vs Creator), zero guest leakage.
- test_hover_reliability.py (3 tests): 700ms dwell threshold, touch filtering, internal child protection.
- test_context_aware_engine.py (17 tests): Intent filtering, multi-item bundles, margin floor enforcement.
- test_decision_engine.py (16 tests): Invariant tests, quote accuracy, sub-25ms response SLA.
- test_empty_basket_recommendations.py (14 tests): Candidate provenance, zero unearned discounts on empty carts.
- test_simulation_engine.py (11 tests): 3-policy simulation comparator, Common Random Numbers reproducibility.
- test_foundation.py (9 tests): Operational health probe, SQLite catalog schema integrity.
- test_associations_math.py (8 tests): Apriori support, Laplace confidence, bounded lift.
- test_explanation_api.py (7 tests): Gemini dual-mode, 3.5s timeout, deterministic offline fallback.
- test_catalog_api.py (6 tests): Catalog endpoint, product schemas, CORS headers.
- test_frequency_aware_signals.py (7 tests): Interaction frequency signals, exponential time decay.
- test_hybrid_ml_recommender.py (6 tests): HistGBM ranking, MMR diversity reranking.
```

---

## 10. Milestone 6D: Final Release Verification, Database Durability Safeguards & Devpost Submission Preparation

> **Release Checkpoint:** Milestone 6D Release Candidate (commit `fa7e73b` + durability hardening)  
> **Verification Date & Time:** October 15, 2026, 23:35 IST  
> **Automated Backend Tests:** **135 / 135 tests passing** (0 failures, 0 errors in 35.417s)  
> **Frontend Production Build:** Built cleanly in 7.38s (0 type errors, 99.55 kB gzip JS, 6.65 kB gzip CSS)  
> **Git Secret Hygiene:** Verified zero committed API keys (`AIzaSy...`), zero passwords, zero `.db` files across full git history.

### 10.1 Resolution of Test Execution Status & Fresh Baseline
- In the initial turn, the test suite was started as an asynchronous background task due to runtime exceeding the immediate response window, generating a transient "awaiting test completion" notification.
- Upon completion, the task output was delivered directly: `Ran 131 tests in 91.700s — OK`.
- For Milestone 6D, we executed a fresh, authoritative run of the full test suite (`python -m unittest discover -s backend/tests -p "test_*.py"`):
  ```text
  Ran 135 tests in 35.417s — OK (0 failures, 0 errors, exit code: 0)
  ```
- The test count expanded from 131 to 135 to explicitly cover:
  1. Safe credential masking (`mask_db_url`) preventing password leakage in logs.
  2. Production-mode strict startup error on PostgreSQL failure (no silent ephemeral SQLite fallback).
  3. Dynamic PostgreSQL / SQLite health probe reporting HTTP 503 on database disconnect.
  4. PostgreSQL wrapper query and order translation with row compatibility.

### 10.2 Production Database Durability & Safe Error Handling
- **The Problem:** In containerized serverless hosting (e.g., Render Free Web Service), the container filesystem is ephemeral and wiped upon every 15-minute idle spin-down. If a production deployment configured for PostgreSQL silently falls back to local SQLite on connection error, all custom merchant settings and simulated orders would be lost on the next container sleep.
- **The Solution:**
  1. **Strict Production Failure:** In production (`ENVIRONMENT=production` or `allow_fallback=False`), a failed PostgreSQL connection raises a clear `RuntimeError` halting startup immediately. This signals an unhealthy deployment to the platform rather than quietly storing state in ephemeral storage.
  2. **Safe Credential Masking:** Implemented `mask_db_url()` to completely scrub user credentials (e.g. `postgresql://***:***@ep-xyz.aws.neon.tech/neondb`) from logs, console messages, and exception traces.
  3. **Dynamic Health Probe:** `GET /api/v1/health` verifies database connectivity dynamically: reports `database="postgresql"` when active, and sets HTTP 503 Service Unavailable with `status="unhealthy"` if database queries fail.
  4. **Adapter Unit Tests vs Integration Tests:** 11 unit tests in `test_database_persistence.py` verify ANSI SQL dialect translation, row indexing, restart persistence, and failure prevention. Integration testing against a live remote database requires configuring `DATABASE_URL` with a valid Neon Serverless PostgreSQL connection string.

### 10.3 Forensic Skill Pack Adherence & Devpost Submission Status
- Forensic repository inspection confirmed `skills-lock.json` has tracked all 6 official skills from `challengepost/learn-ai-basics` since Milestone 1 (commit `957c0fe`).
- All 5 planning and visualization artifacts (`scope.md`, `prd.md`, `spec.md`, `checklist.md`, `app-map.html`) exist in `devpost/` with approved frontmatter and match the implemented codebase.




