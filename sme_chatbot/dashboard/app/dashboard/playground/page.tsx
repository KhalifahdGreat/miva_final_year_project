"use client";

import { useEffect, useRef, useState } from "react";
import { useTenant } from "@/lib/tenant";
import { API_BASE, api, LANG_LABEL } from "@/lib/api";
import { PageHead, Badge, useToast } from "@/components/ui";
import { NoTenant } from "@/components/common";
import { Icon } from "@/components/icons";

type Msg = { role: "user" | "bot"; text: string; lang?: string; escalated?: boolean };

export default function PlaygroundPage() {
  const { tenantId, active } = useTenant();
  const toast = useToast();
  const [session, setSession] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [booting, setBooting] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);

  async function startSession() {
    if (!tenantId) return;
    setBooting(true);
    setMsgs([]); setSession(null);
    try {
      const key = await api<{ widget_key: string }>(`/v1/tenants/${tenantId}/widget-keys`, {
        method: "POST", body: JSON.stringify({ allowed_origins: [] }),
      });
      const s = await api<{ session_token: string; greeting: string }>(`/widget/v1/session`, {
        method: "POST", body: JSON.stringify({ widget_key: key.widget_key }),
      });
      setSession(s.session_token);
      setMsgs([{ role: "bot", text: s.greeting }]);
    } catch (e) { toast(`Couldn't start session: ${String(e)}`, "error"); }
    finally { setBooting(false); }
  }

  useEffect(() => { if (tenantId) void startSession(); /* eslint-disable-next-line */ }, [tenantId]);
  useEffect(() => { threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" }); }, [msgs]);

  async function send() {
    const text = input.trim();
    if (!text || !session || sending) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text }]);
    setSending(true);
    try {
      const r = await fetch(`${API_BASE}/widget/v1/message`, {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${session}` },
        body: JSON.stringify({ text }),
      });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      setMsgs((m) => [...m, { role: "bot", text: data.reply, lang: data.detected_language, escalated: data.escalated }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "bot", text: `⚠️ ${String(e)}` }]);
    } finally { setSending(false); }
  }

  if (!tenantId) return (<><PageHead title="Playground" /><NoTenant /></>);

  return (
    <>
      <PageHead
        title="Playground"
        lede={`Chat with your assistant exactly as a customer would${active ? ` · ${active.business_name}` : ""}.`}
        actions={<button className="btn btn-ghost btn-sm" onClick={startSession} disabled={booting}><Icon name="refresh" size={14} /> Reset</button>}
      />

      <div className="card" style={{ maxWidth: 760, margin: "0 auto" }}>
        <div className="card-head">
          <div className="row" style={{ gap: 10 }}>
            <span className="ws-ava" style={{ width: 30, height: 30 }}>{(active?.business_name ?? "S").slice(0, 1).toUpperCase()}</span>
            <div><h3>{active?.business_name ?? "Assistant"}</h3><div className="sub">{session ? "Online" : "Connecting…"}</div></div>
          </div>
          {session ? <Badge tone="green" dot>Live session</Badge> : <span className="spinner dark" />}
        </div>

        <div ref={threadRef} className="chat-thread" style={{ height: 440, overflowY: "auto", padding: 20 }}>
          {msgs.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.text}
              {m.role === "bot" && (m.lang || m.escalated) && (
                <div className="meta">{m.lang ? (LANG_LABEL[m.lang] ?? m.lang) : ""}{m.escalated ? " · escalated to human" : ""}</div>
              )}
            </div>
          ))}
          {sending && <div className="bubble bot"><span className="spinner dark" /></div>}
        </div>

        <div className="card-head" style={{ borderTop: "1px solid var(--border)", borderBottom: 0, gap: 10 }}>
          <input
            placeholder={session ? "Type a message…" : "Starting session…"}
            value={input} disabled={!session}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button className="btn" onClick={send} disabled={!session || sending || !input.trim()}><Icon name="send" size={15} /> Send</button>
        </div>
      </div>
    </>
  );
}
