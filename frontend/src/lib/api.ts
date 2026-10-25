import type { Assessment, Farm, FieldDetail, FieldSeries, ObsDate, Priorities, RiskSnapshot } from "./types";

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
  priorities: (id: number, on?: string) => get<Priorities>(`/api/farms/${id}/priorities${on ? `?on=${on}` : ""}`),
  assessment: (fieldId: number, on: string) => get<Assessment>(`/api/fields/${fieldId}/assessment?on=${on}`),
  field: (fieldId: number) => get<FieldDetail>(`/api/fields/${fieldId}`),
  weather: (id: number, start: string, end: string) =>
    get<{ date: string; rain_mm: number; tmax_c: number; tmin_c: number }[]>(`/api/farms/${id}/weather?start=${start}&end=${end}`),
  tasksSummary: (id: number) => get<{ open: number; by_status: Record<string, number> }>(`/api/farms/${id}/tasks/summary`),
  fieldsUrl: (id: number) => `${API_URL}/api/farms/${id}/fields.geojson`,
  cellsUrl: (id: number) => `${API_URL}/api/farms/${id}/cells.geojson`,
};
