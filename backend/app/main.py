from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.db.repository import CatalogRepository
from backend.app.engine import DecisionOrchestrator
from backend.app.models.schemas import (
    DecisionRequest,
    DecisionResponse,
    HealthResponse,
    Product,
)
from fastapi import HTTPException

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
    """Retrieves all 20 catalog products with verified reference prices, COGS, and stock."""
    try:
        repo = CatalogRepository()
        products = repo.get_all_products()
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve catalog from database: {str(e)}")

@app.post("/api/v1/decision", response_model=DecisionResponse, tags=["Decision Engine"])
def create_decision(request: DecisionRequest) -> DecisionResponse:
    """Evaluates the active cart context to produce an explainable complementary recommendation
    and margin-preserving incentive optimization. Synchronous and deterministic (< 25ms).
    """
    try:
        orchestrator = DecisionOrchestrator()
        return orchestrator.process_decision(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision pipeline failed: {str(e)}")

@app.get("/", tags=["Root"])
def root_status():
    return {
        "message": "FairCart AI Decision API is running.",
        "documentation": "/docs",
        "health": "/api/v1/health",
    }
