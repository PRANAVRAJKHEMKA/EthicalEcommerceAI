from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.db.repository import CatalogRepository
from backend.app.engine import DecisionOrchestrator
from backend.app.engine.explanation import GeminiExplanationService
from backend.app.engine.associations import get_association_engine
from backend.app.models.schemas import (
    BasketQuote,
    DecisionRequest,
    DecisionResponse,
    ExplanationRequest,
    ExplanationResponse,
    HealthResponse,
    MerchantSettingsRequest,
    Product,
    QuoteRequest,
    SessionEventCreate,
    SimulationRequest,
    SimulationResponse,
)
from backend.app.engine.simulator import EconomicSimulator

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Explainable, margin-preserving e-commerce recommendation and incentive optimization engine.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema on startup
@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/api/v1/health", response_model=HealthResponse, tags=["System Health"])
def get_health() -> HealthResponse:
    """Operational health check endpoint verifying database connectivity and catalog item count."""
    repo = CatalogRepository()
    count = repo.count_products()
    
    return HealthResponse(
        status="healthy",
        catalog_items_loaded=count,
        database="sqlite",
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
def create_decision(request: DecisionRequest) -> DecisionResponse:
    """Evaluates the active cart context to produce ranked complementary recommendations (3-5 items)
    and margin-preserving incentive optimization. Synchronous and deterministic (< 25ms).
    """
    try:
        orchestrator = DecisionOrchestrator()
        return orchestrator.process_decision(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision pipeline failed: {str(e)}")

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
def update_settings(req: MerchantSettingsRequest):
    """Updates merchant policy guardrails (margin floor and discount cap) in SQLite."""
    try:
        repo = CatalogRepository()
        repo.update_merchant_setting("margin_floor", req.margin_floor)
        repo.update_merchant_setting("discount_cap", req.discount_cap)
        return {"status": "updated", "margin_floor": req.margin_floor, "discount_cap": req.discount_cap}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save merchant settings: {str(e)}")

@app.post("/api/v1/simulate", response_model=SimulationResponse, tags=["Economic Simulation"])
def run_economic_simulation(request: SimulationRequest) -> SimulationResponse:
    """Executes a reproducible 3-policy simulation comparator with Common Random Numbers."""
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
def root_status():
    return {
        "message": "FairCart AI Decision API is running.",
        "documentation": "/docs",
        "health": "/api/v1/health",
    }
