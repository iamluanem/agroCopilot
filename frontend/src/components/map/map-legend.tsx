import { INDEX_RAMP, LEVEL_COLOR, LEVEL_DESC, LEVEL_LABEL } from "@/lib/colors";
import type { Level, LayerMode } from "@/lib/types";
import { fmt } from "@/lib/utils";

export function MapLegend({ mode }: { mode: LayerMode }) {
  if (mode === "risco") {
    return (
      <div className="w-40 rounded-xl bg-white/95 p-3 shadow-lg ring-1 ring-slate-900/5 backdrop-blur">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Risco por célula</div>
        <ul className="space-y-1.5">
          {(["vermelho", "amarelo", "verde", "sem_dado"] as Level[]).map((l) => (
            <li key={l} className="flex items-center gap-2 text-xs text-slate-700" title={LEVEL_DESC[l]}>
              <span className="size-3 shrink-0 rounded-sm" style={{ background: LEVEL_COLOR[l] }} />
              {LEVEL_LABEL[l]}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  const ramp = INDEX_RAMP[mode];
  return (
    <div className="w-40 rounded-xl bg-white/95 p-3 shadow-lg ring-1 ring-slate-900/5 backdrop-blur">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{mode.toUpperCase()}</div>
      <div className="h-2.5 rounded-full" style={{ background: `linear-gradient(to right, ${ramp.map(([, c]) => c).join(",")})` }} />
      <div className="mt-1 flex justify-between text-[10px] text-slate-500">
        <span>≤ {fmt(ramp[0][0], 2)}</span><span>{fmt(ramp[ramp.length - 1][0], 2)}+</span>
      </div>
      <p className="mt-2 text-[11px] leading-snug text-slate-500">Índice bruto. Valor baixo isolado não indica a causa — use a camada de risco e a vistoria.</p>
    </div>
  );
}
