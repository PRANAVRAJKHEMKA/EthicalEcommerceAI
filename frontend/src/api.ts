import {
  Product,
  HealthStatus,
  DecisionRequest,
  DecisionResponse,
  QuoteRequest,
  BasketQuote,
} from './types.ts';

const API_BASE = 'http://127.0.0.1:8000';

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/api/v1/health`);
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchCatalog(): Promise<Product[]> {
  const res = await fetch(`${API_BASE}/api/v1/catalog`);
  if (!res.ok) {
    throw new Error(`Catalog fetch failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchDecision(req: DecisionRequest): Promise<DecisionResponse> {
  const res = await fetch(`${API_BASE}/api/v1/decision`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Decision engine request failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchQuote(req: QuoteRequest): Promise<BasketQuote> {
  const res = await fetch(`${API_BASE}/api/v1/quote`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Basket quote request failed with status ${res.status}`);
  }
  return res.json();
}
