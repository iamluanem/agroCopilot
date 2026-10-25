"use client";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronRight, ClipboardList, User } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { StatusBadge, STATUS_LABEL } from "@/components/ops/status";
import { DemoBadge } from "@/components/ui/demo-badge";
import { PageHeader } from "@/components/ui/page";
import { Segmented } from "@/components/ui/segmented";
import { ErrorState, Loading } from "@/components/ui/states";
import { api } from "@/lib/api";
import type { TaskStatus } from "@/lib/types";
import { cn, fmtDate } from "@/lib/utils";

type Filter = "abertas" | "todas" | TaskStatus;
const OPEN: TaskStatus[] = ["pendente", "atribuída", "em_andamento", "concluída"];

export default function TarefasPage() {
  const q = useQuery({ queryKey: ["tasks"], queryFn: () => api.tasks() });
  const [filter, setFilter] = useState<Filter>("abertas");
  const list = (q.data ?? []).filter((t) => filter === "todas" || (filter === "abertas" ? OPEN.includes(t.status) : t.status === filter));
  return (
    <div className="flex-1 overflow-y-auto">
      <PageHeader title="Tarefas" subtitle="Vistorias geradas a partir dos alertas. Execute no celular pelo detalhe da tarefa." right={<DemoBadge />} />
      <div className="p-6">
        <Segmented value={filter} onChange={setFilter} options={[
          { value: "abertas", label: "Abertas" }, { value: "verificada", label: STATUS_LABEL.verificada }, { value: "todas", label: "Todas" },
        ]} />
        {q.error ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data ? <Loading /> : list.length === 0 ? (
          <div className="mt-6 rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
            <ClipboardList className="mx-auto size-6 text-slate-400" />
            <p className="mt-2 text-sm font-medium text-slate-700">Nenhuma tarefa {filter === "abertas" ? "aberta" : "neste filtro"}</p>
            <p className="mt-1 text-xs text-slate-500">Crie uma vistoria pelo painel do talhão no Mapa ou pedindo ao Copiloto.</p>
            <div className="mt-4 flex justify-center gap-2 text-xs">
              <Link href="/mapa" className="rounded-lg border border-slate-200 px-3 py-1.5 font-medium hover:bg-slate-50">Abrir mapa</Link>
              <Link href="/copiloto" className="rounded-lg bg-brand-600 px-3 py-1.5 font-medium text-white hover:bg-brand-700">Perguntar ao copiloto</Link>
            </div>
          </div>
        ) : (
          <ul className="mt-4 grid gap-3 lg:grid-cols-2">
            {list.map((t) => (
              <li key={t.id}>
                <Link href={`/tarefas/${t.id}`} className="group flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:shadow-sm">
                  <span className={cn("mt-1 h-10 w-1 rounded-full", t.priority === "alta" ? "bg-red-500" : t.priority === "media" ? "bg-amber-400" : "bg-slate-300")} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-semibold text-slate-400">#{t.id} · {t.field_code}</span>
                      <StatusBadge s={t.status} />
                      {t.is_synthetic && <span className="text-[10px] text-violet-600">histórico demo</span>}
                    </div>
                    <div className="mt-1 truncate text-sm font-semibold text-slate-900">{t.title}</div>
                    <div className="mt-1 flex flex-wrap gap-x-3 text-[11px] text-slate-500">
                      <span className="inline-flex items-center gap-1"><User className="size-3" />{t.assignee ?? "sem responsável"}</span>
                      {t.due_date && <span className="inline-flex items-center gap-1"><CalendarDays className="size-3" />até {fmtDate(t.due_date)}</span>}
                      {t.verified_cause && <span>Causa: <span className="font-medium text-slate-700">{t.verified_cause}</span></span>}
                    </div>
                  </div>
                  <ChevronRight className="mt-3 size-4 text-slate-300 group-hover:text-slate-500" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
