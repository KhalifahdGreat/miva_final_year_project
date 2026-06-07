"use client";

import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const AXIS = { fontSize: 11, fill: "#94a3b8" };

export function AreaTrend({ data, color = "#10b981", height = 240 }: {
  data: { label: string; value: number }[]; color?: string; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.32} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
        <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={40} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: color, strokeOpacity: 0.2 }} />
        <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2.4} fill="url(#areaFill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function Bars({ data, color = "#2563eb", height = 240 }: {
  data: { label: string; value: number }[]; color?: string; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
        <XAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} minTickGap={20} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={40} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "#f1f5f9" }} />
        <Bar dataKey="value" fill={color} radius={[5, 5, 0, 0]} maxBarSize={42} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Donut({ data, height = 220 }: {
  data: { name: string; value: number; color: string }[]; height?: number;
}) {
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
      <div style={{ width: 200, height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={58} outerRadius={84} paddingAngle={2} stroke="none">
              {data.map((d, i) => <Cell key={i} fill={d.color} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div style={{ flex: 1, minWidth: 160 }}>
        {data.map((d) => (
          <div key={d.name} className="between" style={{ padding: "6px 0" }}>
            <span className="row" style={{ gap: 8 }}>
              <span style={{ width: 10, height: 10, borderRadius: 3, background: d.color }} />
              <span style={{ fontSize: 13 }}>{d.name}</span>
            </span>
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              {total ? Math.round((d.value / total) * 100) : 0}%
            </span>
          </div>
        ))}
        {data.length === 0 && <span className="muted">No data yet.</span>}
      </div>
    </div>
  );
}

const tooltipStyle = {
  borderRadius: 10,
  border: "1px solid #e6eaf0",
  boxShadow: "0 6px 18px rgba(15,23,42,0.08)",
  fontSize: 12,
};
