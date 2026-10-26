"use client";
import { AlertTriangle, ClipboardCheck, ClipboardPlus, LineChart, NotebookPen, Search, Sprout, Wrench } from "lucide-react";
import { useMemo, useState } from "react";
import type { MemoryEvent } from "@/lib/types";
import { cn, fmtDate } from "@/lib/utils";
import { DemoBadge } from "../ui/demo-badge";

const TYPE = {
  season: { icon: Sprout, label: "Season", cls: "bg-slate-100 text-slate-600" },
  anomaly: { icon: AlertTriangle, label: "Anomaly", cls: "bg-red-50 text-red-600" },
  inspection: { icon: ClipboardCheck, label: "Inspection", cls: "bg-sky-50 text-sky-700" },
  intervention: { icon: Wrench, label: "Intervention", cls: "bg-violet-50 text-violet-700" },
  outcome: { icon: LineChart, label: "Outcome", cls: "bg-emerald-50 text-emerald-700" },
  note: { icon: NotebookPen, label: "Field note", cls: "bg-amber-50 text-amber-700" },
  task: { icon: ClipboardPlus, label: "Task", cls: "bg-brand-50 text-brand-700" },
} as const;

export function MemoryTimeline({ events }: { events: MemoryEvent[] }) {
  const [q, setQ] = useState("");
  const [hideSeason, setHideSeason] = useState(true);
  const list = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return events.filter((e) => (!hideSeason || e.type !== "season" || needle) &&
      (!needle || `${e.title} ${e.summary}`.toLowerCase().includes(needle)));
  }, [events, q, hideSeason]);
  const seasons = [...new Set(list.map((e) => e.season ?? "—"))];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="flex flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 focus-within:ring-2 focus-within:ring-brand-500/30">
          <Search className="size-3.5 text-slate-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search memory — e.g. water, pivot, stand" className="w-full bg-transparent text-xs outline-none placeholder:text-slate-400" />
        </label>
        <label className="flex items-center gap-1.5 text-[11px] text-slate-500">
          <input type="checkbox" checked={hideSeason} onChange={(e) => setHideSeason(e.target.checked)} className="accent-brand-600" /> Hide season milestones
        </label>
        <DemoBadge label="Demo" />
      </div>
      {list.length === 0 && <p className="rounded-lg bg-slate-50 p-4 text-center text-xs text-slate-500">Nothing found in this field’s memory.</p>}
      {seasons.map((season) => (
        <section key={season} className="mb-4">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Season {season}</div>
          <ol className="relative ml-3 border-l border-slate-200">
            {list.filter((e) => (e.season ?? "—") === season).map((e) => {
              const t = TYPE[e.type] ?? TYPE.note;
              const Icon = t.icon;
              return (
                <li key={e.id} className="mb-3 ml-5">
                  <span className={cn("absolute -left-3 grid size-6 place-items-center rounded-full ring-4 ring-white", t.cls)}><Icon className="size-3" /></span>
                  <div className="flex flex-wrap items-baseline gap-x-2 text-[11px] text-slate-500">
                    <span className="font-medium text-slate-700">{fmtDate(e.date)}</span>
                    <span>{t.label}</span>
                  </div>
                  <div className="text-xs font-semibold text-slate-900">{e.title}</div>
                  {e.summary && <p className="mt-0.5 text-xs leading-relaxed text-slate-600">{e.summary}</p>}
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
