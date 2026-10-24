import type { Decision, Overview } from "./types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function fetchOverview() {
  return getJson<Overview>("/api/overview");
}

export function fetchDecision(deliveryDate: string) {
  return getJson<Decision>(`/api/decision?deliveryDate=${deliveryDate}`);
}
