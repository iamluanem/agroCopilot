"use client";
import { Cloud, FlaskConical } from "lucide-react";
import type { ObsDate } from "@/lib/types";
import { cn, fmtDate } from "@/lib/utils";

export function DateTimeline({ dates, value, onChange }: { dates: ObsDate[]; value: string | null; onChange: (d: string) => void }) {
  const sel = dates.find((d) => d.date === value);
  return (
    <div className="rounded-xl bg-white/95 px-3 pb-2 pt-2.5 shadow-lg ring-1 ring-slate-900/5 backdrop-blur">
      <div className="mb-1.5 flex items-baseline justify-between gap-4 text-xs">
        <span className="font-semibold text-slate-800">
          {sel ? fmtDate(sel.date, { day: "2-digit", month: "short", year: "numeric" }) : "—"}
          <span className="ml-1.5 font-normal text-slate-500">DAS {sel?.das ?? "—"}</span>
        </span>
        <span className="text-[11px] text-slate-500">
          {sel?.simulated ? (
            <span className="inline-flex items-center gap-1 font-medium text-violet-700"><FlaskConical className="size-3" /> Post-intervention simulation (demo)</span>
          ) : sel && sel.cloud_pct > 0 ? (
            <span className="inline-flex items-center gap-1 text-sky-700"><Cloud className="size-3" /> {sel.cloud_pct.toFixed(0)}% cloud — discarded</span>
          ) : "Cloud-free scene"}
        </span>
      </div>
      <div className="flex items-end gap-[3px]" role="listbox" aria-label="Observation dates">
        {dates.map((d, i) => {
          const active = d.date === value;
          const month = i === 0 || dates[i - 1].date.slice(5, 7) !== d.date.slice(5, 7);
          return (
            <button
              key={d.date}
              role="option"
              aria-selected={active}
              title={`${fmtDate(d.date)} · DAS ${d.das}${d.cloud_pct ? ` · ${d.cloud_pct.toFixed(0)}% cloud` : ""}`}
              onClick={() => onChange(d.date)}
              className="group flex w-5 flex-col items-center gap-1"
            >
              <span className="h-3">{d.simulated ? <FlaskConical className="size-3 text-violet-500" /> : d.cloud_pct > 5 && <Cloud className="size-3 text-sky-500" />}</span>
              <span
                className={cn(
                  "h-5 w-1.5 rounded-full transition",
                  active ? cn("h-6 w-2", d.simulated ? "bg-violet-600" : "bg-brand-600") : d.simulated ? "bg-violet-300 group-hover:bg-violet-400" : d.cloud_pct > 5 ? "bg-sky-200 group-hover:bg-sky-300" : "bg-slate-300 group-hover:bg-slate-400",
                )}
              />
              <span className={cn("h-3 text-[9px] uppercase text-slate-400", active && "font-semibold text-brand-700")}>
                {month ? fmtDate(d.date, { month: "short" }).replace(".", "") : ""}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
