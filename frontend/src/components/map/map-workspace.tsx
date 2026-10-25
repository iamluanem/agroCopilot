"use client";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { LEVEL_COLOR } from "@/lib/colors";
import type { Basemap, FieldProps, Level, LayerMode } from "@/lib/types";
import { cn } from "@/lib/utils";
import { DemoBadge } from "../ui/demo-badge";
import { Segmented } from "../ui/segmented";
import { Slider } from "../ui/slider";
import { ErrorState, Loading } from "../ui/states";
import { DateTimeline } from "./date-timeline";
import { MapLegend } from "./map-legend";
import { SidePanel, type CellInfo } from "./side-panel";

const FarmMap = dynamic(() => import("./farm-map").then((m) => m.FarmMap), { ssr: false });

const LEVELS: Level[] = ["verde", "amarelo", "vermelho", "sem_dado"];

export function MapWorkspace() {
  const farms = useQuery({ queryKey: ["farms"], queryFn: api.farms });
  const farmId = farms.data?.[0]?.id;
  const farm = useQuery({ queryKey: ["farm", farmId], queryFn: () => api.farm(farmId!), enabled: !!farmId });
  const fields = useQuery({
    queryKey: ["fields", farmId],
    enabled: !!farmId,
    queryFn: async () => {
      const r = await fetch(api.fieldsUrl(farmId!));
      if (!r.ok) throw new Error("Falha ao carregar talhões");
      return (await r.json()) as GeoJSON.FeatureCollection<GeoJSON.Polygon, FieldProps>;
    },
  });

  const [seasonId, setSeasonId] = useState<number | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const [mode, setMode] = useState<LayerMode>("risco");
  const [basemap, setBasemap] = useState<Basemap>("satelite");
  const [opacity, setOpacity] = useState(0.8);
  const [hidden, setHidden] = useState<number[]>([]);
  const [selField, setSelField] = useState<number | null>(null);
  const [selCell, setSelCell] = useState<number | null>(null);

  useEffect(() => {
    if (farm.data && seasonId == null) setSeasonId(farm.data.seasons.find((s) => s.is_current)?.id ?? farm.data.seasons.at(-1)!.id);
  }, [farm.data, seasonId]);

  const dates = useQuery({ queryKey: ["dates", farmId, seasonId], queryFn: () => api.dates(farmId!, seasonId!), enabled: !!farmId && !!seasonId });
  useEffect(() => {
    if (dates.data?.length && !dates.data.some((d) => d.date === date)) setDate(dates.data.at(-1)!.date);
  }, [dates.data, date]);

  const risk = useQuery({
    queryKey: ["risk", farmId, date],
    queryFn: () => api.risk(farmId!, date!),
    enabled: !!farmId && !!date,
    placeholderData: keepPreviousData,
  });

  const cellIndex = useMemo(() => {
    const m = new Map<number, number>();
    risk.data?.cells.id.forEach((id, i) => m.set(id, i));
    return m;
  }, [risk.data]);

  const cell: CellInfo | undefined = useMemo(() => {
    if (selCell == null || !risk.data) return undefined;
    const i = cellIndex.get(selCell);
    if (i == null) return undefined;
    const c = risk.data.cells;
    return {
      id: selCell, level: LEVELS[c.level[i]], score: c.score[i], ndvi: c.ndvi[i], ndre: c.ndre[i], baseline: c.baseline[i],
      confidence: c.confidence[i] >= 0 ? risk.data.confidence_labels[c.confidence[i]] : null,
      area_ha: c.area[i],
    };
  }, [selCell, risk.data, cellIndex]);

  const visibleFieldIds = useMemo(() => (farm.data?.fields ?? []).map((f) => f.id).filter((id) => !hidden.includes(id)), [farm.data, hidden]);

  if (farms.error || farm.error || fields.error) return <ErrorState error={farms.error ?? farm.error ?? fields.error} onRetry={() => { farms.refetch(); farm.refetch(); fields.refetch(); }} />;
  if (farms.data && farms.data.length === 0) {
    return <div className="p-8 text-sm text-slate-600">Nenhuma fazenda cadastrada. Rode o seed de demonstração (veja o README).</div>;
  }
  if (!farm.data || !fields.data) return <Loading label="Carregando fazenda…" />;

  const fieldProps = fields.data.features.find((f) => f.properties.id === selField)?.properties;
  const fieldRisk = risk.data?.fields.find((f) => f.field_id === selField);

  return (
    <div className="flex min-h-0 flex-1">
      <section className="relative min-w-0 flex-1">
        <FarmMap
          farmId={farm.data.id}
          bbox={farm.data.bbox}
          fields={fields.data}
          risk={risk.data}
          mode={mode}
          basemap={basemap}
          opacity={opacity}
          visibleFieldIds={visibleFieldIds}
          selectedFieldId={selField}
          selectedCellId={selCell}
          onSelectCell={(c, f) => { setSelCell(c); setSelField(f); }}
          onSelectField={(f) => { setSelField(f); setSelCell(null); }}
          onClear={() => { setSelCell(null); setSelField(null); }}
        />

        {/* barra superior */}
        <div className="pointer-events-none absolute inset-x-3 top-3 flex flex-wrap items-start justify-between gap-2">
          <div className="pointer-events-auto flex flex-wrap items-center gap-2 rounded-xl bg-white/95 p-1.5 pl-3 shadow-lg ring-1 ring-slate-900/5 backdrop-blur">
            <select
              aria-label="Safra"
              value={seasonId ?? ""}
              onChange={(e) => { setSeasonId(Number(e.target.value)); setSelCell(null); }}
              className="rounded-md bg-transparent py-1 pr-1 text-xs font-semibold text-slate-800 focus:outline-none"
            >
              {farm.data.seasons.map((s) => <option key={s.id} value={s.id}>Safra {s.name}{s.is_current ? " (atual)" : ""}</option>)}
            </select>
            <span className="h-5 w-px bg-slate-200" />
            <Segmented value={mode} onChange={setMode} options={[{ value: "risco", label: "Risco" }, { value: "ndvi", label: "NDVI" }, { value: "ndre", label: "NDRE" }]} />
            <Segmented value={basemap} onChange={setBasemap} options={[{ value: "satelite", label: "Satélite" }, { value: "terreno", label: "Terreno" }]} />
            <label className="flex items-center gap-2 px-1 text-[11px] text-slate-500">
              Opacidade
              <Slider className="w-20" min={0} max={1} step={0.05} value={[opacity]} onValueChange={([v]) => setOpacity(v)} aria-label="Opacidade da camada" />
            </label>
            {risk.isFetching && <Loader2 className="mr-1 size-3.5 animate-spin text-slate-400" />}
          </div>
          <div className="pointer-events-auto flex items-center gap-1.5 rounded-xl bg-white/95 p-1.5 shadow-lg ring-1 ring-slate-900/5 backdrop-blur">
            {farm.data.fields.map((f) => {
              const on = !hidden.includes(f.id);
              const lvl = risk.data?.fields.find((x) => x.field_id === f.id)?.level;
              return (
                <button
                  key={f.id}
                  onClick={() => setHidden((h) => (on ? [...h, f.id] : h.filter((x) => x !== f.id)))}
                  className={cn("flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-semibold transition", on ? "bg-slate-100 text-slate-800" : "text-slate-400 line-through")}
                  title={on ? "Ocultar talhão" : "Mostrar talhão"}
                >
                  <span className="size-1.5 rounded-full" style={{ background: lvl ? LEVEL_COLOR[lvl] : "#cbd5e1" }} />
                  {f.code}
                </button>
              );
            })}
          </div>
        </div>

        <div className="pointer-events-none absolute bottom-8 left-3 flex flex-col gap-2">
          <DemoBadge className="pointer-events-auto self-start bg-white shadow" label="Dados de demonstração" />
          <div className="pointer-events-auto"><MapLegend mode={mode} /></div>
        </div>
        {dates.data && (
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
            <DateTimeline dates={dates.data} value={date} onChange={(d) => setDate(d)} />
          </div>
        )}
      </section>

      <SidePanel
        farm={farm.data}
        risk={risk.data}
        riskLoading={risk.isLoading}
        riskError={risk.error}
        fieldProps={fieldProps}
        fieldRisk={fieldRisk}
        cell={cell}
        onSelectField={(f) => { setSelField(f); setSelCell(null); }}
        onBack={() => { setSelField(null); setSelCell(null); }}
      />
    </div>
  );
}
