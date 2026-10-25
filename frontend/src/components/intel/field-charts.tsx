"use client";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LEVEL_COLOR } from "@/lib/colors";
import type { FieldDetail } from "@/lib/types";
import { fmt, fmtDate } from "@/lib/utils";

const AXIS = { fontSize: 10, fill: "#64748b" };
const TT = { contentStyle: { fontSize: 11, borderRadius: 8, borderColor: "#e2e8f0" }, cursor: { fill: "rgba(15,23,42,0.04)" } };
const dm = (iso: string) => fmtDate(iso, { day: "2-digit", month: "2-digit" });

export function NdviVsBaselineChart({ d }: { d: FieldDetail }) {
  const data = d.evolution.map((e) => ({ ...e, ndvi: e.cloud_pct > 50 ? null : e.ndvi }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
        <CartesianGrid stroke="#eef2f6" vertical={false} />
        <XAxis dataKey="date" tickFormatter={dm} tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis domain={[0.2, 0.95]} tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v) => fmt(v, 1)} />
        <Tooltip {...TT} labelFormatter={(l) => fmtDate(String(l))} formatter={(v, n) => [fmt(v as number, 3), n]} />
        <Legend wrapperStyle={{ fontSize: 11 }} iconType="plainline" />
        <Line dataKey="baseline" name="Histórico (mesmo DAS)" stroke="#94a3b8" strokeWidth={2} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
        <Line dataKey="ndvi" name={`Safra ${d.season.name}`} stroke="#23824a" strokeWidth={2} dot={{ r: 2.5, strokeWidth: 0, fill: "#23824a" }} connectNulls isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function RiskEvolutionChart({ d }: { d: FieldDetail }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={d.evolution} margin={{ top: 8, right: 12, bottom: 0, left: -16 }} barCategoryGap={3}>
        <CartesianGrid stroke="#eef2f6" vertical={false} />
        <XAxis dataKey="date" tickFormatter={dm} tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} unit=" ha" width={56} />
        <Tooltip {...TT} labelFormatter={(l) => fmtDate(String(l))} formatter={(v, n) => [`${fmt(v as number, 1)} ha`, n]} />
        <Legend wrapperStyle={{ fontSize: 11 }} iconType="square" />
        <Bar dataKey="vermelho" name="Crítico" stackId="a" fill={LEVEL_COLOR.vermelho} stroke="#fff" strokeWidth={1} isAnimationActive={false} />
        <Bar dataKey="amarelo" name="Atenção" stackId="a" fill={LEVEL_COLOR.amarelo} stroke="#fff" strokeWidth={1} isAnimationActive={false} />
        <Bar dataKey="sem_dado" name="Sem dado (nuvem)" stackId="a" fill={LEVEL_COLOR.sem_dado} stroke="#fff" strokeWidth={1} radius={[3, 3, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function RainChart({ d }: { d: FieldDetail }) {
  const w = d.assessment.weather;
  return (
    <ResponsiveContainer width="100%" height={150}>
      <BarChart data={d.weather} margin={{ top: 8, right: 12, bottom: 0, left: -16 }} barCategoryGap={1}>
        <CartesianGrid stroke="#eef2f6" vertical={false} />
        <XAxis dataKey="date" tickFormatter={dm} tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} unit=" mm" width={56} />
        {w?.dry_start && w.dry_end && (
          <ReferenceArea x1={w.dry_start} x2={w.dry_end} fill="#f59e0b" fillOpacity={0.12}
            label={{ value: `${w.max_dry_days} dias sem chuva`, position: "insideTop", fontSize: 10, fill: "#b45309" }} />
        )}
        <Tooltip {...TT} labelFormatter={(l) => fmtDate(String(l))} formatter={(v) => [`${fmt(v as number, 1)} mm`, "Chuva"]} />
        <Bar dataKey="rain_mm" name="Chuva diária" fill="#3b82f6" radius={[2, 2, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
