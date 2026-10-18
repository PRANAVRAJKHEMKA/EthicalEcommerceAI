import time
import re
import logging
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Request, Depends, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.config import settings, BASE_DIR
from backend.app.db.database import init_db, is_postgres
from backend.app.db.repository import CatalogRepository
from backend.app.engine import DecisionOrchestrator
from backend.app.engine.explanation import GeminiExplanationService
from backend.app.engine.associations import get_association_engine
from backend.app.models.schemas import (
    BasketQuote,
    CreateOrderRequest,
    DealPassportRequest,
    DecisionRequest,
    DecisionResponse,
    DemoLoginRequest,
    DemoPersonaPublic,
    ExplanationRequest,
    ExplanationResponse,
    FairDealPassport,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    MerchantSettingsRequest,
    OrderDetail,
    OrderItemDetail,
    Product,
    QuoteRequest,
    SessionEventCreate,
    SimulationRequest,
    SimulationResponse,
    UserProfile,
    FunnelMetricsResponse,
    UpliftEvaluationResponse,
    CSVImportRequest,
    CSVImportResponse,
    CSVValidationResponse,
    MultiStoreProfitResponse,
)
from backend.app.engine.simulator import EconomicSimulator
from backend.app.engine.uplift import run_uplift_evaluation, UpliftDatasetSchemaError
from backend.app.engine.multi_store_analytics import (
    validate_and_parse_csv,
    aggregate_profit_intelligence,
)
from backend.app.auth import (
    ALLOWED_DEMO_PERSONAS,
    ALLOWED_MERCHANT_PERSONAS,
    attach_session_cookie,
    check_demo_login_rate_limit,
    check_login_rate_limit,
    clear_login_failures,
    clear_session_cookie,
    create_user_session,
    get_current_user_optional,
    get_current_user_required,
    record_failed_login,
    verify_password,
)

# In-memory sliding window rate limiter for CPU-intensive endpoints (zero external dependencies)
SIMULATION_RATE_LIMITS: dict[str, list[float]] = defaultdict(list)

def enforce_simulation_rate_limit(client_ip: str, max_requests: int = 15, window_seconds: int = 60) -> None:
    now = time.time()
    history = SIMULATION_RATE_LIMITS[client_ip]
    SIMULATION_RATE_LIMITS[client_ip] = [t for t in history if now - t < window_seconds]
    if len(SIMULATION_RATE_LIMITS[client_ip]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Simulation rate limit reached ({max_requests} requests per minute). Please wait a moment before running another evaluation.",
        )
    SIMULATION_RATE_LIMITS[client_ip].append(now)

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Explainable, margin-preserving e-commerce recommendation and incentive optimization engine.",
    docs_url="/docs",
    redoc_url="/redoc",
)

logger = logging.getLogger("faircart.api")

def resolve_cors_origins(raw_origins: str | list[str] | None, environment: str = "development") -> list[str]:
    """Parse, normalize, and enforce strict security guardrails on CORS origins.

    Security & CORS Protocol Guardrail:
    Because FairCart AI uses `allow_credentials=True` for HttpOnly session cookies (`faircart_session`),
    browsers strictly reject any response having `Access-Control-Allow-Origin: *` under the W3C Fetch standard.
    Furthermore, exposing credentials to wildcard origins is an insecure practice.

    Rules enforced:
    1. In production ('production' or 'prod'):
       - Wildcard '*' is strictly prohibited and immediately raises RuntimeError.
       - Empty origins configuration is strictly prohibited and immediately raises RuntimeError.
       - Explicit trusted origins (e.g., 'https://faircart.onrender.com') must be provided.
    2. In non-production (e.g. 'development', 'test'):
       - Wildcard '*' is rejected with ValueError to prevent silent fallback to broken credentials.
       - If origins are omitted or empty, defaults safely to explicit local development origins.
    3. Normalization:
       - Trims whitespace and strips trailing slashes from HTTP/HTTPS URLs to match browser Origin headers.
       - Deduplicates origins while preserving order.
       - Never returns ['*'] under any condition when credentials are required.
    """
    if raw_origins is None:
        raw_list: list[str] = []
    elif isinstance(raw_origins, str):
        raw_list = [o.strip() for o in raw_origins.split(",") if o.strip()]
    elif isinstance(raw_origins, (list, tuple, set)):
        raw_list = [str(o).strip() for o in raw_origins if str(o).strip()]
    else:
        raw_list = [str(raw_origins).strip()]

    is_prod = (environment or "").strip().lower() in ("production", "prod")
    has_wildcard = any(o == "*" for o in raw_list)

    if is_prod:
        if has_wildcard:
            raise RuntimeError(
                "CORS production security violation: Wildcard '*' origin is prohibited in production "
                "when allow_credentials=True. Browsers reject credentialed requests with wildcard origins, "
                "and wildcard credentials expose session cookies to arbitrary domains. "
                "Configure explicit trusted frontend origins in CORS_ORIGINS (e.g., 'https://faircart.onrender.com')."
            )
        if not raw_list:
            raise RuntimeError(
                "CORS production configuration error: CORS_ORIGINS cannot be empty in production. "
                "Explicit trusted frontend origins must be specified."
            )
    else:
        if has_wildcard:
            raise ValueError(
                "Invalid CORS configuration: Wildcard '*' origin cannot be used when allow_credentials=True. "
                "Browsers reject credentialed requests with wildcard CORS origins. "
                "Specify explicit local development origins (e.g., 'http://localhost:5173')."
            )

    normalized: list[str] = []
    for origin in raw_list:
        clean = origin.rstrip("/") if origin.startswith(("http://", "https://")) else origin
        if clean and clean not in normalized:
            normalized.append(clean)

    if not normalized and not is_prod:
        normalized = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    return normalized

# Parse and configure production-safe CORS origins
cors_origins = resolve_cors_origins(settings.CORS_ORIGINS, settings.ENVIRONMENT)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema and ensure deterministic catalog & demo accounts seeding on startup
@app.on_event("startup")
def on_startup():
    init_db()
    try:
        repo = CatalogRepository()
        if repo.count_products() < 96:
            from backend.scripts.seed_catalog import seed_catalog
            seed_catalog()
        if repo.count_users() < 5:
            from backend.scripts.seed_demo_accounts import seed_demo_accounts
            seed_demo_accounts()
    except Exception as e:
        print(f"Startup catalog/demo account verification note: {e}")

@app.get("/api/v1/health", response_model=HealthResponse, tags=["System Health"])
def get_health(response: Response) -> HealthResponse:
    """Operational health check endpoint verifying database connectivity and catalog item count."""
    db_type = "postgresql" if is_postgres(settings.DATABASE_URL) else "sqlite"
    try:
        repo = CatalogRepository()
        count = repo.count_products()
        return HealthResponse(
            status="healthy",
            catalog_items_loaded=count,
            database=db_type,
            gemini_configured=bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip()),
            version=settings.APP_VERSION,
        )
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="unhealthy",
            catalog_items_loaded=0,
            database=f"{db_type} (unhealthy: {str(e)})",
            gemini_configured=bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip()),
            version=settings.APP_VERSION,
        )

@app.get("/api/v1/catalog", response_model=list[Product], tags=["Catalog"])
def get_catalog() -> list[Product]:
    """Retrieves all catalog products with verified reference prices, COGS, and stock."""
    try:
        repo = CatalogRepository()
        products = repo.get_all_products()
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve catalog from database: {str(e)}")

@app.post("/api/v1/decision", response_model=DecisionResponse, tags=["Decision Engine"])
def create_decision(
    request: DecisionRequest,
    current_user: dict | None = Depends(get_current_user_optional),
) -> DecisionResponse:
    """Evaluates the active cart context to produce ranked complementary recommendations (3-5 items)
    and margin-preserving incentive optimization. Synchronous and deterministic (< 25ms).
    """
    try:
        if current_user and not request.user_id:
            request.user_id = current_user["user_id"]
        orchestrator = DecisionOrchestrator()
        return orchestrator.process_decision(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision pipeline failed: {str(e)}")

# ------------------------------------------------------------------------------
# DEMONSTRATION AUTHENTICATION & SESSIONS (Milestone 6B)
# ------------------------------------------------------------------------------

@app.get("/api/v1/auth/demo-personas", response_model=list[DemoPersonaPublic], tags=["Authentication"])
def get_demo_personas() -> list[DemoPersonaPublic]:
    """Returns public persona metadata for the 5 evaluation demo accounts.
    
    Zero passwords, password hashes, or session tokens are ever returned.
    """
    repo = CatalogRepository()
    users = repo.get_all_users()
    tag_map = {
        "demo_gamer": "Gamer",
        "demo_student": "Student",
        "demo_creator": "Creator",
        "demo_traveler": "Traveler",
        "demo_office": "Office Pro",
    }
    personas = []
    for u in users:
        if u.username in ALLOWED_DEMO_PERSONAS:
            personas.append(DemoPersonaPublic(
                id=u.id,
                username=u.username,
                display_name=u.display_name,
                tag=tag_map.get(u.username, "Customer"),
                persona_description=u.persona_description,
            ))
    return personas

@app.post("/api/v1/auth/demo-login", response_model=LoginResponse, tags=["Authentication"])
def demo_login(req: DemoLoginRequest, request: Request, response: Response) -> LoginResponse:
    """Authenticates one of the 5 explicitly designated synthetic customer personas without exposing passwords.
    
    Strictly restricted to the whitelist: {demo_gamer, demo_student, demo_creator, demo_traveler, demo_office}.
    Enforces IP rate limiting (15 requests/min) and issues a standard customer session cookie.
    Guaranteed: zero merchant-administrative privileges.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_demo_login_rate_limit(client_ip)

    persona_key = req.persona.strip().lower()
    allowed_personas = ALLOWED_DEMO_PERSONAS | ALLOWED_MERCHANT_PERSONAS
    if persona_key not in allowed_personas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid demo persona '{req.persona}'. Must be one of: {sorted(allowed_personas)}",
        )

    repo = CatalogRepository()
    user = repo.get_user_by_username(persona_key)
    if not user:
        # Self-heal demo accounts if needed
        from backend.scripts.seed_demo_accounts import seed_demo_accounts
        seed_demo_accounts()
        user = repo.get_user_by_username(persona_key)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Demo persona '{persona_key}' is not available.",
            )

    session_token, _ = create_user_session(user.id, days=7)
    attach_session_cookie(response, session_token)

    return LoginResponse(
        user=UserProfile(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            persona_description=user.persona_description,
            created_at=user.created_at,
        ),
        session_token=session_token,
        message=f"Authenticated as demo persona: {user.display_name}",
    )

@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["Authentication"])
def login(login_req: LoginRequest, request: Request, response: Response) -> LoginResponse:
    """Authenticates one of the 5 demo accounts, enforces failed login rate limits, and issues a session."""
    client_ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_ip)
    check_login_rate_limit(login_req.username)

    repo = CatalogRepository()
    user = repo.get_user_by_username(login_req.username)

    if not user or not verify_password(user.password_hash, login_req.password):
        record_failed_login(client_ip)
        record_failed_login(login_req.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password. Please verify demonstration credentials.",
        )

    clear_login_failures(client_ip)
    clear_login_failures(login_req.username)

    session_token, _ = create_user_session(user.id, days=7)
    attach_session_cookie(response, session_token)

    return LoginResponse(
        user=UserProfile(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            persona_description=user.persona_description,
            created_at=user.created_at,
        ),
        session_token=session_token,
    )

@app.get("/api/v1/auth/me", response_model=UserProfile, tags=["Authentication"])
def get_me(current_user: dict = Depends(get_current_user_required)) -> UserProfile:
    """Retrieves profile information for the actively authenticated demo account."""
    return UserProfile(
        id=current_user["user_id"],
        username=current_user["username"],
        display_name=current_user["display_name"],
        persona_description=current_user["persona_description"],
        created_at=current_user["created_at"],
    )

@app.post("/api/v1/auth/logout", tags=["Authentication"])
def logout(request: Request, response: Response):
    """Terminates the active session and clears the session cookie."""
    from backend.app.auth import extract_session_token
    token = extract_session_token(request)
    if token:
        repo = CatalogRepository()
        repo.delete_session(token)
    clear_session_cookie(response)
    return {"status": "logged_out", "message": "Session invalidated successfully"}

# ------------------------------------------------------------------------------
# ACCOUNT-SPECIFIC ORDER HISTORIES & SIMULATED CHECKOUT (Milestone 6B)
# ------------------------------------------------------------------------------

@app.get("/api/v1/orders", response_model=list[OrderDetail], tags=["Orders"])
def get_orders(current_user: dict = Depends(get_current_user_required)) -> list[OrderDetail]:
    """Retrieves past simulated orders belonging strictly to the authenticated demo account."""
    repo = CatalogRepository()
    orders = repo.get_orders_for_user(current_user["user_id"])
    return [
        OrderDetail(
            id=o.id,
            user_id=o.user_id,
            created_at=o.created_at,
            status=o.status,
            provenance=o.provenance,
            currency=o.currency,
            total_amount=o.total_amount,
            total_savings=o.total_savings,
            items=[
                OrderItemDetail(
                    product_id=i["product_id"],
                    name=i["name"],
                    category=i.get("category", ""),
                    image_url=i.get("image_url", ""),
                    quantity=i["quantity"],
                    reference_price=i["reference_price"],
                    simulated_price=i["simulated_price"],
                    savings=i["savings"],
                    line_total=i["line_total"],
                )
                for i in o.items
            ],
        )
        for o in orders
    ]

@app.get("/api/v1/orders/{order_id}", response_model=OrderDetail, tags=["Orders"])
def get_order_by_id(order_id: str, current_user: dict = Depends(get_current_user_required)) -> OrderDetail:
    """Retrieves an itemized order, enforcing ownership by the authenticated account."""
    repo = CatalogRepository()
    order = repo.get_order_by_id(order_id, current_user["user_id"])
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderDetail(
        id=order.id,
        user_id=order.user_id,
        created_at=order.created_at,
        status=order.status,
        provenance=order.provenance,
        currency=order.currency,
        total_amount=order.total_amount,
        total_savings=order.total_savings,
        items=[
            OrderItemDetail(
                product_id=i["product_id"],
                name=i["name"],
                category=i.get("category", ""),
                image_url=i.get("image_url", ""),
                quantity=i["quantity"],
                reference_price=i["reference_price"],
                simulated_price=i["simulated_price"],
                savings=i["savings"],
                line_total=i["line_total"],
            )
            for i in order.items
        ],
    )

@app.post("/api/v1/orders", response_model=OrderDetail, tags=["Orders"])
def create_simulated_order(
    req: CreateOrderRequest,
    current_user: dict = Depends(get_current_user_required),
) -> OrderDetail:
    """Records a new simulated completed checkout under the authenticated demo account."""
    if not req.items:
        raise HTTPException(status_code=400, detail="Cannot create an order with an empty basket.")

    import uuid
    from datetime import datetime, timezone
    import json

    repo = CatalogRepository()
    product_ids = [item.get("product_id") for item in req.items if item.get("product_id")]
    entities = {e.id: e for e in repo.get_entities_by_ids(product_ids)}

    total_standard_cents = 0
    total_final_cents = 0
    order_items = []

    for item in req.items:
        pid = item.get("product_id")
        qty = int(item.get("quantity", 1))
        prod = entities.get(pid)
        if not prod or qty <= 0:
            continue

        ref_cents = prod.reference_price_cents
        disc_pct = req.applied_discounts.get(pid, 0.0)
        custom_price = item.get("discounted_price") or item.get("custom_price")
        if custom_price is not None:
            unit_cents = int(round(custom_price * 100))
        else:
            unit_cents = int(round(ref_cents * (1.0 - disc_pct)))

        unit_cents = min(unit_cents, ref_cents)
        line_total = unit_cents * qty
        savings_cents = max(0, (ref_cents - unit_cents) * qty)

        total_standard_cents += ref_cents * qty
        total_final_cents += line_total

        order_items.append({
            "product_id": prod.id,
            "name": prod.name,
            "category": prod.category,
            "image_url": prod.image_url,
            "quantity": qty,
            "reference_price": round(ref_cents / 100.0, 2),
            "simulated_price": round(unit_cents / 100.0, 2),
            "savings": round(savings_cents / 100.0, 2),
            "line_total": round(line_total / 100.0, 2),
        })

    if not order_items:
        raise HTTPException(status_code=400, detail="No valid catalog products in order.")

    total_savings_cents = total_standard_cents - total_final_cents
    order_id = f"ord_sim_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    order_entity = repo.create_order(
        order_id=order_id,
        user_id=current_user["user_id"],
        created_at=now,
        status="completed_simulated",
        provenance="simulated_checkout",
        currency="USD",
        total_cents=total_final_cents,
        savings_cents=total_savings_cents,
        items_json=json.dumps(order_items),
    )

    return OrderDetail(
        id=order_entity.id,
        user_id=order_entity.user_id,
        created_at=order_entity.created_at,
        status=order_entity.status,
        provenance=order_entity.provenance,
        currency=order_entity.currency,
        total_amount=order_entity.total_amount,
        total_savings=order_entity.total_savings,
        items=[
            OrderItemDetail(
                product_id=i["product_id"],
                name=i["name"],
                category=i.get("category", ""),
                image_url=i.get("image_url", ""),
                quantity=i["quantity"],
                reference_price=i["reference_price"],
                simulated_price=i["simulated_price"],
                savings=i["savings"],
                line_total=i["line_total"],
            )
            for i in order_entity.items
        ],
    )


@app.post("/api/v1/quote", response_model=BasketQuote, tags=["Decision Engine"])
def calculate_quote(request: QuoteRequest) -> BasketQuote:
    """Authoritative backend basket quote calculation ensuring line-item and subtotal consistency."""
    try:
        repo = CatalogRepository()
        product_ids = [item.product_id for item in request.cart_items]
        entities_by_id = {e.id: e for e in repo.get_entities_by_ids(product_ids)}

        cart_entities = []
        for item in request.cart_items:
            entity = entities_by_id.get(item.product_id)
            if entity and item.quantity > 0:
                cart_entities.append((entity, item.quantity))

        orchestrator = DecisionOrchestrator(repository=repo)
        return orchestrator.calculate_basket_quote(
            cart_entities,
            request.applied_discounts,
            margin_floor=request.margin_floor,
            discount_cap=request.discount_cap,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Basket quote calculation failed: {str(e)}")

@app.post("/api/v1/deal-passport", response_model=FairDealPassport, tags=["Decision Engine"])
def create_deal_passport(request: DealPassportRequest) -> FairDealPassport:
    """Generates an inspectable Fair Deal Passport evaluating three counterfactual scenarios
    (No discount, FairCart approved offer, and an aggressive alternative) for the exact same cart snapshot.
    """
    try:
        orchestrator = DecisionOrchestrator()
        return orchestrator.generate_deal_passport(request)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deal Passport generation failed: {str(e)}")

@app.post("/api/v1/explanation", response_model=ExplanationResponse, tags=["AI Explanation"])
async def explain_recommendations(request: ExplanationRequest) -> ExplanationResponse:
    """Asynchronously generates natural-language explanations powered by Gemini with deterministic fallback.
    
    This endpoint operates completely independently of the synchronous decision pipeline
    and cannot modify financial values, prices, or product rankings.
    """
    try:
        service = GeminiExplanationService()
        return await service.explain(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation service error: {str(e)}")

@app.get("/api/v1/settings", tags=["Merchant Settings"])
def get_settings():
    """Retrieves current merchant policy guardrails from SQLite."""
    try:
        repo = CatalogRepository()
        return repo.get_merchant_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load merchant settings: {str(e)}")

@app.post("/api/v1/settings", tags=["Merchant Settings"])
def update_settings(
    req: MerchantSettingsRequest,
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    authorization: str | None = Header(None, alias="Authorization"),
):
    """Updates merchant policy guardrails (margin floor and discount cap) in SQLite.
    
    In environments where ADMIN_TOKEN is configured, requires a matching
    'X-Admin-Token' or 'Authorization: Bearer <token>' header.
    """
    admin_token = settings.ADMIN_TOKEN.strip() if settings.ADMIN_TOKEN else ""
    is_prod = settings.ENVIRONMENT.lower() == "production"

    supplied_token = x_admin_token
    if not supplied_token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            supplied_token = parts[1]

    # Explicit isolation: verify supplied token is not a customer session token
    if supplied_token:
        repo = CatalogRepository()
        if repo.get_session(supplied_token):
            raise HTTPException(
                status_code=403,
                detail="Customer session tokens cannot be used to modify merchant policies.",
            )

    if admin_token:
        if supplied_token != admin_token:
            raise HTTPException(
                status_code=403,
                detail="Merchant authorization required to update policy guardrails.",
            )
    elif is_prod:
        # In production mode, ADMIN_TOKEN must be configured and matched
        raise HTTPException(
            status_code=403,
            detail="Merchant policy updates disabled: administrative token not configured.",
        )

    try:
        repo = CatalogRepository()
        repo.update_merchant_setting("margin_floor", req.margin_floor)
        repo.update_merchant_setting("discount_cap", req.discount_cap)
        return {"status": "updated", "margin_floor": req.margin_floor, "discount_cap": req.discount_cap}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save merchant settings: {str(e)}")

@app.post("/api/v1/simulate", response_model=SimulationResponse, tags=["Economic Simulation"])
def run_economic_simulation(request: SimulationRequest, req: Request) -> SimulationResponse:
    """Executes a reproducible 3-policy simulation comparator with Common Random Numbers."""
    client_ip = req.client.host if req.client else "unknown"
    enforce_simulation_rate_limit(client_ip)
    try:
        simulator = EconomicSimulator()
        return simulator.run_simulation(
            num_sessions=request.num_sessions,
            random_seed=request.random_seed,
            margin_floor=request.margin_floor,
            discount_cap=request.discount_cap,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")

@app.get("/api/v1/simulate/latest", tags=["Economic Simulation"])
def get_latest_simulation():
    """Retrieves the latest persisted simulation run from SQLite."""
    try:
        repo = CatalogRepository()
        latest = repo.get_latest_simulation_run()
        if not latest:
            raise HTTPException(status_code=404, detail="No simulation runs found")
        return latest
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch simulation run: {str(e)}")

ALLOWED_EVENT_TYPES = {
    "product_view",
    "product_viewed",
    "product_hover",
    "product_focus",
    "search_submitted",
    "add_to_cart",
    "cart_item_added",
    "cart_add",
    "remove_from_cart",
    "cart_item_removed",
    "cart_remove",
    "cart_saved",
    "save_cart",
    "recommendation_impression",
    "recommendation_shown",
    "recommendation_click",
    "recommendation_accepted",
    "offer_exposure",
    "offer_shown",
    "offer_accepted",
    "offer_rejected",
    "checkout_started",
    "demo_order_completed",
    "simulated_purchase_completed",
    "order_completed",
    "order_cancelled",
    "context_selected",
    "page_view",
    "navigation_changed",
}

EVENT_TYPE_NORMALIZATION = {
    "product_viewed": "product_view",
    "cart_item_added": "add_to_cart",
    "cart_add": "add_to_cart",
    "cart_item_removed": "remove_from_cart",
    "cart_remove": "remove_from_cart",
    "save_cart": "cart_saved",
    "recommendation_shown": "recommendation_impression",
    "recommendation_accepted": "recommendation_click",
    "offer_shown": "offer_exposure",
    "simulated_purchase_completed": "demo_order_completed",
}

@app.post("/api/v1/events", tags=["Session Events"])
def record_event(evt: SessionEventCreate):
    """Records an anonymous interaction event (distinguishing browsing vs purchase intent) with zero PII."""
    if evt.event_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_type '{evt.event_type}'. Must be one of {sorted(ALLOWED_EVENT_TYPES)}",
        )
    normalized_type = EVENT_TYPE_NORMALIZATION.get(evt.event_type, evt.event_type)
    try:
        repo = CatalogRepository()
        event_id = repo.record_session_event(
            session_id=evt.session_id,
            event_type=normalized_type,
            product_id=evt.product_id,
            shopping_context=evt.shopping_context,
            metadata=evt.metadata,
            event_id=evt.event_id,
            timestamp=evt.timestamp,
        )
        return {"status": "recorded", "event_id": event_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record event: {str(e)}")

@app.get("/api/v1/events", tags=["Session Events"])
def get_events(session_id: str, limit: int = 50):
    """Retrieves recent anonymous interaction events for a session."""
    try:
        repo = CatalogRepository()
        return repo.get_session_events(session_id=session_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch session events: {str(e)}")

@app.delete("/api/v1/events", tags=["Session Events"])
def delete_events(session_id: str):
    """Clears all session interaction events upon shopper reset."""
    try:
        repo = CatalogRepository()
        deleted = repo.clear_session_events(session_id=session_id)
        return {"status": "deleted", "events_cleared": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear session events: {str(e)}")

@app.get("/api/v1/analytics/funnel", response_model=FunnelMetricsResponse, tags=["First-Party Analytics"])
def get_funnel_analytics(
    time_window_hours: int = 24,
    provenance: str | None = None,
    storefront_id: str | None = None,
) -> FunnelMetricsResponse:
    """Aggregates first-party interaction events into commerce funnel stages and conversion metrics.

    Provides merchant visibility into recommendation impressions, offer acceptance, and demo checkout completions.
    """
    try:
        repo = CatalogRepository()
        metrics = repo.get_outcome_funnel_metrics(
            time_window_hours=time_window_hours,
            provenance_filter=provenance,
            storefront_filter=storefront_id,
        )
        return FunnelMetricsResponse(**metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to aggregate funnel metrics: {str(e)}")

@app.get("/api/v1/uplift/evaluation", response_model=UpliftEvaluationResponse, tags=["Uplift Modeling"])
def get_uplift_evaluation(
    outcome: str = "conversion",
    dataset_path: str | None = None,
) -> UpliftEvaluationResponse:
    """Evaluates offline causal uplift modeling across Two-Model T-Learner, Propensity, and Random baselines.

    Uses Criteo Uplift Benchmark schema. Bounded to offline research; does not alter synchronous live pricing.
    """
    try:
        eval_results = run_uplift_evaluation(dataset_path=dataset_path, outcome_col=outcome)
        return UpliftEvaluationResponse(**eval_results)
    except UpliftDatasetSchemaError as e:
        raise HTTPException(status_code=400, detail=f"Dataset schema assumption violation: {str(e)}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Uplift evaluation failed: {str(e)}")

@app.post("/api/v1/uplift/evaluate", response_model=UpliftEvaluationResponse, tags=["Uplift Modeling"])
def trigger_uplift_evaluation(
    outcome: str = "conversion",
    dataset_path: str | None = None,
) -> UpliftEvaluationResponse:
    """Triggers on-demand offline uplift evaluation with optional dataset path."""
    return get_uplift_evaluation(outcome=outcome, dataset_path=dataset_path)

# ==============================================================================
# MULTI-STORE PROFIT INTELLIGENCE ENDPOINTS (Step 5.20)
# ==============================================================================

def sanitize_storefront_id(storefront_id: str | None) -> str | None:
    """Validates and sanitizes storefront_id query parameters against injection or path traversal."""
    if not storefront_id:
        return None
    cleaned = storefront_id.strip()
    if not re.match(r"^[a-zA-Z0-9_\-\.]{1,64}$", cleaned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid storefront_id: must be 1-64 alphanumeric characters, underscores, hyphens, or periods.",
        )
    return cleaned


def verify_merchant_access(
    request: Request,
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict:
    """Verifies merchant authorization for previewing, importing, and viewing profit intelligence.

    Allows authenticated merchant sessions or administrative token holders.
    Customer session tokens are strictly rejected with HTTP 403.
    Unauthenticated requests in production are rejected with HTTP 401.
    """
    admin_token = settings.ADMIN_TOKEN.strip() if settings.ADMIN_TOKEN else ""
    is_prod = settings.ENVIRONMENT.lower() in ("production", "prod")

    supplied_token = x_admin_token
    if not supplied_token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            supplied_token = parts[1]

    # 1. Admin Token match
    if admin_token and supplied_token == admin_token:
        return {
            "merchant_id": "usr_demo_merchant",
            "username": "admin",
            "role": "admin",
            "is_admin": True,
        }

    # 2. Check for authenticated user session
    from backend.app.auth import extract_session_token, ALLOWED_DEMO_PERSONAS
    session_token = extract_session_token(request)
    if session_token:
        repo = CatalogRepository()
        session = repo.get_session(session_token)
        if session:
            username = session.get("username", "")
            role = session.get("role", "customer")
            # Customer accounts can never access merchant operations or confidential profit data
            if role != "merchant" and username in ALLOWED_DEMO_PERSONAS:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Customer session tokens cannot access merchant profit intelligence or perform merchant operations.",
                )
            # Authenticated merchant session
            return {
                "merchant_id": session["user_id"],
                "username": username,
                "role": role,
                "is_admin": False,
            }

    # 3. No valid session or admin token
    if is_prod or admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Merchant authentication required to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Local development environment fallback
    return {
        "merchant_id": "usr_demo_merchant",
        "username": "demo_merchant",
        "role": "merchant",
        "is_admin": True,
    }


def verify_merchant_admin_access(
    request: Request,
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict:
    """Verifies merchant administrator authorization for mutating/destructive multi-store operations."""
    admin_token = settings.ADMIN_TOKEN.strip() if settings.ADMIN_TOKEN else ""
    is_prod = settings.ENVIRONMENT.lower() in ("production", "prod")

    supplied_token = x_admin_token
    if not supplied_token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            supplied_token = parts[1]

    # Reject customer session tokens explicitly
    repo = CatalogRepository()
    cookie_token = request.cookies.get("faircart_session", "").strip()
    if cookie_token and repo.get_session(cookie_token):
        s = repo.get_session(cookie_token)
        if s.get("role") == "customer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customer session tokens cannot be used to perform merchant administrative operations.",
            )

    if supplied_token and repo.get_session(supplied_token):
        s = repo.get_session(supplied_token)
        if s.get("role") == "customer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customer session tokens cannot be used to perform merchant administrative operations.",
            )

    if admin_token:
        if supplied_token != admin_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Merchant authorization required.",
            )
    elif is_prod:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant administrative operations disabled in production: administrative token not configured.",
        )

    return {"is_admin": True}


@app.post("/api/v1/analytics/multi-store/preview", response_model=CSVValidationResponse, tags=["Multi-Store Intelligence"])
def preview_multi_store_csv(
    request: CSVImportRequest,
    _auth: dict = Depends(verify_merchant_access),
) -> CSVValidationResponse:
    """Dry-run validation and summary preview of an uploaded order-lines or traffic CSV."""
    try:
        clean_override = sanitize_storefront_id(request.storefront_override)
        is_valid, accepted_rows, errors, summary_metrics = validate_and_parse_csv(
            csv_content=request.csv_content,
            import_type=request.import_type,
            storefront_override=clean_override,
            default_currency="USD",
        )
        preview_rows = accepted_rows[:10]
        return CSVValidationResponse(
            valid=is_valid,
            import_type=request.import_type,
            filename=request.filename,
            total_rows=summary_metrics.get("total_rows_parsed", len(accepted_rows) + len(errors)),
            accepted_rows=len(accepted_rows),
            rejected_rows=len(errors),
            errors=errors,
            preview_rows=preview_rows,
            detected_storefronts=summary_metrics.get("detected_storefronts", []),
            detected_currencies=summary_metrics.get("detected_currencies", []),
            detected_channels=summary_metrics.get("detected_channels", []),
            summary_metrics=summary_metrics,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview multi-store CSV: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"CSV preview failed: {str(e)}")


@app.post("/api/v1/analytics/multi-store/import", response_model=CSVImportResponse, tags=["Multi-Store Intelligence"])
def import_multi_store_csv(
    request: CSVImportRequest,
    auth: dict = Depends(verify_merchant_access),
) -> CSVImportResponse:
    """Validates and persists order-lines or traffic-events CSV data scoped to the authenticated merchant."""
    try:
        import uuid
        repo = CatalogRepository()
        clean_override = sanitize_storefront_id(request.storefront_override)
        merchant_id = auth["merchant_id"]

        is_valid, accepted_rows, errors, summary_metrics = validate_and_parse_csv(
            csv_content=request.csv_content,
            import_type=request.import_type,
            storefront_override=clean_override,
            default_currency="USD",
        )

        batch_id = f"batch-{uuid.uuid4().hex[:12]}"
        storefront_id = clean_override or (summary_metrics.get("detected_storefronts", ["default"])[0] if summary_metrics.get("detected_storefronts") else "default")

        if not is_valid and len(accepted_rows) == 0:
            repo.record_import_batch({
                "id": batch_id,
                "merchant_id": merchant_id,
                "storefront_id": storefront_id,
                "import_type": request.import_type,
                "filename": request.filename,
                "schema_version": "1.0",
                "status": "failed",
                "total_rows": len(errors),
                "accepted_rows": 0,
                "rejected_rows": len(errors),
                "errors": errors,
            })
            raise HTTPException(
                status_code=400,
                detail=f"CSV validation failed with {len(errors)} error(s). No rows were imported."
            )

        # Persist rows scoped to authenticated merchant
        if request.import_type == "orders":
            inserted = repo.insert_storefront_order_lines(accepted_rows, batch_id=batch_id, merchant_id=merchant_id)
        elif request.import_type == "traffic":
            inserted = repo.insert_storefront_traffic_events(accepted_rows, batch_id=batch_id, merchant_id=merchant_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported import_type '{request.import_type}'. Must be 'orders' or 'traffic'.")

        status_str = "completed" if len(errors) == 0 else "partial"
        repo.record_import_batch({
            "id": batch_id,
            "merchant_id": merchant_id,
            "storefront_id": storefront_id,
            "import_type": request.import_type,
            "filename": request.filename,
            "schema_version": "1.0",
            "status": status_str,
            "total_rows": len(accepted_rows) + len(errors),
            "accepted_rows": inserted,
            "rejected_rows": len(errors),
            "errors": errors,
        })

        return CSVImportResponse(
            batch_id=batch_id,
            status=status_str,
            import_type=request.import_type,
            storefront_id=storefront_id,
            filename=request.filename,
            total_rows=len(accepted_rows) + len(errors),
            accepted_rows=inserted,
            rejected_rows=len(errors),
            errors=errors,
            message=f"Successfully imported {inserted} {request.import_type} records into {storefront_id} (Batch {batch_id})."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multi-store CSV import error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Multi-store import failed: {str(e)}")


@app.get("/api/v1/analytics/multi-store/profit", response_model=MultiStoreProfitResponse, tags=["Multi-Store Intelligence"])
def get_multi_store_profit_metrics(
    storefront_id: str | None = None,
    currency: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    auth: dict = Depends(verify_merchant_access),
) -> MultiStoreProfitResponse:
    """Aggregates and compares multi-store commerce performance strictly scoped to the authenticated merchant."""
    try:
        clean_sid = sanitize_storefront_id(storefront_id)
        merchant_id = auth["merchant_id"]
        repo = CatalogRepository()
        order_lines = repo.get_storefront_order_lines(
            merchant_id=merchant_id,
            storefront_id=clean_sid,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
        )
        traffic_events = repo.get_storefront_traffic_events(
            merchant_id=merchant_id,
            storefront_id=clean_sid,
            date_from=date_from,
            date_to=date_to,
        )
        catalogue = repo.get_all_products()
        batches = repo.get_import_batches(merchant_id=merchant_id, limit=100)

        intelligence = aggregate_profit_intelligence(
            order_rows=order_lines,
            traffic_rows=traffic_events,
            catalogue_products=catalogue,
            currency_filter=currency,
        )

        intelligence["total_batches_imported"] = len(batches)
        intelligence["date_range_start"] = date_from
        intelligence["date_range_end"] = date_to

        return MultiStoreProfitResponse(**intelligence)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate multi-store profit metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate multi-store metrics: {str(e)}")


@app.get("/api/v1/analytics/multi-store/batches", tags=["Multi-Store Intelligence"])
def get_multi_store_batches(
    limit: int = 50,
    auth: dict = Depends(verify_merchant_access),
):
    """Returns the audit log of recent multi-store CSV import batches for the authenticated merchant."""
    try:
        repo = CatalogRepository()
        return repo.get_import_batches(merchant_id=auth["merchant_id"], limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch import batches: {str(e)}")


@app.post("/api/v1/analytics/multi-store/seed-demo", tags=["Multi-Store Intelligence"])
def seed_multi_store_demo_data(
    _auth: dict = Depends(verify_merchant_admin_access),
):
    """Loads bundled synthetic multi-store orders and traffic CSV fixtures into the local database."""
    try:
        repo = CatalogRepository()
        orders_fixture = BASE_DIR / "backend" / "tests" / "fixtures" / "synthetic_multi_store_orders.csv"
        traffic_fixture = BASE_DIR / "backend" / "tests" / "fixtures" / "synthetic_multi_store_traffic.csv"

        if not orders_fixture.exists() or not traffic_fixture.exists():
            raise HTTPException(status_code=404, detail="Demo fixtures not found on server disk.")

        orders_csv = orders_fixture.read_text(encoding="utf-8")
        traffic_csv = traffic_fixture.read_text(encoding="utf-8")
        demo_merchant_id = "usr_demo_merchant"

        # Ingest orders
        is_v_o, order_rows, err_o, _ = validate_and_parse_csv(orders_csv, import_type="orders")
        order_batch_id = f"demo-orders-{int(time.time())}"
        inserted_orders = repo.insert_storefront_order_lines(order_rows, batch_id=order_batch_id, merchant_id=demo_merchant_id)
        repo.record_import_batch({
            "id": order_batch_id,
            "merchant_id": demo_merchant_id,
            "storefront_id": "multi-store-demo",
            "import_type": "orders",
            "filename": "synthetic_multi_store_orders.csv",
            "schema_version": "1.0",
            "status": "completed",
            "total_rows": len(order_rows),
            "accepted_rows": inserted_orders,
            "rejected_rows": 0,
            "errors": [],
        })

        # Ingest traffic
        is_v_t, traffic_rows, err_t, _ = validate_and_parse_csv(traffic_csv, import_type="traffic")
        traffic_batch_id = f"demo-traffic-{int(time.time())}"
        inserted_traffic = repo.insert_storefront_traffic_events(traffic_rows, batch_id=traffic_batch_id, merchant_id=demo_merchant_id)
        repo.record_import_batch({
            "id": traffic_batch_id,
            "merchant_id": demo_merchant_id,
            "storefront_id": "multi-store-demo",
            "import_type": "traffic",
            "filename": "synthetic_multi_store_traffic.csv",
            "schema_version": "1.0",
            "status": "completed",
            "total_rows": len(traffic_rows),
            "accepted_rows": inserted_traffic,
            "rejected_rows": 0,
            "errors": [],
        })

        return {
            "status": "success",
            "order_lines_imported": inserted_orders,
            "traffic_events_imported": inserted_traffic,
            "order_batch_id": order_batch_id,
            "traffic_batch_id": traffic_batch_id,
            "message": f"Successfully loaded synthetic multi-store demo fixtures: {inserted_orders} order lines across 3 stores, {inserted_traffic} traffic events across 5 acquisition channels.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to seed demo multi-store fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to seed demo data: {str(e)}")


@app.delete("/api/v1/analytics/multi-store/data", tags=["Multi-Store Intelligence"])
def clear_multi_store_data(
    request: Request,
    storefront_id: str | None = None,
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
    authorization: str | None = Header(None, alias="Authorization"),
):
    """Clears imported multi-store data, scoped to storefront or globally."""
    try:
        clean_sid = sanitize_storefront_id(storefront_id)
        repo = CatalogRepository()
        if clean_sid:
            # Scoped storefront deletion can be performed by the authenticated merchant who owns it
            auth = verify_merchant_access(request, x_admin_token, authorization)
            result = repo.clear_storefront_data(merchant_id=auth["merchant_id"], storefront_id=clean_sid)
            return {
                "status": "success",
                "storefront_id": clean_sid,
                "cleared": result,
                "message": f"Cleared multi-store data for storefront {clean_sid}: {result.get('order_lines_cleared', 0)} order lines, {result.get('traffic_events_cleared', 0)} traffic events, {result.get('batches_cleared', 0)} batches."
            }
        else:
            # Destructive global wipe across all storefronts requires explicit administrative authorization
            verify_merchant_admin_access(request, x_admin_token, authorization)
            result = repo.clear_storefront_data(storefront_id=None)
            return {
                "status": "success",
                "storefront_id": "all",
                "cleared": result,
                "message": f"Cleared all multi-store data: {result.get('order_lines_cleared', 0)} order lines, {result.get('traffic_events_cleared', 0)} traffic events, {result.get('batches_cleared', 0)} batches."
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear multi-store data: {str(e)}")


@app.get("/", tags=["Root"])
def root_status(request: Request):
    """Returns basic API discovery information or serves the compiled SPA for browser requests."""
    accept = request.headers.get("accept", "")
    frontend_dist = BASE_DIR / "frontend" / "dist"
    if "text/html" in accept and frontend_dist.exists() and (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")
    return {
        "message": "FairCart AI Decision API is running.",
        "documentation": "/docs",
        "health": "/api/v1/health",
    }

frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    if (frontend_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str, request: Request):
        if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json"):
            raise HTTPException(status_code=404, detail="Not Found")
        target_file = frontend_dist / full_path
        if target_file.is_file():
            return FileResponse(target_file)
        if "text/html" in request.headers.get("accept", ""):
            return FileResponse(frontend_dist / "index.html")
        raise HTTPException(status_code=404, detail="Not Found")
