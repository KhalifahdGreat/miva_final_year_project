"use client";

import { useState } from "react";
import useSWR from "swr";
import { useTenant } from "@/lib/tenant";
import { API_BASE, fetcher, LANG_LABEL, type Conversation } from "@/lib/api";
import { PageHead, Badge, Empty, Skeleton, Modal, useToast } from "@/components/ui";
import { NoTenant } from "@/components/common";
import { Icon } from "@/components/icons";
import { fmtTime, timeAgo } from "@/lib/format";

type TurnRow = {
  turn_id: string; role: string; text: string; received_at: string | null;
  detected_language: string | null; escalated: boolean; escalation_reason: string | null;
};

export default function ConversationsPage() {
  const { tenantId } = useTenant();
  const toast = useToast();
  const [onlyEsc, setOnlyEsc] = useState(false);
  const [open, setOpen] = useState<Conversation | null>(null);

  const q = new URLSearchParams({ limit: "100" });
  if (onlyEsc) q.set("escalated", "true");
  const base = tenantId ? `/v1/tenants/${tenantId}/conversations?${q}` : null;
  const { data, isLoading } = useSWR<{ items: Conversation[] }>(base, fetcher);

  const turnsKey = open && tenantId ? `/v1/tenants/${tenantId}/conversations/${open.conversation_id}/turns` : null;
  const { data: turns } = useSWR<{ items: TurnRow[] }>(turnsKey, fetcher);

  async function rate(turnId: string, rating: "up" | "down") {
    if (!open || !tenantId) return;
    try {
      await fetch(`${API_BASE}/v1/tenants/${tenantId}/conversations/${open.conversation_id}/feedback`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ turn_id: turnId, rating }),
      });
      toast(rating === "up" ? "Marked as good" : "Flagged for review", "success");
    } catch (e) { toast(`Failed: ${String(e)}`, "error"); }
  }

  if (!tenantId) return (<><PageHead title="Conversations" /><NoTenant /></>);
  const items = data?.items ?? [];

  return (
    <>
      <PageHead
        title="Conversations"
        lede="Review what customers asked and how the bot replied."
        actions={<span className={`chip ${onlyEsc ? "on" : ""}`} onClick={() => setOnlyEsc((v) => !v)}><Icon name="alert" size={14} /> Escalated only</span>}
      />

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Channel</th><th>Customer</th><th>Turns</th><th>Languages</th><th>Status</th><th>Started</th><th>Last activity</th></tr></thead>
            <tbody>
              {isLoading && [0, 1, 2, 3].map((i) => <tr key={i}><td colSpan={7}><Skeleton h={20} /></td></tr>)}
              {!isLoading && items.map((c) => (
                <tr key={c.conversation_id} className="clickable" onClick={() => setOpen(c)}>
                  <td><Badge tone={c.channel === "whatsapp" ? "green" : "blue"}>{c.channel}</Badge></td>
                  <td className="mono">{(c.sender_id ?? "—").slice(0, 18)}</td>
                  <td>{c.turn_count}</td>
                  <td>{(c.languages_seen ?? []).map((l) => LANG_LABEL[l] ?? l).join(", ") || "—"}</td>
                  <td>{c.has_escalation ? <Badge tone="amber">Escalated</Badge> : <Badge tone="green">Resolved</Badge>}</td>
                  <td className="muted">{fmtTime(c.started_at)}</td>
                  <td className="muted">{timeAgo(c.last_turn_at)}</td>
                </tr>
              ))}
              {!isLoading && items.length === 0 && (
                <tr><td colSpan={7}><Empty icon="chat" title="No conversations" hint={onlyEsc ? "No escalations in range." : "Conversations show up here as customers chat."} /></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {open && (
        <Modal title="Conversation transcript" onClose={() => setOpen(null)} wide>
          <div className="row" style={{ marginBottom: 14, gap: 8 }}>
            <Badge tone={open.channel === "whatsapp" ? "green" : "blue"}>{open.channel}</Badge>
            <span className="mono muted">{open.sender_id}</span>
            <span className="faint">·</span>
            <span className="muted">{fmtTime(open.started_at)}</span>
          </div>
          <div className="chat-thread">
            {(turns?.items ?? []).map((t) => (
              <div key={t.turn_id} className={`bubble ${t.role === "user" ? "user" : "bot"}`}>
                {t.text}
                <div className="meta row" style={{ justifyContent: "space-between" }}>
                  <span>{t.detected_language ? (LANG_LABEL[t.detected_language] ?? t.detected_language) : t.role}{t.escalated ? " · escalated" : ""}</span>
                  {t.role !== "user" && (
                    <span className="row" style={{ gap: 6 }}>
                      <button className="btn btn-ghost btn-icon btn-sm" title="Good reply" onClick={() => rate(t.turn_id, "up")}><Icon name="check" size={13} /></button>
                      <button className="btn btn-ghost btn-icon btn-sm" title="Needs work" onClick={() => rate(t.turn_id, "down")}><Icon name="x" size={13} /></button>
                    </span>
                  )}
                </div>
              </div>
            ))}
            {(!turns || turns.items.length === 0) && <div className="muted" style={{ padding: 20, textAlign: "center" }}>Loading transcript…</div>}
          </div>
        </Modal>
      )}
    </>
  );
}
