export type Level = "green" | "yellow" | "red" | "no_data";
export type Confidence = "low" | "moderate" | "high";

export interface Season {
  id: number;
  name: string;
  sowing_date: string;
  harvest_date: string | null;
  is_current: boolean;
  expected_yield_bags_ha: number | null;
  realized_yield_bags_ha: number | null;
}

export interface Farm {
  id: number;
  name: string;
  municipality: string;
  state: string;
  crop: string;
  area_ha: number;
  reference_date: string;
  soil_notes: string | null;
  is_synthetic: boolean;
  bbox: [number, number, number, number];
  seasons: Season[];
  fields: { id: number; code: string; name: string; area_ha: number }[];
}

export interface ObsDate {
  date: string;
  das: number;
  cloud_pct: number;
  simulated?: boolean;
  season_id: number;
}

export interface FieldRisk {
  field_id: number;
  code: string;
  name: string;
  area_ha: number;
  level: Exclude<Level, "no_data">;
  area_by_level: Record<Level, number>;
  ndvi_mean: number | null;
  ndvi_baseline: number | null;
  max_score: number | null;
  cloud_pct: number;
}

export interface RiskSnapshot {
  date: string;
  das: number;
  season_id: number;
  season_name: string;
  is_synthetic: boolean;
  simulated?: boolean;
  source: string;
  method: string;
  thresholds: { yellow: number; red: number };
  levels: Level[];
  confidence_labels: Confidence[];
  cells: {
    id: number[];
    level: number[];
    score: (number | null)[];
    ndvi: (number | null)[];
    ndre: (number | null)[];
    baseline: (number | null)[];
    confidence: number[];
    area: number[];
  };
  fields: FieldRisk[];
  summary: {
    total_ha: number;
    area_by_level: Record<Level, number>;
    pct_by_level: Record<Level, number>;
    cloud_pct: number;
  };
}

export interface FieldProps {
  id: number;
  code: string;
  name: string;
  area_ha: number;
  soil_texture: string | null;
  irrigation: string;
  boundary_source: string;
  is_synthetic: boolean;
  label_point: [number, number];
}

export interface FieldSeries {
  field_id: number;
  code: string;
  name: string;
  seasons: {
    season_id: number;
    season: string;
    is_current: boolean;
    points: { date: string; das: number; ndvi: number | null; cloud_pct: number }[];
  }[];
}

export type LayerMode = "risk" | "ndvi" | "ndre" | "sentinel";
export type Basemap = "satellite" | "terrain";

export interface HypothesisT {
  rank: number;
  cause: string;
  confidence: Confidence;
  evidence: string[];
  missing: string[];
}

export interface Economics {
  affected_ha: number;
  exposure_min: number;
  exposure_max: number;
  inspection_cost: number;
  intervention_cost: number;
  gross_value_brl: number;
  formula: string;
  label: string;
  assumptions: {
    expected_yield_bags_ha: number;
    bag_price_brl: number;
    loss_min_pct: number;
    loss_max_pct: number;
    inspection_cost_brl: number;
    intervention_cost_brl_ha: number;
    watch_area_weight: number;
    critical_area_ha: number;
    watch_area_ha: number;
  };
}

export interface Assessment {
  field_id: number;
  code: string;
  name: string;
  area_ha: number;
  date: string;
  das: number;
  stage: string;
  level: Exclude<Level, "no_data">;
  red_ha: number;
  yellow_ha: number;
  ndvi_mean: number | null;
  ndvi_baseline: number | null;
  is_synthetic: boolean;
  assessment_id: number | null;
  has_zone: boolean;
  priority_score: number;
  rank?: number;
  summary?: string;
  confidence?: Confidence;
  observation?: string;
  pattern_label?: string;
  onset_das?: number | null;
  onset_date?: string | null;
  ndvi_drop?: number;
  recurrence_share?: number;
  weather?: { max_dry_days: number; dry_start: string | null; dry_end: string | null; rain_21d_mm: number; tmax_dry_mean: number | null };
  urgency?: number;
  urgency_reason?: string;
  worsening?: boolean;
  priority_formula?: string;
  next_step?: string;
  prior_verified?: { season: string; cause: string }[];
  disclaimer?: string;
  hypotheses: HypothesisT[];
  economics: Economics | null;
}

export interface Priorities {
  date: string;
  priority_formula: string;
  items: Assessment[];
  totals: { exposure_min: number; exposure_max: number; affected_ha: number; inspection_cost: number };
}

export interface MemoryEvent {
  id: number;
  date: string;
  type: "season" | "anomaly" | "inspection" | "intervention" | "outcome" | "note" | "task";
  title: string;
  summary: string;
  season: string | null;
  is_synthetic: boolean;
}

export interface FieldDetail {
  field_id: number;
  code: string;
  name: string;
  area_ha: number;
  soil_texture: string | null;
  irrigation: string;
  boundary_source: string;
  season: { id: number; name: string; sowing_date: string; expected_yield_bags_ha: number | null };
  date: string;
  assessment: Assessment;
  evolution: { date: string; das: number; cloud_pct: number; simulated?: boolean; red: number; yellow: number; no_data: number; ndvi: number | null; baseline: number | null }[];
  weather: { date: string; rain_mm: number; tmax_c: number }[];
  memory: MemoryEvent[];
  harvests: { season: string; expected: number | null; realized: number | null }[];
}

export interface TaskProposal {
  field_id: number;
  field_code: string;
  assessment_id: number | null;
  title: string;
  priority: "high" | "medium" | "low";
  assignee: string | null;
  due_date: string | null;
  instructions: string;
}

export interface CopilotAnswer {
  summary: string;
  evidence: string[];
  confidence: Confidence;
  missing_data: string[];
  next_action: string;
  sources: { type: string; label: string; ref: string | null }[];
  proposed_task: TaskProposal | null;
  warnings: string[];
}

export interface CopilotResponse {
  answer: CopilotAnswer;
  provider: string;
  tools_used: { name: string; args: Record<string, unknown> }[];
}

export interface CopilotStatus {
  provider: string;
  label: string;
  suggestions: string[];
  available: Record<string, boolean>;
}

export type TaskStatus = "pending" | "assigned" | "in_progress" | "completed" | "verified";

export interface TaskT {
  id: number;
  field_id: number;
  field_code: string;
  field_name: string;
  assessment_id: number | null;
  title: string;
  kind: string;
  status: TaskStatus;
  priority: "high" | "medium" | "low";
  assignee: string | null;
  due_date: string | null;
  instructions: string | null;
  created_at: string;
  is_synthetic: boolean;
  has_inspection: boolean;
  verified_cause: string | null;
}

export interface InspectionT {
  id: number;
  inspected_at: string;
  findings: string;
  verified_cause: string | null;
  photos: string[];
  notes: string | null;
  recorded_by: string;
}

export interface OutcomeT {
  id: number;
  intervention_id: number;
  metric: string;
  before_start: string;
  before_end: string;
  after_start: string;
  after_end: string;
  before_value: number;
  after_value: number;
  comparison_before: number | null;
  comparison_after: number | null;
  delta: number;
  delta_vs_comparison: number | null;
  method: string;
  comparison_area: string | null;
  limitations: string;
  confidence: Confidence;
  is_synthetic: boolean;
}

export interface InterventionT {
  id: number;
  field_id: number;
  inspection_id: number | null;
  recommended_action: string | null;
  approved_action: string;
  approved_by: string;
  executed_at: string;
  actual_cost: number;
  notes: string | null;
  is_synthetic: boolean;
  outcome: OutcomeT | null;
}

export interface TaskDetail extends TaskT {
  inspection: InspectionT | null;
  interventions: InterventionT[];
  assessment: { id: number; date: string; level: Level; affected_ha: number; observation: string; next_step: string; hypotheses: { cause: string; confidence: Confidence }[] } | null;
  previous_intervention: { executed_at: string; approved_action: string; actual_cost: number } | null;
  status_flow: TaskStatus[];
}

export interface OutcomeListItem extends OutcomeT {
  field_id: number;
  field_code: string;
  field_name: string;
  executed_at: string;
  approved_action: string;
  actual_cost: number;
  user_created: boolean;
}

export interface OutcomeDetail {
  outcome: OutcomeT;
  field_id: number;
  field_code: string;
  field_name: string;
  farm_id: number;
  intervention: InterventionT;
  inspection: InspectionT | null;
  task: { id: number; title: string } | null;
  zone_cells: number;
  comparison_cells: number;
  zone_cell_ids: number[];
  series: { date: string; das: number; simulated: boolean; zone: number | null; comparison: number | null }[];
  before_date: string;
  after_date: string;
  disclaimer: string;
}

export interface EconomicsCfg {
  expected_yield_bags_ha: number;
  bag_price_brl: number;
  loss_min_pct: number;
  loss_max_pct: number;
  inspection_cost_brl: number;
  intervention_cost_brl_ha: number;
}
export interface RiskCfg {
  yellow_threshold: number;
  red_threshold: number;
  history_weight: number;
}
export type ProviderChoice = "auto" | "demo" | "anthropic" | "openai";
export interface SettingsT {
  economics: EconomicsCfg;
  risk: RiskCfg;
  llm_provider: ProviderChoice;
  copilot: CopilotStatus;
}

export interface SentinelScene {
  scene_id: string;
  date: string;
  datetime: string;
  cloud_cover: number | null;
  bounds: [number, number, number, number];
  files: { ndvi: string; ndre: string };
  valid_pct: number;
  ndvi_mean: number | null;
  ndre_mean: number | null;
  source: string;
  stac_item?: string;
}
