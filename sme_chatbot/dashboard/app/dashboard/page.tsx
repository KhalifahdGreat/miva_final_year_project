"use client";

import Link from "next/link";
import useSWR from "swr";
import { useTenant } from "@/lib/tenant";
import {
  fetcher, LANG_COLOR, LANG_LABEL,
  type AnalyticsSummary, type Conversation, type DocItem, type Timeseries,
} from "@/lib/api";
import { PageHead, Stat, Badge, Skeleton, Empty } from "@/components/ui";
import { AreaTrend, Donut } from "@/components/charts";
import { NoTenant } from "@/components/common";
import { bucketLabel, fmtNum, timeAgo } from "@/lib/format";
import { Icon } from "@/components/icons";

export default function OverviewPage() {
  const { tenantId, active } = useTenant();
  const base = tenantId ? `/v1/tenants/${tenantId}` : null;

  const { data: sum, isLoading: l1 } = useSWR<AnalyticsSummary>(base ? `${base}/analytics/summary?window=7d` : null, fetcher);
  const { data: ts } = useSWR<Timeseries>(base ? `${base}/analytics/timeseries?metric=messages&window=7d` : null, fetcher);
  const { data: convs } = useSWR<{ items: Conversation[] }>(base ? `${base}/conversations?limit=6` : null, fetcher);
  const { data: docs } = useSWR<{ items: DocItem[] }>(base ? `${base}/documents` : null, fetcher);

  if (!tenantId) return (<><PageHead title="Overview" /><NoTenant /></>);

  const deflection = sum ? `${Math.round(sum.deflection_rate * 100)}%` : "—";
  const readyDocs = docs?.items.filter((d) => d.status === "ready").length ?? 0;
  const trend = (ts?.points ?? []).map((p) => ({ label: bucketLabel(p.t, "7d"), value: p.v }));
  const langData = Object.entries(sum?.by_language ?? {}).map(([k, v]) => ({
    name: LANG_LABEL[k] ?? k, value: v, color: LANG_COLOR[k] ?? "#94a3b8",
  }));

  return (
    <>
      <PageHead
        title={`Welcome${active ? `, ${active.business_name}` : ""}`}
        lede="A snapshot of your assistant's activity over the last 7 days."
      />

      <div className="grid grid-4" style={{ marginBottom: 18 }}>
        {l1 ? (
          [0, 1, 2, 3].map((i) => <div key={i} className="stat"><Skeleton h={70} /></div>)
        ) : (
          <>
            <Stat label="Messages" value={fmtNum(sum?.messages_total ?? 0)} icon="chat" delta={`${fmtNum(sum?.user_messages ?? 0)} from customers`} />
            <Stat label="Deflection rate" value={deflection} icon="shield" delta="resolved without a human" deltaDir="up" />
            <Stat label="Escalations" value={fmtNum(sum?.escalations_total ?? 0)} icon="alert" delta="handed to a human" />
            <Stat label="Knowledge" value={fmtNum(readyDocs)} icon="book" delta="documents indexed" />
          </>
        )}
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1.6fr 1fr", marginBottom: 18 }}>
        <div className="card">
          <div className="card-head">
            <div><h3>Message volume</h3><div className="sub">Hourly, last 7 days</div></div>
            <Link href="/dashboard/analytics" className="btn btn-ghost btn-sm">Analytics <Icon name="external" size={13} /></Link>
          </div>
          <div className="card-pad">
            {trend.length ? <AreaTrend data={trend} /> : <Empty icon="chart" title="No traffic yet" hint="Volume appears once customers start chatting." />}
          </div>
        </div>

        <div className="card">
          <div className="card-head"><div><h3>Language mix</h3><div className="sub">Detected on inbound</div></div></div>
          <div className="card-pad"><Donut data={langData} /></div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <div><h3>Recent conversations</h3></div>
          <Link href="/dashboard/conversations" className="btn btn-ghost btn-sm">View all</Link>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Channel</th><th>Customer</th><th>Turns</th><th>Languages</th><th>Status</th><th>Last activity</th></tr></thead>
            <tbody>
              {(convs?.items ?? []).map((c) => (
                <tr key={c.conversation_id}>
                  <td><Badge tone={c.channel === "whatsapp" ? "green" : "blue"}>{c.channel}</Badge></td>
                  <td className="mono">{(c.sender_id ?? "—").slice(0, 16)}</td>
                  <td>{c.turn_count}</td>
                  <td>{(c.languages_seen ?? []).map((l) => LANG_LABEL[l] ?? l).join(", ") || "—"}</td>
                  <td>{c.has_escalation ? <Badge tone="amber">Escalated</Badge> : <Badge tone="green">Resolved</Badge>}</td>
                  <td className="muted">{timeAgo(c.last_turn_at)}</td>
                </tr>
              ))}
              {(!convs || convs.items.length === 0) && (
                <tr><td colSpan={6}><Empty icon="chat" title="No conversations yet" hint="Test your bot in the Playground or connect WhatsApp." /></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
