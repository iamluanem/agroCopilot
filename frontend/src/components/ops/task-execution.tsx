"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowLeft, Camera, CheckCircle2, FlaskConical, Loader2, Map as MapIcon, PlayCircle, ShieldCheck, Wrench, X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TaskDetail } from "@/lib/types";
import { cn, fmtBRL, fmtDate, fmtHa } from "@/lib/utils";
import { ConfidencePill } from "../intel/assessment-cards";
import { DemoBadge } from "../ui/demo-badge";
import { ErrorState, Loading } from "../ui/states";
import { StatusBadge, StatusStepper } from "./status";

const CAUSES = ["Water stress", "Pest or disease pressure", "Nutrient deficiency",
  "Stand failure / uneven emergence", "Not confirmed"];
const CHEMICAL = /(pesticid|insecticid|fungicid|herbicid|acaricid|agrochemical|spray|l\/ha|ml\/ha|g\/ha|dose)/i;
const input = "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500/30";
const label = "block text-xs font-medium text-slate-600";

function Box({ title, icon: Icon, children, done }: { title: string; icon: typeof Camera; children: React.ReactNode; done?: boolean }) {
  return (
    <section className={cn("rounded-2xl border bg-white p-4", done ? "border-emerald-200" : "border-slate-200")}>
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
        <Icon className={cn("size-4", done ? "text-emerald-600" : "text-slate-400")} />{title}
        {done && <CheckCircle2 className="ml-auto size-4 text-emerald-600" />}
      </h2>
      {children}
    </section>
  );
}

async function resizeToDataUrl(file: File, max = 1280): Promise<string> {
  const bmp = await createImageBitmap(file);
  const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas");
  c.width = Math.round(bmp.width * k);
  c.height = Math.round(bmp.height * k);
  c.getContext("2d")!.drawImage(bmp, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.8);
}

const readDraft = <T,>(key: string, fallback: T): T => {
  try {
    const raw = localStorage.getItem(key);
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback;
  } catch {
    return fallback;
  }
};
const writeDraft = (key: string, v: unknown) => {
  try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* storage unavailable */ }
};
const clearDraft = (key: string) => {
  try { localStorage.removeItem(key); } catch { /* ignore */ }
};

export function TaskExecution({ taskId }: { taskId: number }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["task", taskId], queryFn: () => api.task(taskId) });
  const refresh = (d: TaskDetail) => {
    qc.setQueryData(["task", taskId], d);
    ["tasks", "tasks-summary", "field", "outcomes"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  };
  const start = useMutation({ mutationFn: () => api.setStatus(taskId, "in_progress"), onSuccess: refresh });

  if (q.isLoading) return <Loading label="Loading task…" />;
  if (q.error || !q.data) return <ErrorState error={q.error ?? "Task not found"} onRetry={() => q.refetch()} />;
  const t = q.data;
  const iv = t.interventions[0];

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="mx-auto max-w-xl space-y-3 p-4 pb-16 sm:p-6">
        <Link href="/tasks" className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800"><ArrowLeft className="size-3.5" /> Tasks</Link>
        <header className="rounded-2xl bg-navy-950 p-4 text-white">
          <div className="flex items-center gap-2 text-[11px] text-slate-400">#{t.id} · {t.field_name} <span className="ml-auto"><StatusBadge s={t.status} /></span></div>
          <h1 className="mt-1 text-base font-semibold leading-snug">{t.title}</h1>
          <p className="mt-1 text-xs text-slate-400">{t.assignee ?? "Unassigned"}{t.due_date ? ` · due ${fmtDate(t.due_date)}` : ""} · {t.priority} priority</p>
          <div className="mt-4 rounded-xl bg-white p-3"><StatusStepper flow={t.status_flow} current={t.status} /></div>
        </header>

        <Box title="What to check" icon={MapIcon}>
          {t.assessment && (
            <div className="mb-3 space-y-2 text-xs text-slate-600">
              <p>{t.assessment.observation}</p>
              <div className="flex flex-wrap gap-1.5">
                {t.assessment.hypotheses.slice(0, 3).map((h, i) => (
                  <span key={h.cause} className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px]", i === 0 ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600")}>
                    {h.cause} <span className="opacity-70">· {h.confidence}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
          {t.instructions && <p className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-700">{t.instructions}</p>}
          {t.previous_intervention && (
            <p className="mt-2 text-[11px] text-slate-500">Last time this happened ({fmtDate(t.previous_intervention.executed_at)}): {t.previous_intervention.approved_action}</p>
          )}
          <Link href={`/map?field=${t.field_id}`} className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline"><MapIcon className="size-3.5" /> View zone on map</Link>
        </Box>

        {(t.status === "pending" || t.status === "assigned") && (
          <button onClick={() => start.mutate()} disabled={start.isPending} className="flex w-full items-center justify-center gap-2 rounded-2xl bg-brand-600 py-3.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60">
            {start.isPending ? <Loader2 className="size-4 animate-spin" /> : <PlayCircle className="size-4" />} Start field inspection
          </button>
        )}

        {t.status === "in_progress" && <InspectionForm t={t} onDone={refresh} />}
        {t.inspection && <InspectionSummary t={t} />}
        {t.status === "completed" && <VerifyForm t={t} onDone={refresh} />}
        {t.status === "verified" && !iv && t.inspection && <InterventionForm t={t} onDone={() => q.refetch()} />}
        {iv && <InterventionSummary t={t} onSimulated={() => q.refetch()} />}
      </div>
    </div>
  );
}

function InspectionForm({ t, onDone }: { t: TaskDetail; onDone: (d: TaskDetail) => void }) {
  const key = `agrocopilot:inspection:${t.id}`;
  const empty = { findings: "", verified_cause: "", notes: "", recorded_by: t.assignee?.split(" (")[0] ?? "", photos: [] as string[] };
  const [d, setD] = useState(empty);
  const [restored, setRestored] = useState(false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const draft = readDraft(key, empty);
    setRestored(draft.findings !== "" || draft.photos.length > 0);
    setD(draft);
    setLoaded(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => { if (loaded) writeDraft(key, d); }, [key, d, loaded]);

  const m = useMutation({
    mutationFn: () => api.inspect(t.id, { ...d, verified_cause: d.verified_cause || null, notes: d.notes || null }),
    onSuccess: (r) => { clearDraft(key); onDone(r); },
  });
  const addPhotos = async (files: FileList | null) => {
    if (!files) return;
    const urls = await Promise.all([...files].slice(0, 6 - d.photos.length).map((f) => resizeToDataUrl(f)));
    setD((x) => ({ ...x, photos: [...x.photos, ...urls] }));
  };
  const valid = d.findings.trim().length >= 5 && d.recorded_by.trim().length >= 2;

  return (
    <Box title="Record inspection" icon={Camera}>
      {restored && <p className="mb-3 rounded-lg bg-sky-50 px-3 py-2 text-[11px] text-sky-800">Draft restored from this device — nothing was lost.</p>}
      <div className="space-y-3">
        <label className={label}>What did you find?
          <textarea rows={4} value={d.findings} onChange={(e) => setD({ ...d, findings: e.target.value })} className={cn(input, "mt-1")}
            placeholder="E.g. plants wilting in the hot hours in the southwest sector; sprinklers on towers 7 and 8 clogged; beat-sheet counts below action threshold." />
        </label>
        <div>
          <span className={label}>Cause verified in the field</span>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {CAUSES.map((c) => (
              <button key={c} type="button" onClick={() => setD({ ...d, verified_cause: d.verified_cause === c ? "" : c })}
                className={cn("rounded-full border px-3 py-1.5 text-xs transition", d.verified_cause === c ? "border-navy-900 bg-navy-900 text-white" : "border-slate-200 bg-white text-slate-700 hover:border-slate-300")}>
                {c}
              </button>
            ))}
          </div>
        </div>
        <div>
          <span className={label}>Photos ({d.photos.length}/6)</span>
          <div className="mt-1 grid grid-cols-3 gap-2">
            {d.photos.map((p, i) => (
              <div key={i} className="relative aspect-square overflow-hidden rounded-lg bg-slate-100">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p} alt={`Photo ${i + 1}`} className="size-full object-cover" />
                <button type="button" aria-label="Remove photo" onClick={() => setD({ ...d, photos: d.photos.filter((_, j) => j !== i) })} className="absolute right-1 top-1 rounded-full bg-black/60 p-0.5 text-white"><X className="size-3" /></button>
              </div>
            ))}
            {d.photos.length < 6 && (
              <label className="grid aspect-square cursor-pointer place-items-center rounded-lg border-2 border-dashed border-slate-300 text-slate-400 hover:border-brand-500 hover:text-brand-600">
                <span className="flex flex-col items-center gap-1 text-[11px]"><Camera className="size-5" />Add</span>
                <input type="file" accept="image/*" capture="environment" multiple className="hidden" onChange={(e) => addPhotos(e.target.files)} />
              </label>
            )}
          </div>
        </div>
        <label className={label}>Notes
          <input value={d.notes} onChange={(e) => setD({ ...d, notes: e.target.value })} className={cn(input, "mt-1")} placeholder="Optional" />
        </label>
        <label className={label}>Recorded by
          <input value={d.recorded_by} onChange={(e) => setD({ ...d, recorded_by: e.target.value })} className={cn(input, "mt-1")} />
        </label>
        <button disabled={!valid || m.isPending} onClick={() => m.mutate()} className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50">
          {m.isPending ? <Loader2 className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />} Complete inspection
        </button>
        {m.error && <p className="text-xs text-red-600">{(m.error as Error).message}</p>}
        <p className="text-[11px] text-slate-400">The draft is saved on this device while you fill it in.</p>
      </div>
    </Box>
  );
}

function InspectionSummary({ t }: { t: TaskDetail }) {
  const i = t.inspection!;
  return (
    <Box title="Inspection recorded" icon={Camera} done>
      <div className="space-y-2 text-xs text-slate-700">
        <div className="flex flex-wrap gap-2 text-[11px] text-slate-500">{fmtDate(i.inspected_at)} · {i.recorded_by}</div>
        <p className="text-sm font-semibold text-slate-900">Verified cause: {i.verified_cause ?? "not confirmed"}</p>
        <p className="leading-relaxed">{i.findings}</p>
        {i.notes && <p className="whitespace-pre-line text-slate-500">{i.notes}</p>}
        {i.photos.length > 0 && (
          <div className="grid grid-cols-3 gap-2 pt-1">
            {i.photos.map((p) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={p} src={api.mediaUrl(p)} alt="Inspection photo" className="aspect-square w-full rounded-lg object-cover" />
            ))}
          </div>
        )}
      </div>
    </Box>
  );
}

function VerifyForm({ t, onDone }: { t: TaskDetail; onDone: (d: TaskDetail) => void }) {
  const [by, setBy] = useState("Mariana Rocha, agronomist (CREA-MT)");
  const [notes, setNotes] = useState("");
  const m = useMutation({ mutationFn: () => api.verify(t.id, by, notes || undefined), onSuccess: onDone });
  return (
    <Box title="Agronomist verification" icon={ShieldCheck}>
      <p className="mb-3 text-xs text-slate-600">A licensed agronomist reviews the findings before any intervention is approved.</p>
      <div className="space-y-3">
        <label className={label}>Responsible agronomist<input value={by} onChange={(e) => setBy(e.target.value)} className={cn(input, "mt-1")} /></label>
        <label className={label}>Opinion (optional)<input value={notes} onChange={(e) => setNotes(e.target.value)} className={cn(input, "mt-1")} placeholder="E.g. agree with the cause; prioritize sprinklers" /></label>
        <button disabled={by.trim().length < 2 || m.isPending} onClick={() => m.mutate()} className="flex w-full items-center justify-center gap-2 rounded-xl bg-navy-900 py-3 text-sm font-semibold text-white hover:bg-navy-800 disabled:opacity-50">
          {m.isPending ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />} Verify inspection
        </button>
        {m.error && <p className="text-xs text-red-600">{(m.error as Error).message}</p>}
      </div>
    </Box>
  );
}

function InterventionForm({ t, onDone }: { t: TaskDetail; onDone: () => void }) {
  const hydric = /water/i.test(t.inspection?.verified_cause ?? "");
  const [d, setD] = useState({
    recommended_action: t.previous_intervention?.approved_action ?? t.assessment?.next_step ?? "",
    approved_action: hydric ? "Unclog/replace sprinklers on the end towers and increase the irrigation depth in the affected sector for 10 days." : "",
    approved_by: "Mariana Rocha, agronomist (CREA-MT)",
    executed_at: "",
    actual_cost: hydric && t.assessment ? Math.round(t.assessment.affected_ha * 90) : 0,
    notes: "",
    prescription_confirmed: false,
  });
  const chemical = CHEMICAL.test(d.approved_action);
  const m = useMutation({
    mutationFn: () => api.intervene({ ...d, field_id: t.field_id, inspection_id: t.inspection!.id, executed_at: d.executed_at || null, notes: d.notes || null, recommended_action: d.recommended_action || null }),
    onSuccess: onDone,
  });
  return (
    <Box title="Approved intervention" icon={Wrench}>
      <div className="space-y-3">
        {d.recommended_action && <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600"><span className="font-semibold text-slate-800">Recommended: </span>{d.recommended_action}</p>}
        <label className={label}>Approved and executed action
          <textarea rows={3} value={d.approved_action} onChange={(e) => setD({ ...d, approved_action: e.target.value })} className={cn(input, "mt-1")} />
        </label>
        {chemical && (
          <label className="flex gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
            <input type="checkbox" checked={d.prescription_confirmed} onChange={(e) => setD({ ...d, prescription_confirmed: e.target.checked })} className="mt-0.5 accent-amber-600" />
            <span><AlertTriangle className="mr-1 inline size-3.5" />Involves a chemical product. Requires a prescription and validation by a licensed agronomist. I confirm the prescription was issued.</span>
          </label>
        )}
        <div className="grid grid-cols-2 gap-3">
          <label className={label}>Actual cost (R$)<input type="number" min={0} value={d.actual_cost} onChange={(e) => setD({ ...d, actual_cost: Number(e.target.value) })} className={cn(input, "mt-1")} /></label>
          <label className={label}>Executed on<input type="date" value={d.executed_at} onChange={(e) => setD({ ...d, executed_at: e.target.value })} className={cn(input, "mt-1")} /></label>
        </div>
        <label className={label}>Approved by<input value={d.approved_by} onChange={(e) => setD({ ...d, approved_by: e.target.value })} className={cn(input, "mt-1")} /></label>
        <button disabled={d.approved_action.trim().length < 5 || m.isPending || (chemical && !d.prescription_confirmed)} onClick={() => m.mutate()} className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50">
          {m.isPending ? <Loader2 className="size-4 animate-spin" /> : <Wrench className="size-4" />} Record intervention
        </button>
        {m.error && <p className="text-xs text-red-600">{(m.error as Error).message}</p>}
        <p className="text-[11px] text-slate-400">Empty date = demo reference date.</p>
      </div>
    </Box>
  );
}

function InterventionSummary({ t, onSimulated }: { t: TaskDetail; onSimulated: () => void }) {
  const qc = useQueryClient();
  const iv = t.interventions[0];
  const m = useMutation({
    mutationFn: () => api.simulate(iv.id),
    onSuccess: () => { ["outcomes", "dates", "risk", "field"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); onSimulated(); },
  });
  const o = iv.outcome;
  return (
    <>
      <Box title="Intervention recorded" icon={Wrench} done>
        <div className="space-y-1.5 text-xs text-slate-700">
          <p className="text-sm font-semibold text-slate-900">{iv.approved_action}</p>
          <p className="text-slate-500">{fmtDate(iv.executed_at)} · approved by {iv.approved_by} · actual cost <span className="font-semibold text-slate-800">{fmtBRL(iv.actual_cost)}</span></p>
        </div>
      </Box>
      {!o ? (
        <section className="rounded-2xl border-2 border-dashed border-violet-300 bg-violet-50/60 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-violet-900"><FlaskConical className="size-4" /> Measure the outcome</div>
          <p className="mt-1 text-xs leading-relaxed text-violet-900/80">
            In a real operation the app waits for the next satellite scenes. In the demo, generate 3 <strong>synthetic</strong> post-intervention observations (5, 10 and 15 days later) to measure the outcome against the comparison area.
          </p>
          <button onClick={() => m.mutate()} disabled={m.isPending} className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-violet-700 py-3 text-sm font-semibold text-white hover:bg-violet-800 disabled:opacity-60">
            {m.isPending ? <Loader2 className="size-4 animate-spin" /> : <FlaskConical className="size-4" />} Simulate post-intervention observations (demo)
          </button>
          {m.error && <p className="mt-2 text-xs text-red-600">{(m.error as Error).message}</p>}
        </section>
      ) : (
        <Link href={`/outcomes/${o.id}`} className="block rounded-2xl border border-emerald-200 bg-emerald-50 p-4 transition hover:border-emerald-300">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-900"><CheckCircle2 className="size-4" /> Outcome measured <DemoBadge label="Simulated" className="ml-auto" /></div>
          <p className="mt-1 text-xs text-emerald-900/80">
            Net NDVI gain vs. comparison area: <strong>{o.delta_vs_comparison != null ? `${o.delta_vs_comparison >= 0 ? "+" : ""}${o.delta_vs_comparison.toFixed(2)}` : "—"}</strong> · <ConfidencePill value={o.confidence} />
          </p>
          <p className="mt-2 text-xs font-medium text-emerald-800 underline">Open outcome report</p>
        </Link>
      )}
      {t.assessment && <p className="px-1 text-[11px] text-slate-400">Assessment zone: {fmtHa(t.assessment.affected_ha)} affected on {fmtDate(t.assessment.date)}.</p>}
    </>
  );
}
