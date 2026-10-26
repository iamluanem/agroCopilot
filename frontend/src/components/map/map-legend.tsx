import { INDEX_RAMP, LEVEL_COLOR, LEVEL_DESC, LEVEL_LABEL } from "@/lib/colors";
import type { Level, LayerMode, SentinelScene } from "@/lib/types";
import { Satellite } from "lucide-react";
import { fmt, fmtDate } from "@/lib/utils";

export function MapLegend({ mode, scene }: { mode: LayerMode; scene?: SentinelScene }) {
  if (mode === "sentinel" && scene) {
    const ramp = INDEX_RAMP.ndvi;
    return (
      <div className="w-56 rounded-xl bg-white/95 p-3 shadow-lg ring-1 ring-slate-900/5 backdrop-blur">
        <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-emerald-700"><Satellite className="size-3.5" /> Real Sentinel-2 · NDVI</div>
        <div className="text-[11px] text-slate-600">{fmtDate(scene.date)} · cloud {fmt(scene.cloud_cover, 1)}% · {fmt(scene.valid_pct, 0)}% valid</div>
        <div className="mt-2 h-2.5 rounded-full" style={{ background: `linear-gradient(to right, ${ramp.map(([, c]) => c).join(",")})` }} />
        <div className="mt-1 flex justify-between text-[10px] text-slate-500"><span>≤ {fmt(ramp[0][0], 2)}</span><span>{fmt(ramp[ramp.length - 1][0], 2)}+</span></div>
        <p className="mt-2 text-[10px] leading-snug text-slate-500">Real Copernicus imagery (10 m). Clouds masked with SCL. Field boundaries remain synthetic.</p>
      </div>
    );
  }
  if (mode === "risk") {
    return (
      <div className="w-40 rounded-xl bg-white/95 p-3 shadow-lg ring-1 ring-slate-900/5 backdrop-blur">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Risk per cell</div>
        <ul className="space-y-1.5">
          {(["red", "yellow", "green", "no_data"] as Level[]).map((l) => (
            <li key={l} className="flex items-center gap-2 text-xs text-slate-700" title={LEVEL_DESC[l]}>
              <span className="size-3 shrink-0 rounded-sm" style={{ background: LEVEL_COLOR[l] }} />
              {LEVEL_LABEL[l]}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  const ramp = INDEX_RAMP[mode === "ndre" ? "ndre" : "ndvi"];
  return (
    <div className="w-40 rounded-xl bg-white/95 p-3 shadow-lg ring-1 ring-slate-900/5 backdrop-blur">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{mode.toUpperCase()}</div>
      <div className="h-2.5 rounded-full" style={{ background: `linear-gradient(to right, ${ramp.map(([, c]) => c).join(",")})` }} />
      <div className="mt-1 flex justify-between text-[10px] text-slate-500">
        <span>≤ {fmt(ramp[0][0], 2)}</span><span>{fmt(ramp[ramp.length - 1][0], 2)}+</span>
      </div>
      <p className="mt-2 text-[11px] leading-snug text-slate-500">Raw index. A low value alone does not indicate the cause — use the risk layer and field scouting.</p>
    </div>
  );
}
