"use client";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FieldSeries } from "@/lib/types";
import { fmt } from "@/lib/utils";

const PREV_COLORS = ["#94a3b8", "#64748b"];

export function FieldSeriesChart({ series, das }: { series: FieldSeries; das?: number }) {
  const byDas = new Map<number, Record<string, number | null>>();
  series.seasons.forEach((s) => s.points.forEach((p) => {
    const row = byDas.get(p.das) ?? { das: p.das };
    row[s.season] = p.cloud_pct > 50 ? null : p.ndvi;
    byDas.set(p.das, row);
  }));
  const data = [...byDas.values()].sort((a, b) => (a.das as number) - (b.das as number));
  let prevIdx = 0;
  return (
    <ResponsiveContainer width="100%" height={190}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
        <CartesianGrid stroke="#eef2f6" vertical={false} />
        <XAxis dataKey="das" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} label={{ value: "DAS", position: "insideBottomRight", offset: -2, fontSize: 10, fill: "#94a3b8" }} />
        <YAxis domain={[0.2, 0.95]} tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} tickFormatter={(v) => fmt(v, 1)} />
        <Tooltip formatter={(v) => fmt(v as number, 3)} labelFormatter={(l) => `DAS ${l}`} contentStyle={{ fontSize: 11, borderRadius: 8 }} />
        <Legend wrapperStyle={{ fontSize: 10 }} iconType="plainline" />
        {das != null && <ReferenceLine x={das} stroke="#23824a" strokeDasharray="3 3" />}
        {series.seasons.map((s) => (
          <Line
            key={s.season}
            dataKey={s.season}
            name={`Safra ${s.season}`}
            connectNulls
            dot={false}
            isAnimationActive={false}
            stroke={s.is_current ? "#23824a" : PREV_COLORS[prevIdx++ % 2]}
            strokeWidth={s.is_current ? 2.4 : 1.4}
            strokeDasharray={s.is_current ? undefined : "4 3"}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
