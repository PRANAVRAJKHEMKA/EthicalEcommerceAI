import { Product, HealthStatus } from './types.ts';

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
