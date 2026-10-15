from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.db.repository import CatalogRepository
from backend.app.engine import DecisionOrchestrator
from backend.app.models.schemas import (
    BasketQuote,
    DecisionRequest,
    DecisionResponse,
    HealthResponse,
    MerchantSettingsRequest,
    Product,
    QuoteRequest,
)

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

@app.get("/", tags=["Root"])
def root_status():
    return {
        "message": "FairCart AI Decision API is running.",
        "documentation": "/docs",
        "health": "/api/v1/health",
    }
