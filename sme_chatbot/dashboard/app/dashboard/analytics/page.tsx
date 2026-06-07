"use client";

import { useState } from "react";
import useSWR from "swr";
import { useTenant } from "@/lib/tenant";
import {
  fetcher, LANG_COLOR, LANG_LABEL,
  type AnalyticsSummary, type Timeseries,
} from "@/lib/api";
import { PageHead, Stat, Skeleton, Empty } from "@/components/ui";
import { AreaTrend, Bars, Donut } from "@/components/charts";
import { NoTenant, WindowPicker } from "@/components/common";
import { bucketLabel, fmtNum } from "@/lib/format";

export default function AnalyticsPage() {
  const { tenantId } = useTenant();
  const [win, setWin] = useState("7d");
  const base = tenantId ? `/v1/tenants/${tenantId}` : null;

  const { data: sum, isLoading } = useSWR<AnalyticsSummary>(base ? `${base}/analytics/summary?window=${win}` : null, fetcher);
  const { data: msgs } = useSWR<Timeseries>(base ? `${base}/analytics/timeseries?metric=messages&window=${win}` : null, fetcher);
  const { data: esc } = useSWR<Timeseries>(base ? `${base}/analytics/timeseries?metric=escalations&window=${win}` : null, fetcher);

  if (!tenantId) return (<><PageHead title="Analytics" /><NoTenant /></>);

  const msgTrend = (msgs?.points ?? []).map((p) => ({ label: bucketLabel(p.t, win), value: p.v }));
  const escTrend = (esc?.points ?? []).map((p) => ({ label: bucketLabel(p.t, win), value: p.v }));
  const langData = Object.entries(sum?.by_language ?? {}).map(([k, v]) => ({
    name: LANG_LABEL[k] ?? k, value: v, color: LANG_COLOR[k] ?? "#94a3b8",
  }));

  return (
    <>
      <PageHead
        title="Analytics"
        lede="Volume, deflection, latency and language mix."
        actions={<WindowPicker value={win} onChange={setWin} />}
      />

      <div className="grid grid-4" style={{ marginBottom: 18 }}>
        {isLoading ? [0, 1, 2, 3].map((i) => <div key={i} className="stat"><Skeleton h={70} /></div>) : (
          <>
            <Stat label="Total messages" value={fmtNum(sum?.messages_total ?? 0)} icon="chat" />
            <Stat label="Deflection" value={`${Math.round((sum?.deflection_rate ?? 0) * 100)}%`} icon="shield" deltaDir="up" delta="auto-resolved" />
            <Stat label="Median latency" value={`${fmtNum(sum?.avg_latency_p50_ms ?? 0)} ms`} icon="clock" delta={`p95 ${fmtNum(sum?.avg_latency_p95_ms ?? 0)}ms · p99 ${fmtNum(sum?.avg_latency_p99_ms ?? 0)}ms`} />
            <Stat label="Escalations" value={fmtNum(sum?.escalations_total ?? 0)} icon="alert" />
          </>
        )}
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-head"><div><h3>Message volume</h3><div className="sub">Messages per hour</div></div></div>
        <div className="card-pad">
          {msgTrend.length ? <AreaTrend data={msgTrend} height={280} /> : <Empty icon="chart" title="No data for this window" />}
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1.4fr 1fr" }}>
        <div className="card">
          <div className="card-head"><div><h3>Escalations</h3><div className="sub">Handed to a human</div></div></div>
          <div className="card-pad">
            {escTrend.some((d) => d.value) ? <Bars data={escTrend} color="#d97706" height={260} /> : <Empty icon="check" title="No escalations" hint="The bot resolved everything in this window." />}
          </div>
        </div>
        <div className="card">
          <div className="card-head"><div><h3>Language mix</h3></div></div>
          <div className="card-pad"><Donut data={langData} height={240} /></div>
        </div>
      </div>
    </>
  );
}
