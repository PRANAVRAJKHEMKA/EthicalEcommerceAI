"""Gemini Natural Language Explanation Service

Provides server-side natural language explanation for complementary recommendations.
Operates asynchronously and independently of the sub-25ms synchronous decision pipeline.

Architectural guarantees:
1. Strict separation of concerns: Gemini NEVER determines or modifies prices, discounts,
   margins, inventory, or product rankings.
2. Verified ground-truth prompt: Only validated product metadata, categories, subcategories,
   and tags from SQLite are sent to Gemini.
3. Sub-4s SLA with instant deterministic fallback: If GEMINI_API_KEY is not configured,
   the request times out, or quota is exceeded, the service falls back immediately to
   the attribute-grounded factual explanation without interrupting the customer experience.
4. Response deduplication & in-memory caching to minimize external API consumption.
"""

import json
import logging
import time
from typing import Any
import httpx

from backend.app.config import settings
from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.recommender import build_factual_recommendation_reason
from backend.app.models.schemas import (
    ExplanationRequest,
    ExplanationResponse,
    ItemExplanation,
)

logger = logging.getLogger("faircart.explanation")

class GeminiExplanationService:
    """Server-side explanation engine leveraging Google Gemini with deterministic fallback."""

    def __init__(
        self,
        api_key: str | None = None,
        repository: CatalogRepository | None = None,
        model_name: str = "gemini-2.5-flash",
        timeout_seconds: float = 3.5,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.repository = repository or CatalogRepository()
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self._cache: dict[tuple, dict[str, ItemExplanation]] = {}

    def _build_cache_key(self, request: ExplanationRequest) -> tuple:
        return (
            tuple(sorted(request.cart_product_ids)),
            tuple(sorted(request.candidate_product_ids)),
            request.shopping_context.strip().lower(),
        )

    def _generate_deterministic_explanations(
        self,
        candidates: list[ProductEntity],
        cart_items: list[ProductEntity],
        shopping_context: str,
    ) -> dict[str, ItemExplanation]:
        """Generates attribute-grounded fallback explanations without external API calls."""
        results: dict[str, ItemExplanation] = {}
        parent = cart_items[0] if cart_items else None

        for cand in candidates:
            reason = build_factual_recommendation_reason(
                candidate=cand,
                parent=parent,
                shopping_context=shopping_context,
            )
            signals = [
                f"Category: {cand.category}",
                f"Subcategory: {cand.subcategory}",
            ]
            if cand.tags:
                signals.append(f"Tags: {', '.join(cand.tags[:3])}")
            if shopping_context != "all":
                signals.append(f"Intent Context: {shopping_context.capitalize()}")

            results[cand.id] = ItemExplanation(
                product_id=cand.id,
                explanation=reason,
                factual_signals=signals,
                source="deterministic_fallback",
            )

        return results

    def _build_prompt(
        self,
        candidates: list[ProductEntity],
        cart_items: list[ProductEntity],
        shopping_context: str,
    ) -> str:
        """Constructs an ethical prompt grounded strictly in catalogue attributes."""
        cart_summary = [
            f"- {p.name} (Category: {p.category}, Subcategory: {p.subcategory}, Tags: {', '.join(p.tags)})"
            for p in cart_items
        ]
        cand_summary = [
            f"- ID: {c.id} | Name: {c.name} | Category: {c.category} | Subcategory: {c.subcategory} | Tags: {', '.join(c.tags)} | Description: {c.description}"
            for c in candidates
        ]

        return f"""You are the ethical AI copywriter for FairCart AI, a transparent e-commerce platform.
Your task is to write a concise, natural, factual 1-2 sentence explanation for why each complementary product is recommended.

CUSTOMER CART:
{chr(10).join(cart_summary) if cart_summary else "No current cart items."}

CUSTOMER SELECTED SHOPPING INTENT:
{shopping_context.capitalize() if shopping_context != "all" else "General Workstation"}

CANDIDATE PRODUCTS TO EXPLAIN:
{chr(10).join(cand_summary)}

STRICT ETHICAL GUIDELINES:
1. Explain concrete, factual attributes (e.g. typing ergonomics, USB-C connectivity, high-DPI gaming tracking, acoustic decoupling).
2. NEVER invent fake compatibility, health claims, or false scarcity.
3. NEVER mention prices, discounts, or financial calculations (these are handled by an independent economic engine).
4. Keep each explanation strictly between 1 and 2 sentences, professional, helpful, and natural.
5. Return a strict JSON object mapping each candidate product ID to its explanation string.

Example JSON output format:
{{
  "explanations": {{
    "item-002": "The memory foam wrist rest pairs with mechanical keyboards by maintaining neutral wrist elevation to relieve typing fatigue during extended sessions."
  }}
}}
"""

    async def explain(self, request: ExplanationRequest) -> ExplanationResponse:
        """Generates natural language explanations for recommendation candidates."""
        start_time = time.perf_counter()

        if not request.candidate_product_ids:
            latency = round((time.perf_counter() - start_time) * 1000.0, 2)
            return ExplanationResponse(
                session_id=request.session_id,
                shopping_context=request.shopping_context,
                explanations={},
                ai_generated=False,
                fallback_applied=False,
                execution_latency_ms=latency,
            )

        # 1. Fetch ground-truth product facts from SQLite
        candidate_entities = self.repository.get_entities_by_ids(request.candidate_product_ids)
        cart_entities = self.repository.get_entities_by_ids(request.cart_product_ids)

        # Generate deterministic baseline fallback
        fallback_explanations = self._generate_deterministic_explanations(
            candidates=candidate_entities,
            cart_items=cart_entities,
            shopping_context=request.shopping_context,
        )

        # 2. Check cache
        cache_key = self._build_cache_key(request)
        if cache_key in self._cache:
            latency = round((time.perf_counter() - start_time) * 1000.0, 2)
            return ExplanationResponse(
                session_id=request.session_id,
                shopping_context=request.shopping_context,
                explanations=self._cache[cache_key],
                ai_generated=True,
                fallback_applied=False,
                execution_latency_ms=latency,
            )

        # 3. Check if Gemini API key is configured
        if not self.api_key or not self.api_key.strip():
            latency = round((time.perf_counter() - start_time) * 1000.0, 2)
            return ExplanationResponse(
                session_id=request.session_id,
                shopping_context=request.shopping_context,
                explanations=fallback_explanations,
                ai_generated=False,
                fallback_applied=True,
                fallback_reason="Gemini API key is not configured. Displaying deterministic factual explanation.",
                execution_latency_ms=latency,
            )

        # 4. Invoke Gemini REST API
        prompt = self._build_prompt(
            candidates=candidate_entities,
            cart_items=cart_entities,
            shopping_context=request.shopping_context,
        )

        api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
            f"?key={self.api_key.strip()}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
                "maxOutputTokens": 800,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(api_url, json=payload)
                response.raise_for_status()
                data = response.json()

            # Parse model output
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "{}")
            )
            parsed = json.loads(text)
            ai_map = parsed.get("explanations", {})

            # Validate that returned explanations are valid strings
            results: dict[str, ItemExplanation] = {}
            for cand in candidate_entities:
                if cand.id in ai_map and isinstance(ai_map[cand.id], str) and len(ai_map[cand.id].strip()) > 10:
                    results[cand.id] = ItemExplanation(
                        product_id=cand.id,
                        explanation=ai_map[cand.id].strip(),
                        factual_signals=[
                            f"Category: {cand.category}",
                            f"Subcategory: {cand.subcategory}",
                            "Verified by Gemini 2.5 Flash",
                        ],
                        source="gemini",
                    )
                else:
                    # Partial fallback if an individual item is missing in output
                    results[cand.id] = fallback_explanations[cand.id]

            # Cache successful response
            self._cache[cache_key] = results
            latency = round((time.perf_counter() - start_time) * 1000.0, 2)

            return ExplanationResponse(
                session_id=request.session_id,
                shopping_context=request.shopping_context,
                explanations=results,
                ai_generated=True,
                fallback_applied=False,
                execution_latency_ms=latency,
            )

        except Exception as e:
            logger.warning("Gemini explanation call failed, using deterministic fallback: %s", str(e))
            latency = round((time.perf_counter() - start_time) * 1000.0, 2)
            return ExplanationResponse(
                session_id=request.session_id,
                shopping_context=request.shopping_context,
                explanations=fallback_explanations,
                ai_generated=False,
                fallback_applied=True,
                fallback_reason=f"Gemini call unavailable ({type(e).__name__}). Using deterministic fallback.",
                execution_latency_ms=latency,
            )
