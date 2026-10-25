"use client";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { LEVEL_COLOR, LEVEL_LABEL } from "@/lib/colors";
import { fmt, fmtBRL, fmtDate, fmtHa } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { DemoBadge } from "@/components/ui/demo-badge";
import { PageHeader } from "@/components/ui/page";
import { ErrorState, Loading } from "@/components/ui/states";

export default function TalhoesPage() {
  const farms = useQuery({ queryKey: ["farms"], queryFn: api.farms });
  const farmId = farms.data?.[0]?.id;
  const p = useQuery({ queryKey: ["priorities", farmId], queryFn: () => api.priorities(farmId!), enabled: !!farmId });
  const err = farms.error ?? p.error;
  return (
    <div className="flex-1 overflow-y-auto">
      <PageHeader title="Talhões" subtitle={p.data ? `Ordenados por prioridade em ${fmtDate(p.data.date)}` : undefined} right={<DemoBadge />} />
      {err ? <ErrorState error={err} onRetry={() => p.refetch()} /> : !p.data ? <Loading label="Calculando prioridades…" /> : (
        <div className="grid gap-3 p-6 md:grid-cols-2 xl:grid-cols-3">
          {p.data.items.map((it) => (
            <Link key={it.field_id} href={`/talhoes/${it.field_id}`} className="group rounded-xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:shadow-sm">
              <div className="flex items-center gap-2">
                <span className="h-8 w-1 rounded-full" style={{ background: LEVEL_COLOR[it.level] }} />
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-sm font-semibold">{it.name}<Badge tone={it.level}>{LEVEL_LABEL[it.level]}</Badge></div>
                  <div className="text-[11px] text-slate-500">{fmtHa(it.area_ha)} · NDVI {fmt(it.ndvi_mean, 2)} (hist. {fmt(it.ndvi_baseline, 2)})</div>
                </div>
                <ChevronRight className="size-4 text-slate-300 group-hover:text-slate-500" />
              </div>
              <div className="mt-3 border-t border-slate-100 pt-3 text-xs">
                {it.has_zone ? (
                  <>
                    <div className="text-slate-500">Hipótese principal</div>
                    <div className="font-medium text-slate-800">{it.hypotheses[0]?.cause} <span className="font-normal text-slate-400">· confiança {it.hypotheses[0]?.confidence}</span></div>
                    <div className="mt-1.5 text-slate-500">Exposição estimada <span className="font-semibold text-slate-800">{fmtBRL(it.economics!.exposure_min)} – {fmtBRL(it.economics!.exposure_max)}</span></div>
                  </>
                ) : <div className="text-slate-500">{it.summary}</div>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
