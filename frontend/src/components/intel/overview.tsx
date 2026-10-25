"use client";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronRight, CloudRain, MapPin } from "lucide-react";
import Link from "next/link";
import { Bar, BarChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { LEVEL_COLOR, LEVEL_LABEL } from "@/lib/colors";
import type { Assessment, Level } from "@/lib/types";
import { fmt, fmtBRL, fmtBRLk, fmtDate, fmtHa, fmtPct } from "@/lib/utils";
import { Badge } from "../ui/badge";
import { DemoBadge } from "../ui/demo-badge";
import { Card, Kpi, PageHeader } from "../ui/page";
import { ErrorState, Loading } from "../ui/states";
import { ConfidencePill } from "./assessment-cards";

const addDays = (iso: string, n: number) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
};

export function Overview() {
  const farms = useQuery({ queryKey: ["farms"], queryFn: api.farms });
  const farmId = farms.data?.[0]?.id;
  const farm = useQuery({ queryKey: ["farm", farmId], queryFn: () => api.farm(farmId!), enabled: !!farmId });
  const ref = farm.data?.reference_date;
  const risk = useQuery({ queryKey: ["risk", farmId, ref], queryFn: () => api.risk(farmId!, ref!), enabled: !!ref });
  const prio = useQuery({ queryKey: ["priorities", farmId], queryFn: () => api.priorities(farmId!), enabled: !!farmId });
  const tasks = useQuery({ queryKey: ["tasks-summary", farmId], queryFn: () => api.tasksSummary(farmId!), enabled: !!farmId });
  const wx = useQuery({ queryKey: ["weather", farmId, ref], queryFn: () => api.weather(farmId!, addDays(ref!, -45), ref!), enabled: !!ref });

  const err = farms.error ?? farm.error ?? risk.error ?? prio.error;
  if (err) return <ErrorState error={err} onRetry={() => { farm.refetch(); risk.refetch(); prio.refetch(); }} />;
  if (farms.data?.length === 0) return <div className="p-8 text-sm text-slate-600">Nenhuma fazenda cadastrada. Rode o seed de demonstração (veja o README).</div>;
  if (!farm.data || !risk.data) return <Loading label="Carregando visão geral…" />;

  const f = farm.data;
  const sm = risk.data.summary;
  const season = f.seasons.find((x) => x.id === risk.data.season_id);
  const top = prio.data?.items.find((i) => i.has_zone);

  return (
    <div className="flex-1 overflow-y-auto">
      <PageHeader
        title="Visão Geral"
        subtitle={<span className="inline-flex items-center gap-1"><MapPin className="size-3" />{f.name} · {f.municipality}-{f.state} · {f.crop} · Safra {season?.name} · referência {fmtDate(ref!)} (DAS {risk.data.das})</span>}
        right={<DemoBadge />}
      />
      <div className="space-y-4 p-6">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Kpi label="Área monitorada" value={fmtHa(sm.total_ha, 0)} hint={`${f.fields.length} talhões`} />
          <Kpi label="Saudável" value={fmtPct(sm.pct_by_level.verde)} hint={fmtHa(sm.area_by_level.verde, 0)} accent={LEVEL_COLOR.verde} />
          <Kpi label="Em atenção" value={fmtPct(sm.pct_by_level.amarelo)} hint={fmtHa(sm.area_by_level.amarelo)} accent="#b38600" />
          <Kpi label="Crítica" value={fmtPct(sm.pct_by_level.vermelho)} hint={fmtHa(sm.area_by_level.vermelho)} accent={LEVEL_COLOR.vermelho} />
          <Kpi
            label="Exposição estimada"
            value={prio.data ? <span className="text-xl">{fmtBRLk(prio.data.totals.exposure_min)} – {fmt(prio.data.totals.exposure_max / 1000, 1)} mil</span> : "…"}
            hint={<>Estimativa, não perda confirmada · {tasks.data ? `${tasks.data.open} tarefa(s) aberta(s)` : ""}</>}
          />
        </div>

        {top && (
          <Link href={`/talhoes/${top.field_id}`} className="group flex flex-wrap items-center gap-4 rounded-xl border border-red-200 bg-gradient-to-r from-red-50 to-white p-4 transition hover:border-red-300">
            <div className="grid size-10 place-items-center rounded-full bg-red-600 text-sm font-bold text-white">#1</div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-slate-900">{top.name}: {fmtHa(top.red_ha)} críticos — prioridade da semana</div>
              <div className="text-xs text-slate-600">
                Hipótese principal: <span className="font-medium">{top.hypotheses[0]?.cause}</span> (confiança {top.hypotheses[0]?.confidence}) ·
                exposição {fmtBRL(top.economics?.exposure_min)} – {fmtBRL(top.economics?.exposure_max)} · {top.next_step?.split(",")[0]}.
              </div>
            </div>
            <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700">Abrir talhão <ArrowRight className="size-3.5 transition group-hover:translate-x-0.5" /></span>
          </Link>
        )}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Card title="Prioridades operacionais" right={<span className="text-[11px] text-slate-400" title={prio.data?.priority_formula}>exposição × urgência × confiança</span>}>
            {!prio.data ? <Loading label="Calculando prioridades…" /> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-xs">
                  <thead className="text-[10px] uppercase tracking-wide text-slate-400">
                    <tr className="border-b border-slate-100">
                      <th className="py-2 text-left font-medium">#</th><th className="text-left font-medium">Talhão</th>
                      <th className="text-left font-medium">Distribuição de risco</th><th className="text-left font-medium">Hipótese principal</th>
                      <th className="text-right font-medium">Exposição estimada</th><th />
                    </tr>
                  </thead>
                  <tbody>{prio.data.items.map((it) => <PriorityRow key={it.field_id} it={it} risk={risk.data.fields.find((x) => x.field_id === it.field_id)?.area_by_level} />)}</tbody>
                </table>
              </div>
            )}
          </Card>
          <Card title="Chuva — últimos 45 dias" right={<CloudRain className="size-3.5 text-slate-400" />}>
            {wx.data ? <RainMini data={wx.data} dry={top?.weather} /> : <Loading />}
            {top?.weather && (
              <p className="mt-2 text-[11px] leading-snug text-slate-500">
                {top.weather.max_dry_days} dias consecutivos sem chuva ({fmtDate(top.weather.dry_start!, { day: "2-digit", month: "2-digit" })}–{fmtDate(top.weather.dry_end!, { day: "2-digit", month: "2-digit" })}). Chuva nos últimos 21 dias: {fmt(top.weather.rain_21d_mm, 0)} mm.
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function PriorityRow({ it, risk }: { it: Assessment; risk?: Record<Level, number> }) {
  return (
    <tr className="group border-b border-slate-50 last:border-0 hover:bg-slate-50/70">
      <td className="py-3 pr-2 font-semibold text-slate-400">{it.rank}</td>
      <td className="pr-3">
        <Link href={`/talhoes/${it.field_id}`} className="font-semibold text-slate-900 hover:underline">{it.name}</Link>
        <div className="mt-0.5"><Badge tone={it.level}>{LEVEL_LABEL[it.level]}</Badge></div>
      </td>
      <td className="w-48 pr-4">
        {risk && (
          <div className="flex h-2 gap-px overflow-hidden rounded-full bg-slate-100" title={`Crítico ${fmtHa(risk.vermelho)} · Atenção ${fmtHa(risk.amarelo)}`}>
            {(["vermelho", "amarelo", "verde"] as Level[]).map((l) => <div key={l} style={{ width: `${(risk[l] / it.area_ha) * 100}%`, background: LEVEL_COLOR[l] }} />)}
          </div>
        )}
        <div className="mt-1 text-[11px] text-slate-500">{fmtHa(it.red_ha)} crít. · {fmtHa(it.yellow_ha)} atenção</div>
      </td>
      <td className="pr-3">
        {it.has_zone ? (
          <div className="space-y-1"><div className="text-slate-800">{it.hypotheses[0]?.cause}</div><ConfidencePill value={it.hypotheses[0]!.confidence} label="" /></div>
        ) : <span className="text-slate-400">Sem zona relevante</span>}
      </td>
      <td className="text-right font-semibold tabular-nums text-slate-800">
        {it.economics ? <>{fmtBRL(it.economics.exposure_min)}<span className="text-slate-400"> – </span>{fmtBRL(it.economics.exposure_max)}</> : <span className="font-normal text-slate-400">—</span>}
      </td>
      <td className="pl-2"><Link href={`/talhoes/${it.field_id}`} aria-label={`Abrir ${it.name}`}><ChevronRight className="size-4 text-slate-300 group-hover:text-slate-500" /></Link></td>
    </tr>
  );
}

function RainMini({ data, dry }: { data: { date: string; rain_mm: number }[]; dry?: Assessment["weather"] }) {
  return (
    <ResponsiveContainer width="100%" height={140}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -24 }} barCategoryGap={1}>
        <XAxis dataKey="date" tickFormatter={(d) => fmtDate(d, { day: "2-digit", month: "2-digit" })} tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} minTickGap={28} />
        <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
        {dry?.dry_start && dry.dry_end && <ReferenceArea x1={dry.dry_start} x2={dry.dry_end} fill="#f59e0b" fillOpacity={0.14} />}
        <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} cursor={{ fill: "rgba(15,23,42,0.04)" }} labelFormatter={(l) => fmtDate(String(l))} formatter={(v) => [`${fmt(v as number, 1)} mm`, "Chuva"]} />
        <Bar dataKey="rain_mm" fill="#3b82f6" radius={[2, 2, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
