"""FairCart AI Engine Modules:
- recommender: Engine A (Content-based candidate ranking & affinity scoring)
- optimizer: Engine B (Margin-constrained economic utility optimization)
- orchestrator: Engine C (Decision pipeline orchestration)
"""

from backend.app.engine.recommender import RecommenderEngine, RecommendationCandidate
from backend.app.engine.optimizer import EconomicOptimizer, OptimizationResult
from backend.app.engine.orchestrator import DecisionOrchestrator

__all__ = [
    "RecommenderEngine",
    "RecommendationCandidate",
    "EconomicOptimizer",
    "OptimizationResult",
    "DecisionOrchestrator",
]
