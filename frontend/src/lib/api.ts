import type { Farm, FieldSeries, ObsDate, RiskSnapshot } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Erro ${res.status} ao consultar ${path}`);
  }
  return res.json();
}

export const api = {
  farms: () => get<{ id: number; name: string }[]>("/api/farms"),
  farm: (id: number) => get<Farm>(`/api/farms/${id}`),
  dates: (id: number, seasonId?: number) =>
    get<ObsDate[]>(`/api/farms/${id}/dates${seasonId ? `?season_id=${seasonId}` : ""}`),
  risk: (id: number, on: string) => get<RiskSnapshot>(`/api/farms/${id}/risk?on=${on}`),
  fieldSeries: (fieldId: number) => get<FieldSeries>(`/api/fields/${fieldId}/series`),
  fieldsUrl: (id: number) => `${API_URL}/api/farms/${id}/fields.geojson`,
  cellsUrl: (id: number) => `${API_URL}/api/farms/${id}/cells.geojson`,
};
