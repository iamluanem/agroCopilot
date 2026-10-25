"use client";
import maplibregl from "maplibre-gl";
import type { ExpressionSpecification, GeoJSONSource, MapLayerMouseEvent, MapMouseEvent, MapSourceDataEvent } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { INDEX_RAMP, LEVEL_COLOR, LEVEL_LABEL } from "@/lib/colors";
import type { Basemap, FieldProps, Level, LayerMode, RiskSnapshot } from "@/lib/types";
import { fmt } from "@/lib/utils";

const TRANSPARENT = "rgba(0,0,0,0)";
const LEVEL_KEYS: Level[] = ["verde", "amarelo", "vermelho", "sem_dado"];

type FieldsFC = GeoJSON.FeatureCollection<GeoJSON.Polygon, FieldProps>;

interface Props {
  farmId: number;
  bbox: [number, number, number, number];
  fields: FieldsFC;
  risk?: RiskSnapshot;
  mode: LayerMode;
  basemap: Basemap;
  opacity: number;
  visibleFieldIds: number[];
  selectedFieldId: number | null;
  selectedCellId: number | null;
  onSelectCell: (cellId: number, fieldId: number) => void;
  onSelectField: (fieldId: number) => void;
  onClear: () => void;
}

const levelExpr = ["coalesce", ["feature-state", "level"], -1] as ExpressionSpecification;

function fillColor(mode: LayerMode): ExpressionSpecification {
  if (mode === "risco") {
    return ["match", levelExpr, 0, LEVEL_COLOR.verde, 1, LEVEL_COLOR.amarelo, 2, LEVEL_COLOR.vermelho, 3, LEVEL_COLOR.sem_dado, TRANSPARENT];
  }
  const ramp = INDEX_RAMP[mode].flatMap(([v, c]) => [v, c]);
  return [
    "case",
    ["==", ["typeof", ["feature-state", mode]], "number"],
    ["interpolate", ["linear"], ["feature-state", mode], ...ramp] as ExpressionSpecification,
    LEVEL_COLOR.sem_dado,
  ];
}

function fillOpacity(mode: LayerMode, o: number): ExpressionSpecification | number {
  if (mode !== "risco") return o * 0.9;
  return ["*", o, ["match", levelExpr, 0, 0.42, 1, 0.85, 2, 0.92, 3, 0.55, 0]];
}

function fieldBounds(f: GeoJSON.Feature<GeoJSON.Polygon>): maplibregl.LngLatBoundsLike {
  const b = new maplibregl.LngLatBounds();
  f.geometry.coordinates[0].forEach((c) => b.extend(c as [number, number]));
  return b;
}

export function FarmMap(p: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markers = useRef<Map<number, { marker: maplibregl.Marker; dot: HTMLSpanElement }>>(new Map());
  const cb = useRef(p);
  cb.current = p;
  const [cellsReady, setCellsReady] = useState(false);
  const cellsReadyRef = useRef(false);

  // inicialização
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      bounds: p.bbox,
      fitBoundsOptions: { padding: { top: 90, bottom: 120, left: 40, right: 40 } },
      attributionControl: { compact: true },
      maxZoom: 18,
      style: {
        version: 8,
        sources: {
          satelite: {
            type: "raster", tileSize: 256, maxzoom: 18,
            tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
            attribution: "Imagem base: Esri, Maxar, Earthstar Geographics",
          },
          terreno: {
            type: "raster", tileSize: 256, maxzoom: 18,
            tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"],
            attribution: "Esri, HERE, Garmin, OpenStreetMap",
          },
        },
        layers: [
          { id: "satelite", type: "raster", source: "satelite" },
          { id: "terreno", type: "raster", source: "terreno", layout: { visibility: "none" } },
        ],
      },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "bottom-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    mapRef.current = map;

    map.on("load", () => {
      map.addSource("fields", { type: "geojson", data: cb.current.fields });
      map.addSource("cells", { type: "geojson", data: api.cellsUrl(p.farmId) });

      map.addLayer({ id: "cells-fill", type: "fill", source: "cells", paint: { "fill-color": fillColor("risco"), "fill-opacity": fillOpacity("risco", 0.8) } });
      map.addLayer({
        id: "cells-grid", type: "line", source: "cells", minzoom: 15.5,
        paint: { "line-color": "#ffffff", "line-opacity": 0.18, "line-width": 0.5 },
      });
      map.addLayer({ id: "fields-casing", type: "line", source: "fields", paint: { "line-color": "#0a1120", "line-width": 4, "line-opacity": 0.45 } });
      map.addLayer({ id: "fields-line", type: "line", source: "fields", paint: { "line-color": "#ffffff", "line-width": 1.8 } });
      map.addLayer({
        id: "field-selected", type: "line", source: "fields", filter: ["==", ["id"], -1],
        paint: { "line-color": "#5eead4", "line-width": 3.5 },
      });
      map.addLayer({
        id: "cell-selected", type: "line", source: "cells", filter: ["==", ["id"], -1],
        paint: { "line-color": "#ffffff", "line-width": 2.5 },
      });

      cb.current.fields.features.forEach((f) => {
        const el = document.createElement("button");
        el.className = "flex items-center gap-1.5 rounded-full bg-navy-950/85 px-2.5 py-1 text-[11px] font-semibold text-white shadow-lg ring-1 ring-white/20 backdrop-blur hover:bg-navy-800";
        const dot = document.createElement("span");
        dot.className = "size-2 rounded-full";
        dot.style.background = LEVEL_COLOR.sem_dado;
        el.append(dot, document.createTextNode(f.properties.code));
        el.addEventListener("click", (e) => { e.stopPropagation(); cb.current.onSelectField(f.properties.id); });
        const marker = new maplibregl.Marker({ element: el }).setLngLat(f.properties.label_point).addTo(map);
        markers.current.set(f.properties.id, { marker, dot });
      });
    });

    map.on("sourcedata", (e: MapSourceDataEvent) => {
      if (e.sourceId === "cells" && e.isSourceLoaded && !cellsReadyRef.current) {
        cellsReadyRef.current = true;
        setCellsReady(true);
      }
    });

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, maxWidth: "240px" });
    map.on("mousemove", "cells-fill", (e: MapLayerMouseEvent) => {
      const f = e.features?.[0];
      if (!f) return;
      map.getCanvas().style.cursor = "pointer";
      const st = map.getFeatureState({ source: "cells", id: f.id! });
      const field = cb.current.fields.features.find((x) => x.properties.id === f.properties.f);
      const lvl = LEVEL_KEYS[st.level as number] ?? "sem_dado";
      popup.setLngLat(e.lngLat).setHTML(
        `<div style="padding:8px 10px;font:12px var(--font-geist-sans)">
          <div style="display:flex;align-items:center;gap:6px;font-weight:600">
            <span style="width:8px;height:8px;border-radius:9px;background:${LEVEL_COLOR[lvl]}"></span>
            ${field?.properties.name ?? ""} · ${LEVEL_LABEL[lvl]}
          </div>
          <div style="color:#475569;margin-top:2px">NDVI ${fmt(st.ndvi as number, 2)} · histórico ${fmt(st.baseline as number, 2)}</div>
        </div>`,
      ).addTo(map);
    });
    map.on("mouseleave", "cells-fill", () => {
      map.getCanvas().style.cursor = "";
      popup.remove();
    });
    map.on("click", (e: MapMouseEvent) => {
      const f = map.queryRenderedFeatures(e.point, { layers: ["cells-fill"] })[0];
      if (f && f.id != null) cb.current.onSelectCell(Number(f.id), Number(f.properties.f));
      else cb.current.onClear();
    });

    const markerMap = markers.current;
    return () => {
      markerMap.forEach(({ marker }) => marker.remove());
      markerMap.clear();
      map.remove();
      mapRef.current = null;
      cellsReadyRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.farmId]);

  // estado de risco por célula
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !cellsReady || !p.risk) return;
    const c = p.risk.cells;
    for (let i = 0; i < c.id.length; i++) {
      map.setFeatureState(
        { source: "cells", id: c.id[i] },
        { level: c.level[i], ndvi: c.ndvi[i], ndre: c.ndre[i], baseline: c.baseline[i], score: c.score[i] },
      );
    }
    p.risk.fields.forEach((f) => {
      const m = markers.current.get(f.field_id);
      if (m) m.dot.style.background = LEVEL_COLOR[f.level];
    });
  }, [p.risk, cellsReady]);

  // modo de camada + opacidade
  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("cells-fill")) return;
    map.setPaintProperty("cells-fill", "fill-color", fillColor(p.mode));
    map.setPaintProperty("cells-fill", "fill-opacity", fillOpacity(p.mode, p.opacity));
  }, [p.mode, p.opacity, cellsReady]);

  // mapa base
  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("satelite")) return;
    map.setLayoutProperty("satelite", "visibility", p.basemap === "satelite" ? "visible" : "none");
    map.setLayoutProperty("terreno", "visibility", p.basemap === "terreno" ? "visible" : "none");
  }, [p.basemap, cellsReady]);

  // filtro de talhões
  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("cells-fill")) return;
    const filter: ExpressionSpecification = ["in", ["get", "f"], ["literal", p.visibleFieldIds]];
    map.setFilter("cells-fill", filter);
    map.setFilter("cells-grid", filter);
    markers.current.forEach(({ marker }, id) => {
      marker.getElement().style.opacity = p.visibleFieldIds.includes(id) ? "1" : "0.35";
    });
  }, [p.visibleFieldIds, cellsReady]);

  // seleção
  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("field-selected")) return;
    map.setFilter("field-selected", ["==", ["id"], p.selectedFieldId ?? -1]);
    map.setFilter("cell-selected", ["==", ["id"], p.selectedCellId ?? -1]);
  }, [p.selectedFieldId, p.selectedCellId, cellsReady]);

  // enquadrar talhão selecionado (quando não veio de clique numa célula)
  const lastFlown = useRef<number | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (p.selectedFieldId == null) {
      if (lastFlown.current != null) map.fitBounds(p.bbox, { padding: { top: 90, bottom: 120, left: 40, right: 40 }, duration: 900 });
      lastFlown.current = null;
      return;
    }
    if (p.selectedCellId != null || lastFlown.current === p.selectedFieldId) return;
    const f = p.fields.features.find((x) => x.properties.id === p.selectedFieldId);
    if (f) map.fitBounds(fieldBounds(f), { padding: { top: 100, bottom: 130, left: 60, right: 60 }, duration: 900 });
    lastFlown.current = p.selectedFieldId;
  }, [p.selectedFieldId, p.selectedCellId, p.fields, p.bbox]);

  useEffect(() => {
    const map = mapRef.current;
    const src = map?.getSource("fields") as GeoJSONSource | undefined;
    src?.setData(p.fields);
  }, [p.fields]);

  return (
    <div className="absolute inset-0">
      <div ref={container} className="h-full w-full" />
      {!cellsReady && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <div className="rounded-lg bg-white/90 px-3 py-2 text-xs text-slate-600 shadow">Carregando células de manejo…</div>
        </div>
      )}
    </div>
  );
}
