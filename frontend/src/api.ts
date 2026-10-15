import {
  Product,
  HealthStatus,
  DecisionRequest,
  DecisionResponse,
  QuoteRequest,
  BasketQuote,
  ExplanationRequest,
  ExplanationResponse,
  MerchantSettings,
  SessionEventCreate,
  SessionEvent,
  SimulationRequest,
  SimulationResponse,
} from './types.ts';

// Configurable API base url supporting environment override or relative URL for unified deployment
const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' &&
  window.location.hostname !== 'localhost' &&
  window.location.hostname !== '127.0.0.1'
    ? ''
    : 'http://127.0.0.1:8000');

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

export async function fetchExplanation(req: ExplanationRequest): Promise<ExplanationResponse> {
  const res = await fetch(`${API_BASE}/api/v1/explanation`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Explanation request failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchMerchantSettings(): Promise<MerchantSettings> {
  const res = await fetch(`${API_BASE}/api/v1/settings`);
  if (!res.ok) {
    throw new Error(`Merchant settings request failed with status ${res.status}`);
  }
  return res.json();
}

export async function updateMerchantSettings(
  settings: MerchantSettings,
  adminToken?: string
): Promise<{ status: string; margin_floor: number; discount_cap: number }> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (adminToken) {
    headers['X-Admin-Token'] = adminToken;
  }
  const res = await fetch(`${API_BASE}/api/v1/settings`, {
    method: 'POST',
    headers,
    body: JSON.stringify(settings),
  });
  if (!res.ok) {
    if (res.status === 403) {
      throw new Error('Merchant authorization required to update policy guardrails.');
    }
    throw new Error(`Failed to update merchant settings: ${res.status}`);
  }
  return res.json();
}

export async function recordSessionEvent(
  evt: SessionEventCreate
): Promise<{ status: string; event_id: string }> {
  const res = await fetch(`${API_BASE}/api/v1/events`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(evt),
  });
  if (!res.ok) {
    throw new Error(`Record session event failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchSessionEvents(
  sessionId: string,
  limit = 50
): Promise<SessionEvent[]> {
  const res = await fetch(
    `${API_BASE}/api/v1/events?session_id=${encodeURIComponent(sessionId)}&limit=${limit}`
  );
  if (!res.ok) {
    throw new Error(`Fetch session events failed with status ${res.status}`);
  }
  return res.json();
}

export async function clearSessionEvents(
  sessionId: string
): Promise<{ status: string; events_cleared: number }> {
  const res = await fetch(
    `${API_BASE}/api/v1/events?session_id=${encodeURIComponent(sessionId)}`,
    {
      method: 'DELETE',
    }
  );
  if (!res.ok) {
    throw new Error(`Clear session events failed with status ${res.status}`);
  }
  return res.json();
}

export async function runSimulation(req: SimulationRequest): Promise<SimulationResponse> {
  const res = await fetch(`${API_BASE}/api/v1/simulate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Simulation failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchLatestSimulation(): Promise<SimulationResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/simulate/latest`);
    if (!res.ok) {
      if (res.status === 404) return null;
      throw new Error(`Fetch latest simulation failed with status ${res.status}`);
    }
    const data = await res.json();
    return data.results || data;
  } catch {
    return null;
  }
}


