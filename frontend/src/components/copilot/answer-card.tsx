"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, CircleHelp, ClipboardPlus, Database, Lightbulb, Loader2, Wrench } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import type { CopilotResponse, TaskProposal } from "@/lib/types";
import { cn, fmtDate } from "@/lib/utils";
import { ConfidencePill } from "../intel/assessment-cards";

const TOOL_LABEL: Record<string, string> = {
  get_farm_summary: "farm summary",
  get_field_risk: "field assessment",
  get_cell_history: "cell history",
  compare_fields: "field comparison",
  get_weather: "weather",
  get_memory: "field memory",
  list_tasks: "tasks",
  estimate_economics: "economic model",
  get_intervention_outcomes: "intervention outcomes",
  propose_inspection: "inspection proposal",
};

function Section({ icon: Icon, title, children, tone = "text-slate-400" }: { icon: typeof Lightbulb; title: string; children: React.ReactNode; tone?: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400"><Icon className={cn("size-3", tone)} />{title}</div>
      {children}
    </div>
  );
}

export function AnswerCard({ r, source }: { r: CopilotResponse; source: string }) {
  const a = r.answer;
  return (
    <div className="space-y-3 rounded-2xl rounded-tl-sm border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="flex-1 text-[13px] leading-relaxed text-slate-900">{a.summary}</p>
        <ConfidencePill value={a.confidence} />
      </div>

      {a.evidence.length > 0 && (
        <Section icon={CheckCircle2} title="Evidence" tone="text-emerald-600">
          <ul className="space-y-1 text-xs leading-snug text-slate-700">
            {a.evidence.map((e, i) => <li key={i} className="flex gap-1.5"><span className="mt-1.5 size-1 shrink-0 rounded-full bg-slate-400" />{e}</li>)}
          </ul>
        </Section>
      )}

      {a.missing_data.length > 0 && (
        <Section icon={CircleHelp} title="Missing data" tone="text-amber-500">
          <ul className="space-y-1 text-xs leading-snug text-slate-600">
            {a.missing_data.map((e, i) => <li key={i} className="flex gap-1.5"><span className="mt-1.5 size-1 shrink-0 rounded-full bg-amber-400" />{e}</li>)}
          </ul>
        </Section>
      )}

      <div className="flex gap-2 rounded-lg bg-brand-50 p-2.5 text-xs leading-relaxed text-brand-700 ring-1 ring-brand-100">
        <Lightbulb className="mt-0.5 size-3.5 shrink-0" />
        <p><span className="font-semibold">Next action. </span>{a.next_action}</p>
      </div>

      {a.proposed_task && <TaskConfirm t={a.proposed_task} source={source} />}

      <div className="flex flex-wrap gap-1.5 border-t border-slate-100 pt-2.5">
        {a.sources.map((f, i) => (
          <span key={i} className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600" title={f.ref ?? undefined}>
            <Database className="size-2.5" />{f.label}
          </span>
        ))}
      </div>
      {a.warnings.length > 0 && (
        <ul className="space-y-0.5 text-[10px] leading-snug text-slate-400">
          {a.warnings.map((x, i) => <li key={i} className="flex gap-1"><AlertTriangle className="mt-px size-2.5 shrink-0" />{x}</li>)}
        </ul>
      )}
      <details className="text-[10px] text-slate-400">
        <summary className="inline-flex cursor-pointer items-center gap-1"><Wrench className="size-2.5" /> {r.provider} · {r.tools_used.length} quer{r.tools_used.length === 1 ? "y" : "ies"}</summary>
        <ul className="mt-1 space-y-0.5 font-mono">
          {r.tools_used.map((t, i) => <li key={i}>{TOOL_LABEL[t.name] ?? t.name} — {t.name}({Object.entries(t.args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})</li>)}
        </ul>
      </details>
    </div>
  );
}

function TaskConfirm({ t, source }: { t: TaskProposal; source: string }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState(t);
  const m = useMutation({
    mutationFn: () => api.createTask(draft, source),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tasks-summary"] });
      qc.invalidateQueries({ queryKey: ["field", t.field_id] });
    },
  });
  if (m.data) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
        <CheckCircle2 className="size-4" />
        <span className="flex-1">Task #{m.data.id} created and assigned to {m.data.assignee ?? "—"}. Logged in {m.data.field_code}’s memory.</span>
        <Link href={`/fields/${m.data.field_id}`} className="font-medium underline">View field</Link>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-slate-300 bg-slate-50 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold text-slate-700"><ClipboardPlus className="size-3.5" /> Inspection proposal — not saved yet</div>
      <label className="block text-[10px] font-medium uppercase tracking-wide text-slate-400">Title
        <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} className="mt-0.5 w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-xs normal-case tracking-normal text-slate-800 outline-none focus:ring-2 focus:ring-brand-500/30" />
      </label>
      <div className="mt-2 grid grid-cols-3 gap-2">
        <label className="col-span-2 block text-[10px] font-medium uppercase tracking-wide text-slate-400">Assignee
          <input value={draft.assignee ?? ""} onChange={(e) => setDraft({ ...draft, assignee: e.target.value || null })} className="mt-0.5 w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-xs normal-case tracking-normal text-slate-800 outline-none" />
        </label>
        <label className="block text-[10px] font-medium uppercase tracking-wide text-slate-400">Due
          <input type="date" value={draft.due_date ?? ""} onChange={(e) => setDraft({ ...draft, due_date: e.target.value || null })} className="mt-0.5 w-full rounded-md border border-slate-200 bg-white px-1.5 py-1 text-xs text-slate-800 outline-none" />
        </label>
      </div>
      <p className="mt-2 text-[11px] leading-snug text-slate-600">{draft.instructions}</p>
      <div className="mt-3 flex items-center gap-2">
        <button onClick={() => m.mutate()} disabled={m.isPending} className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
          {m.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />} Confirm and create inspection
        </button>
        <span className="text-[11px] text-slate-500">Priority {draft.priority}{draft.due_date ? ` · due ${fmtDate(draft.due_date)}` : ""}</span>
      </div>
      {m.error && <p className="mt-2 text-[11px] text-red-600">{(m.error as Error).message}</p>}
    </div>
  );
}
