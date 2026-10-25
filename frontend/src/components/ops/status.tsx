import { Check } from "lucide-react";
import type { TaskStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export const STATUS_LABEL: Record<TaskStatus, string> = {
  pendente: "Pendente",
  "atribuída": "Atribuída",
  em_andamento: "Em andamento",
  "concluída": "Vistoria concluída",
  verificada: "Verificada",
};

const STATUS_TONE: Record<TaskStatus, string> = {
  pendente: "bg-slate-100 text-slate-700 ring-slate-200",
  "atribuída": "bg-sky-50 text-sky-700 ring-sky-200",
  em_andamento: "bg-amber-50 text-amber-800 ring-amber-200",
  "concluída": "bg-violet-50 text-violet-700 ring-violet-200",
  verificada: "bg-emerald-50 text-emerald-700 ring-emerald-200",
};

export function StatusBadge({ s }: { s: TaskStatus }) {
  return <span className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset", STATUS_TONE[s])}>{STATUS_LABEL[s]}</span>;
}

export function StatusStepper({ flow, current }: { flow: TaskStatus[]; current: TaskStatus }) {
  const idx = flow.indexOf(current);
  return (
    <ol className="flex items-center gap-1">
      {flow.map((s, i) => (
        <li key={s} className="flex min-w-0 flex-1 items-center gap-1">
          <span className={cn("grid size-5 shrink-0 place-items-center rounded-full text-[10px] font-bold",
            i < idx ? "bg-brand-600 text-white" : i === idx ? "bg-navy-900 text-white ring-4 ring-navy-900/10" : "bg-slate-200 text-slate-500")}>
            {i < idx ? <Check className="size-3" /> : i + 1}
          </span>
          <span className={cn("hidden truncate text-[11px] sm:block", i === idx ? "font-semibold text-slate-900" : "text-slate-500")}>{STATUS_LABEL[s]}</span>
          {i < flow.length - 1 && <span className={cn("h-px flex-1", i < idx ? "bg-brand-600" : "bg-slate-200")} />}
        </li>
      ))}
    </ol>
  );
}
