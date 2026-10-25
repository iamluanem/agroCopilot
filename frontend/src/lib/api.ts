import type { Assessment, CopilotResponse, CopilotStatus, TaskProposal, TaskT, Farm, FieldDetail, FieldSeries, ObsDate, Priorities, RiskSnapshot } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const d = body.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : `Erro ${res.status} ao consultar ${path}`);
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
  copilotStatus: () => get<CopilotStatus>("/api/copilot/status"),
  ask: (question: string, history: { role: string; content: string }[], fieldId?: number | null) =>
    get<CopilotResponse>("/api/copilot/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history, field_id: fieldId ?? null }),
    }),
  createTask: (t: TaskProposal, source: string) =>
    get<TaskT>("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...t, source }),
    }),
  fieldsUrl: (id: number) => `${API_URL}/api/farms/${id}/fields.geojson`,
  cellsUrl: (id: number) => `${API_URL}/api/farms/${id}/cells.geojson`,
};
