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
    DecisionRequest,
    DecisionResponse,
    DemoLoginRequest,
    DemoPersonaPublic,
    ExplanationRequest,
    ExplanationResponse,
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
)
from backend.app.engine.simulator import EconomicSimulator
from backend.app.auth import (
    ALLOWED_DEMO_PERSONAS,
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

# Parse and configure production-safe CORS origins
# Note: Because allow_credentials=True is required for HttpOnly session cookies,
# production deployments must explicitly specify trusted frontend origins rather than wildcard '*'.
cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if "*" in cors_origins:
    if settings.ENVIRONMENT.lower() in ("production", "prod"):
        logger.warning(
            "CORS_ORIGINS contains wildcard '*' in production mode while allow_credentials=True. "
            "Browsers reject credentialed requests with wildcard origins per CORS security standards. "
            "Explicit trusted frontend origins should be configured."
        )
    cors_origins = ["*"]

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
        if repo.count_products() < 32:
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
    if persona_key not in ALLOWED_DEMO_PERSONAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid demo persona '{req.persona}'. Must be one of: {sorted(ALLOWED_DEMO_PERSONAS)}",
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
        return orchestrator.calculate_basket_quote(cart_entities, request.applied_discounts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Basket quote calculation failed: {str(e)}")

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
    "remove_from_cart",
    "cart_item_removed",
    "cart_saved",
    "save_cart",
    "recommendation_shown",
    "recommendation_accepted",
    "offer_shown",
    "context_selected",
    "simulated_purchase_completed",
    "order_completed",
}

EVENT_TYPE_NORMALIZATION = {
    "product_viewed": "product_view",
    "cart_item_added": "add_to_cart",
    "cart_item_removed": "remove_from_cart",
    "save_cart": "cart_saved",
    "order_completed": "simulated_purchase_completed",
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
