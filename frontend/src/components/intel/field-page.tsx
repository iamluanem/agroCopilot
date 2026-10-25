"use client";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Droplets, Layers, Map as MapIcon } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { LEVEL_COLOR, LEVEL_LABEL } from "@/lib/colors";
import { fmt, fmtDate, fmtHa } from "@/lib/utils";
import { Badge } from "../ui/badge";
import { DemoBadge } from "../ui/demo-badge";
import { Card, Kpi, PageHeader } from "../ui/page";
import { ErrorState, Loading } from "../ui/states";
import { AssessmentPanel } from "./assessment-cards";
import { NdviVsBaselineChart, RainChart, RiskEvolutionChart } from "./field-charts";
import { MemoryTimeline } from "./memory-timeline";

export function FieldPage({ fieldId }: { fieldId: number }) {
  const q = useQuery({ queryKey: ["field", fieldId], queryFn: () => api.field(fieldId) });
  if (q.isLoading) return <Loading label="Carregando talhão…" />;
  if (q.error || !q.data) return <ErrorState error={q.error ?? "Talhão não encontrado"} onRetry={() => q.refetch()} />;
  const d = q.data;
  const a = d.assessment;
  const delta = a.ndvi_mean != null && a.ndvi_baseline != null ? a.ndvi_mean - a.ndvi_baseline : null;

  return (
    <div className="flex-1 overflow-y-auto">
      <PageHeader
        back={<Link href="/talhoes" className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800"><ArrowLeft className="size-3.5" /> Talhões</Link>}
        title={<span className="flex items-center gap-2">{d.name}<Badge tone={a.level}>{LEVEL_LABEL[a.level]}</Badge></span>}
        subtitle={<>Safra {d.season.name} · semeadura {fmtDate(d.season.sowing_date)} · referência {fmtDate(d.date)} (DAS {a.das}, {a.stage})</>}
        right={<>
          <DemoBadge />
          <Link href={`/mapa?talhao=${d.field_id}`} className="inline-flex items-center gap-1.5 rounded-lg bg-navy-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-navy-800">
            <MapIcon className="size-3.5" /> Ver no mapa
          </Link>
        </>}
      />
      <div className="grid gap-4 p-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0 space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Kpi label="Área do talhão" value={fmtHa(d.area_ha)} hint={d.irrigation} />
            <Kpi label="Área crítica" value={fmtHa(a.red_ha)} accent={a.red_ha > 1 ? LEVEL_COLOR.vermelho : undefined} />
            <Kpi label="Em atenção" value={fmtHa(a.yellow_ha)} accent={a.yellow_ha > 1 ? "#b38600" : undefined} />
            <Kpi label="NDVI médio" value={fmt(a.ndvi_mean, 2)} hint={delta != null ? `${delta >= 0 ? "+" : ""}${fmt(delta, 2)} vs. histórico` : undefined} />
          </div>
          <Card title="NDVI do talhão vs. histórico no mesmo estádio"><NdviVsBaselineChart d={d} /></Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Evolução da área em anomalia"><RiskEvolutionChart d={d} /></Card>
            <Card title="Chuva diária (sintética)"><RainChart d={d} /></Card>
          </div>
          <Card title="Memória agronômica do talhão"><MemoryTimeline events={d.memory} /></Card>
        </div>
        <div className="space-y-4">
          <Card title={`Avaliação em ${fmtDate(a.date)}`}><AssessmentPanel a={a} /></Card>
          <Card title="Contexto do talhão">
            <dl className="space-y-2 text-xs">
              <div className="flex gap-2"><Layers className="mt-0.5 size-3.5 text-slate-400" /><dt className="w-16 text-slate-500">Solo</dt><dd className="flex-1">{d.soil_texture ?? "—"}</dd></div>
              <div className="flex gap-2"><Droplets className="mt-0.5 size-3.5 text-slate-400" /><dt className="w-16 text-slate-500">Manejo</dt><dd className="flex-1 capitalize">{d.irrigation}</dd></div>
            </dl>
            {d.harvests.length > 0 && (
              <table className="mt-3 w-full text-xs">
                <thead className="text-[10px] uppercase tracking-wide text-slate-400"><tr><th className="py-1 text-left font-medium">Safra</th><th className="text-right font-medium">Esperado</th><th className="text-right font-medium">Realizado (fazenda)</th></tr></thead>
                <tbody>{d.harvests.map((h) => (
                  <tr key={h.season} className="border-t border-slate-100"><td className="py-1">{h.season}</td><td className="text-right">{fmt(h.expected, 0)} sc/ha</td><td className="text-right font-medium">{fmt(h.realized, 1)} sc/ha</td></tr>
                ))}</tbody>
              </table>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
