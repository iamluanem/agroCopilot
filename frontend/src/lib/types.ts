export type Level = "verde" | "amarelo" | "vermelho" | "sem_dado";
export type Confidence = "baixa" | "moderada" | "alta";

export interface Season {
  id: number;
  name: string;
  sowing_date: string;
  harvest_date: string | null;
  is_current: boolean;
  expected_yield_sc_ha: number | null;
  realized_yield_sc_ha: number | null;
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
  season_id: number;
}

export interface FieldRisk {
  field_id: number;
  code: string;
  name: string;
  area_ha: number;
  level: Exclude<Level, "sem_dado">;
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

export type LayerMode = "risco" | "ndvi" | "ndre";
export type Basemap = "satelite" | "terreno";
