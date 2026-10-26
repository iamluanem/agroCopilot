"use client";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "@/lib/api";
import { INDEX_RAMP, LEVEL_COLOR, LEVEL_LABEL } from "@/lib/colors";
import type { Level } from "@/lib/types";
import { fmtDate } from "@/lib/utils";

type CellFC = GeoJSON.FeatureCollection<GeoJSON.Polygon, { f: number; a: number }>;

function rampColor(v: number | null | undefined): string {
  if (v == null) return "#cbd5e1";
  const r = INDEX_RAMP.ndvi;
  if (v <= r[0][0]) return r[0][1];
  for (let i = 1; i < r.length; i++) {
    if (v <= r[i][0]) {
      const [a, ca] = r[i - 1];
      const [b, cb] = r[i];
      const t = (v - a) / (b - a);
      const p = (h: string, k: number) => parseInt(h.slice(k, k + 2), 16);
      const mix = (k: number) => Math.round(p(ca, k) + (p(cb, k) - p(ca, k)) * t).toString(16).padStart(2, "0");
      return `#${mix(1)}${mix(3)}${mix(5)}`;
    }
  }
  return r[r.length - 1][1];
}

export function FieldNdviSvg({ farmId, fieldId, date, zoneIds, title, mode = "risk" }: { farmId: number; fieldId: number; date: string; zoneIds: number[]; title: string; mode?: "risk" | "ndvi" }) {
  const cells = useQuery({
    queryKey: ["cells", farmId],
    staleTime: Infinity,
    queryFn: async () => (await (await fetch(api.cellsUrl(farmId))).json()) as CellFC,
  });
  const risk = useQuery({ queryKey: ["risk", farmId, date], queryFn: () => api.risk(farmId, date) });

  const drawing = useMemo(() => {
    if (!cells.data || !risk.data) return null;
    const idx = new Map(risk.data.cells.id.map((id, i) => [id, i]));
    const feats = cells.data.features.filter((f) => f.properties.f === fieldId);
    let [x0, y0, x1, y1] = [Infinity, Infinity, -Infinity, -Infinity];
    feats.forEach((f) => f.geometry.coordinates[0].forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }));
    const kx = Math.cos(((y0 + y1) / 2) * Math.PI / 180);
    const W = 300;
    const s = W / ((x1 - x0) * kx);
    const H = (y1 - y0) * s;
    const zone = new Set(zoneIds);
    const paths = feats.map((f) => {
      const d = f.geometry.coordinates[0].map(([x, y], i) => `${i ? "L" : "M"}${((x - x0) * kx * s).toFixed(1)},${((y1 - y) * s).toFixed(1)}`).join("") + "Z";
      const i = idx.get(Number(f.id));
      const lvl = i != null ? risk.data.levels[risk.data.cells.level[i]] : "no_data";
      const fill = mode === "risk" ? LEVEL_COLOR[lvl] : rampColor(i != null ? risk.data.cells.ndvi[i] : null);
      return { id: Number(f.id), d, fill, zone: zone.has(Number(f.id)) };
    });
    return { W, H, paths };
  }, [cells.data, risk.data, fieldId, zoneIds, mode]);

  return (
    <figure className="rounded-xl border border-slate-200 bg-white p-3">
      <figcaption className="mb-2 flex items-center justify-between text-xs">
        <span className="font-semibold text-slate-800">{title}</span>
        <span className="text-slate-500">{fmtDate(date)}{risk.data?.simulated ? " · simulated" : ""}</span>
      </figcaption>
      {risk.data && (
        <div className="mb-2 flex gap-3 text-[11px] text-slate-600">
          {(["red", "yellow"] as Level[]).map((l) => {
            const ha = risk.data.fields.find((f) => f.field_id === fieldId)?.area_by_level[l] ?? 0;
            return <span key={l} className="inline-flex items-center gap-1"><span className="size-2 rounded-sm" style={{ background: LEVEL_COLOR[l] }} />{LEVEL_LABEL[l]} {ha.toFixed(1)} ha</span>;
          })}
        </div>
      )}
      {!drawing ? <div className="grid aspect-square place-items-center text-xs text-slate-400">Loading…</div> : (
        <svg viewBox={`0 0 ${drawing.W} ${drawing.H}`} className="w-full" role="img" aria-label={`Field ${mode === "risk" ? "risk" : "NDVI"} map on ${fmtDate(date)}`}>
          {drawing.paths.map((p) => <path key={p.id} d={p.d} fill={p.fill} stroke={p.fill} strokeWidth={0.4} />)}
          <g fill="none" stroke="#0a1120" strokeWidth={0.6} strokeOpacity={0.35}>
            {drawing.paths.filter((p) => p.zone).map((p) => <path key={p.id} d={p.d} />)}
          </g>
        </svg>
      )}
    </figure>
  );
}

export function NdviLegend() {
  return (
    <div className="flex flex-wrap items-center gap-3 text-[10px] text-slate-500">
      {(["red", "yellow", "green"] as Level[]).map((l) => (
        <span key={l} className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm" style={{ background: LEVEL_COLOR[l] }} />{LEVEL_LABEL[l]}</span>
      ))}
      <span>· risk relative to history at the same stage and to the field median (discounts senescence) · outline = treated zone</span>
    </div>
  );
}
