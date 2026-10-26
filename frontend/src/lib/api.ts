import type { SentinelScene, SettingsT, EconomiaCfg, RiscoCfg, ProviderChoice, Assessment, CopilotResponse, CopilotStatus, InterventionT, OutcomeDetail, OutcomeListItem, TaskDetail, TaskProposal, TaskStatus, TaskT, Farm, FieldDetail, FieldSeries, ObsDate, Priorities, RiskSnapshot } from "./types";

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

const send = <T>(method: string, path: string, body?: unknown) =>
  get<T>(path, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });

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
  tasks: (status?: string) => get<TaskT[]>(`/api/tasks${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  task: (id: number) => get<TaskDetail>(`/api/tasks/${id}`),
  setStatus: (id: number, status: TaskStatus) => send<TaskDetail>("PATCH", `/api/tasks/${id}/status`, { status }),
  inspect: (id: number, body: { findings: string; verified_cause: string | null; notes: string | null; recorded_by: string; photos: string[] }) =>
    send<TaskDetail>("POST", `/api/tasks/${id}/inspection`, body),
  verify: (id: number, verified_by: string, notes?: string) => send<TaskDetail>("POST", `/api/tasks/${id}/verify`, { verified_by, notes }),
  intervene: (body: { field_id: number; inspection_id: number; recommended_action: string | null; approved_action: string; approved_by: string; executed_at: string | null; actual_cost: number; notes: string | null; receituario_confirmado: boolean }) =>
    send<InterventionT>("POST", "/api/interventions", body),
  simulate: (interventionId: number) => send<OutcomeDetail>("POST", `/api/interventions/${interventionId}/simulate`),
  outcomes: () => get<OutcomeListItem[]>("/api/outcomes"),
  outcome: (id: number) => get<OutcomeDetail>(`/api/outcomes/${id}`),
  resetDemo: () => send<{ tarefas_removidas: number }>("POST", "/api/demo/reset"),
  mediaUrl: (path: string) => `${API_URL}${path}`,
  settings: () => get<SettingsT>("/api/settings"),
  saveSettings: (b: { economia: EconomiaCfg; risco: RiscoCfg; llm_provider: ProviderChoice }) => send<SettingsT>("PUT", "/api/settings", b),
  imagery: (farmId: number) => get<SentinelScene[]>(`/api/farms/${farmId}/imagery`),
  fieldsUrl: (id: number) => `${API_URL}/api/farms/${id}/fields.geojson`,
  cellsUrl: (id: number) => `${API_URL}/api/farms/${id}/cells.geojson`,
};
