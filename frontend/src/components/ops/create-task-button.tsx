"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ClipboardPlus, Loader2 } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Assessment } from "@/lib/types";

const addDays = (iso: string, n: number) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
};

export function CreateTaskButton({ a }: { a: Assessment }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => api.createTask({
      field_id: a.field_id, field_code: a.code, assessment_id: a.assessment_id,
      title: `Inspection — anomalous zone in ${a.name} (${Math.round(a.red_ha)} ha critical)`,
      priority: a.red_ha >= 10 ? "high" : "medium", assignee: "Carlos Menezes (field technician)",
      due_date: addDays(a.date, 2),
      instructions: `Main hypothesis: ${a.hypotheses[0]?.cause} (${a.hypotheses[0]?.confidence} confidence). Check: ${a.hypotheses.slice(0, 2).flatMap((h) => h.missing).join("; ")}.`,
    }, "map"),
    onSuccess: () => ["tasks", "tasks-summary", "field"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })),
  });
  if (m.data) {
    return (
      <Link href={`/tasks/${m.data.id}`} className="flex items-center justify-center gap-1.5 rounded-lg bg-emerald-50 py-2.5 text-xs font-semibold text-emerald-800 ring-1 ring-emerald-200 hover:bg-emerald-100">
        <CheckCircle2 className="size-3.5" /> Inspection #{m.data.id} created — open task
      </Link>
    );
  }
  return (
    <div>
      <button onClick={() => m.mutate()} disabled={m.isPending} className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-brand-600 py-2.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
        {m.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <ClipboardPlus className="size-3.5" />} Create inspection for this zone
      </button>
      {m.error && <p className="mt-1 text-[11px] text-red-600">{(m.error as Error).message}</p>}
    </div>
  );
}
