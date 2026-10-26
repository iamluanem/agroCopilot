"use client";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, ChevronRight, Droplets, Info, Layers, MapPin } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { LEVEL_COLOR, LEVEL_LABEL } from "@/lib/colors";
import type { Farm, FieldProps, FieldRisk, Level, RiskSnapshot } from "@/lib/types";
import { cn, fmt, fmtDate, fmtHa, fmtPct } from "@/lib/utils";
import { Badge } from "../ui/badge";
import { DemoBadge } from "../ui/demo-badge";
import { ErrorState, Loading } from "../ui/states";
import { FieldSeriesChart } from "./field-series-chart";
import { AssessmentPanel } from "../intel/assessment-cards";
import { CreateTaskButton } from "../ops/create-task-button";

export interface CellInfo {
  id: number;
  level: Level;
  score: number | null;
  ndvi: number | null;
  ndre: number | null;
  baseline: number | null;
  confidence: string | null;
  area_ha: number;
}

interface Props {
  farm: Farm;
  risk?: RiskSnapshot;
  riskLoading: boolean;
  riskError: unknown;
  fieldProps?: FieldProps;
  fieldRisk?: FieldRisk;
  cell?: CellInfo;
  onSelectField: (id: number) => void;
  onBack: () => void;
}

export function SidePanel(p: Props) {
  return (
    <aside className="flex w-full shrink-0 flex-col border-t border-slate-200 bg-white md:w-[380px] md:overflow-y-auto md:border-l md:border-t-0">
      {p.riskError ? <ErrorState error={p.riskError} /> : null}
      {p.fieldProps ? <FieldView {...p} fieldProps={p.fieldProps} /> : <FarmView {...p} />}
    </aside>
  );
}

function LevelBar({ byLevel, total }: { byLevel: Record<Level, number>; total: number }) {
  return (
    <div className="flex h-2 overflow-hidden rounded-full bg-slate-100">
      {(["red", "yellow", "green", "no_data"] as Level[]).map((l) => (
        <div key={l} style={{ width: `${(byLevel[l] / total) * 100}%`, background: LEVEL_COLOR[l] }} />
      ))}
    </div>
  );
}

function Stat({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="text-[11px] font-medium text-slate-500">{label}</div>
      <div className="mt-0.5 text-lg font-semibold tracking-tight" style={accent ? { color: accent } : undefined}>{value}</div>
      {hint && <div className="text-[11px] text-slate-400">{hint}</div>}
    </div>
  );
}

function FarmView({ farm, risk, riskLoading, onSelectField }: Props) {
  const current = farm.seasons.find((s) => s.id === risk?.season_id);
  return (
    <div className="p-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold tracking-tight">{farm.name}</h2>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-slate-500">
            <MapPin className="size-3" /> {farm.municipality}-{farm.state} · {farm.crop} · Season {current?.name ?? "—"}
          </p>
        </div>
        <DemoBadge label="Demo" />
      </div>

      {riskLoading && !risk && <Loading label="Computing risk…" />}
      {risk && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Stat label="Monitored area" value={fmtHa(risk.summary.total_ha, 0)} hint={`${farm.fields.length} fields`} />
            <Stat label="Healthy area" value={fmtPct(risk.summary.pct_by_level.green)} accent={LEVEL_COLOR.green} />
            <Stat label="Watch" value={fmtHa(risk.summary.area_by_level.yellow)} hint={fmtPct(risk.summary.pct_by_level.yellow)} accent="#b38600" />
            <Stat label="Critical" value={fmtHa(risk.summary.area_by_level.red)} hint={fmtPct(risk.summary.pct_by_level.red)} accent={LEVEL_COLOR.red} />
          </div>
          <div className="mt-3"><LevelBar byLevel={risk.summary.area_by_level} total={risk.summary.total_ha} /></div>

          <h3 className="mb-2 mt-6 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Fields by severity</h3>
          <ul className="space-y-1.5">
            {risk.fields.map((f) => {
              const affected = f.area_by_level.red + f.area_by_level.yellow;
              const delta = f.ndvi_mean != null && f.ndvi_baseline != null ? f.ndvi_mean - f.ndvi_baseline : null;
              return (
                <li key={f.field_id}>
                  <button
                    onClick={() => onSelectField(f.field_id)}
                    className="group flex w-full items-center gap-3 rounded-lg border border-slate-200 p-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    <span className="h-9 w-1 rounded-full" style={{ background: LEVEL_COLOR[f.level] }} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold">{f.name}</span>
                        <Badge tone={f.level}>{LEVEL_LABEL[f.level]}</Badge>
                      </div>
                      <div className="mt-0.5 text-[11px] text-slate-500">
                        {affected > 0.5 ? `${fmtHa(affected)} anomalous` : "No relevant anomalous area"} · NDVI {fmt(f.ndvi_mean, 2)}
                        {delta != null && <span className={cn("ml-1", delta < -0.02 ? "text-red-600" : "text-slate-400")}>({delta >= 0 ? "+" : ""}{fmt(delta, 2)} vs. history)</span>}
                      </div>
                    </div>
                    <ChevronRight className="size-4 text-slate-300 group-hover:text-slate-500" />
                  </button>
                </li>
              );
            })}
          </ul>
          <MethodNote risk={risk} />
        </>
      )}
    </div>
  );
}

function FieldView({ fieldProps: f, fieldRisk: fr, cell, risk, onBack }: Props & { fieldProps: FieldProps }) {
  const series = useQuery({ queryKey: ["series", f.id], queryFn: () => api.fieldSeries(f.id) });
  const assess = useQuery({
    queryKey: ["assessment", f.id, risk?.date],
    queryFn: () => api.assessment(f.id, risk!.date),
    enabled: !!risk,
  });
  return (
    <div className="p-5">
      <button onClick={onBack} className="mb-3 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800">
        <ArrowLeft className="size-3.5" /> Farm
      </button>
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold tracking-tight">{f.name}</h2>
          <p className="mt-0.5 text-xs text-slate-500">{fmtHa(f.area_ha)} · {f.irrigation}</p>
        </div>
        {fr && <Badge tone={fr.level}>{LEVEL_LABEL[fr.level]}</Badge>}
      </div>

      {cell && risk && <CellCard cell={cell} risk={risk} fieldName={f.name} />}

      {fr && (
        <div className="mt-4">
          <div className="grid grid-cols-3 gap-2">
            <Stat label="Critical" value={fmtHa(fr.area_by_level.red)} accent={LEVEL_COLOR.red} />
            <Stat label="Watch" value={fmtHa(fr.area_by_level.yellow)} accent="#b38600" />
            <Stat label="Mean NDVI" value={fmt(fr.ndvi_mean, 2)} hint={`hist. ${fmt(fr.ndvi_baseline, 2)}`} />
          </div>
          <div className="mt-3"><LevelBar byLevel={fr.area_by_level} total={fr.area_ha} /></div>
        </div>
      )}

      <div className="mt-6">
        {assess.isLoading && <Loading label="Analyzing zone, hypotheses and exposure…" />}
        {assess.error && <ErrorState error={assess.error} onRetry={() => assess.refetch()} />}
        {assess.data && <AssessmentPanel a={assess.data} compact footer={<CreateTaskButton a={assess.data} />} />}
        <Link href={`/fields/${f.id}`} className="mt-4 flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50">
          Open field: history and memory <ArrowRight className="size-3.5" />
        </Link>
      </div>

      <h3 className="mb-1 mt-6 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Field mean NDVI by season</h3>
      {series.isLoading && <Loading />}
      {series.error && <ErrorState error={series.error} onRetry={() => series.refetch()} />}
      {series.data && <FieldSeriesChart series={series.data} das={risk?.das} />}
      <p className="text-[11px] text-slate-400">Means of cloud-free cells. Dashed vertical line: selected date.</p>

      <dl className="mt-5 space-y-2 text-xs">
        <div className="flex gap-2"><Layers className="mt-0.5 size-3.5 text-slate-400" /><dt className="w-16 text-slate-500">Soil</dt><dd className="flex-1">{f.soil_texture ?? "—"}</dd></div>
        <div className="flex gap-2"><Droplets className="mt-0.5 size-3.5 text-slate-400" /><dt className="w-16 text-slate-500">Water</dt><dd className="flex-1 capitalize">{f.irrigation}</dd></div>
        <div className="flex gap-2"><MapPin className="mt-0.5 size-3.5 text-slate-400" /><dt className="w-16 text-slate-500">Boundary</dt><dd className="flex-1">{f.boundary_source === "synthetic_demo" ? "Synthetic polygon (demo)" : f.boundary_source}</dd></div>
      </dl>
    </div>
  );
}

function CellCard({ cell, risk, fieldName }: { cell: CellInfo; risk: RiskSnapshot; fieldName: string }) {
  const diff = cell.ndvi != null && cell.baseline != null ? cell.ndvi - cell.baseline : null;
  const why =
    cell.level === "no_data"
      ? "This cell's observation was discarded due to cloud cover. Pick another date."
      : `NDVI ${fmt(cell.ndvi, 2)} ${diff != null ? `is ${fmt(Math.abs(diff), 2)} ${diff < 0 ? "below" : "above"} this cell's history at the same stage (DAS ${risk.das})` : "has no comparable history"}. ` +
        `Anomaly score ${fmt(cell.score, 1)} — thresholds: watch ≥ ${fmt(risk.thresholds.yellow, 1)}, critical ≥ ${fmt(risk.thresholds.red, 1)}.`;
  return (
    <div className="mt-4 rounded-xl border p-4" style={{ borderColor: `${LEVEL_COLOR[cell.level]}66`, background: `${LEVEL_COLOR[cell.level]}0d` }}>
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-slate-700">Management cell #{cell.id}</div>
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold" style={{ color: LEVEL_COLOR[cell.level] }}>
          <span className="size-2 rounded-full" style={{ background: LEVEL_COLOR[cell.level] }} />{LEVEL_LABEL[cell.level]}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-y-2 text-xs">
        <Metric label="NDVI" value={fmt(cell.ndvi, 2)} />
        <Metric label="History" value={fmt(cell.baseline, 2)} />
        <Metric label="Difference" value={diff == null ? "—" : `${diff >= 0 ? "+" : ""}${fmt(diff, 2)}`} />
        <Metric label="NDRE" value={fmt(cell.ndre, 2)} />
        <Metric label="Score" value={fmt(cell.score, 1)} />
        <Metric label="Confidence" value={cell.confidence ?? "—"} />
      </div>
      <p className="mt-3 text-xs leading-relaxed text-slate-600"><span className="font-medium text-slate-800">Why this color? </span>{why}</p>
      {(cell.level === "red" || cell.level === "yellow") && (
        <p className="mt-2 text-[11px] font-medium text-slate-700">This cell is part of the field’s anomalous zone. Hypotheses and exposure below.</p>
      )}
      <p className="mt-2 text-[11px] text-slate-500">
        {fieldName} · {fmt(cell.area_ha, 2)} ha · {fmtDate(risk.date)} · A signal to direct scouting, not a diagnosis.
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="font-semibold capitalize text-slate-800">{value}</div>
    </div>
  );
}

function MethodNote({ risk }: { risk: RiskSnapshot }) {
  return (
    <details className="mt-6 rounded-lg bg-slate-50 p-3 text-[11px] text-slate-600">
      <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-slate-700"><Info className="size-3.5" /> How risk is calculated</summary>
      <p className="mt-2 leading-relaxed">{risk.method}</p>
      <p className="mt-1.5 leading-relaxed">Source: {risk.source}. Values are not real satellite measurements.</p>
    </details>
  );
}
