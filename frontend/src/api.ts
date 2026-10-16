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
  UserProfile,
  LoginRequest,
  LoginResponse,
  OrderDetail,
  CreateOrderRequest,
  DemoPersona,
} from './types.ts';

// Configurable API base url supporting environment override or relative URL for unified deployment
const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' &&
  window.location.hostname !== 'localhost' &&
  window.location.hostname !== '127.0.0.1'
    ? ''
    : 'http://127.0.0.1:8000');

export function getStoredSessionToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('faircart_session_token');
}

export function setStoredSessionToken(token: string | null): void {
  if (typeof window === 'undefined') return;
  if (token) {
    localStorage.setItem('faircart_session_token', token);
  } else {
    localStorage.removeItem('faircart_session_token');
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = getStoredSessionToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

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

export async function fetchDecision(req: DecisionRequest, signal?: AbortSignal): Promise<DecisionResponse> {
  const res = await fetch(`${API_BASE}/api/v1/decision`, {
    method: 'POST',
    headers: getAuthHeaders(),
    credentials: 'include',
    body: JSON.stringify(req),
    signal,
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

export const DEFAULT_DEMO_POLICY: MerchantSettings = {
  margin_floor: 0.20,
  discount_cap: 0.20,
};

export function getSessionPolicy(): MerchantSettings {
  if (typeof window === 'undefined') return { ...DEFAULT_DEMO_POLICY };
  try {
    const raw = sessionStorage.getItem('faircart_demo_policy');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (
        typeof parsed.margin_floor === 'number' &&
        isFinite(parsed.margin_floor) &&
        typeof parsed.discount_cap === 'number' &&
        isFinite(parsed.discount_cap)
      ) {
        return {
          margin_floor: Math.max(0.0, Math.min(1.0, parsed.margin_floor)),
          discount_cap: Math.max(0.0, Math.min(0.50, parsed.discount_cap)),
        };
      }
    }
  } catch {
    // Fall back to default on parse failure
  }
  return { ...DEFAULT_DEMO_POLICY };
}

export function saveSessionPolicy(policy: MerchantSettings): void {
  if (typeof window === 'undefined') return;
  try {
    const cleanPolicy: MerchantSettings = {
      margin_floor: Math.max(0.0, Math.min(1.0, policy.margin_floor)),
      discount_cap: Math.max(0.0, Math.min(0.50, policy.discount_cap)),
    };
    sessionStorage.setItem('faircart_demo_policy', JSON.stringify(cleanPolicy));
  } catch (err) {
    console.warn('Failed to save session policy to sessionStorage:', err);
  }
}

export function resetSessionPolicy(): MerchantSettings {
  if (typeof window !== 'undefined') {
    try {
      sessionStorage.removeItem('faircart_demo_policy');
    } catch {}
  }
  return { ...DEFAULT_DEMO_POLICY };
}

// Client-side recent event deduplication tracker (prevents rapid duplicate network traffic)
const recentEventSignatures = new Map<string, number>();

export async function recordSessionEvent(
  evt: SessionEventCreate
): Promise<{ status: string; event_id: string }> {
  const now = Date.now();
  const sigKey = evt.event_id || `${evt.session_id}:${evt.event_type}:${evt.product_id || ''}`;
  const lastTime = recentEventSignatures.get(sigKey);

  // Deduplicate identical signals triggered within 1200ms
  if (lastTime && now - lastTime < 1200) {
    return { status: 'deduplicated', event_id: evt.event_id || '' };
  }
  recentEventSignatures.set(sigKey, now);

  // Prune expired signatures to prevent unbounded memory growth
  if (recentEventSignatures.size > 200) {
    for (const [key, ts] of recentEventSignatures.entries()) {
      if (now - ts > 10000) {
        recentEventSignatures.delete(key);
      }
    }
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(evt),
    });
    if (!res.ok) {
      console.warn(`Analytics event notice: status ${res.status}`);
      return { status: 'failed_server', event_id: evt.event_id || '' };
    }
    return res.json();
  } catch (err) {
    console.warn('Asynchronous event recording notice:', err);
    return { status: 'deferred_local', event_id: evt.event_id || '' };
  }
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

// -------------------------------------------------------------
// Authentication & Order History (Milestone 6B)
// -------------------------------------------------------------

export async function fetchDemoPersonas(): Promise<DemoPersona[]> {
  const res = await fetch(`${API_BASE}/api/v1/auth/demo-personas`);
  if (!res.ok) {
    throw new Error(`Failed to fetch demo personas (${res.status})`);
  }
  return res.json();
}

export async function demoLoginUser(persona: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/demo-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ persona }),
    credentials: 'include',
  });
  if (!res.ok) {
    let msg = `Demo login failed (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) msg = err.detail;
    } catch {
      // fallback
    }
    throw new Error(msg);
  }
  const data: LoginResponse = await res.json();
  setStoredSessionToken(data.session_token);
  return data;
}

export async function loginUser(credentials: LoginRequest): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
    credentials: 'include',
  });
  if (!res.ok) {
    let msg = `Login failed (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) msg = err.detail;
    } catch {
      // fallback
    }
    throw new Error(msg);
  }
  const data: LoginResponse = await res.json();
  setStoredSessionToken(data.session_token);
  return data;
}

export async function fetchCurrentUser(): Promise<UserProfile | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: getAuthHeaders(),
      credentials: 'include',
    });
    if (!res.ok) {
      if (res.status === 401) {
        setStoredSessionToken(null);
      }
      return null;
    }
    return res.json();
  } catch {
    return null;
  }
}

export async function logoutUser(): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: 'POST',
      headers: getAuthHeaders(),
      credentials: 'include',
    });
  } catch {
    // ignore network errors on logout
  } finally {
    setStoredSessionToken(null);
  }
}

export async function fetchUserOrders(): Promise<OrderDetail[]> {
  const res = await fetch(`${API_BASE}/api/v1/orders`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch orders (${res.status})`);
  }
  return res.json();
}

export async function fetchOrderById(orderId: string): Promise<OrderDetail> {
  const res = await fetch(`${API_BASE}/api/v1/orders/${encodeURIComponent(orderId)}`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch order (${res.status})`);
  }
  return res.json();
}

export async function createSimulatedOrder(req: CreateOrderRequest): Promise<OrderDetail> {
  const res = await fetch(`${API_BASE}/api/v1/orders`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(req),
    credentials: 'include',
  });
  if (!res.ok) {
    let msg = `Order submission failed (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) msg = err.detail;
    } catch {
      // fallback
    }
    throw new Error(msg);
  }
  return res.json();
}


