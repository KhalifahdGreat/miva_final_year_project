"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { useTenant } from "@/lib/tenant";
import { API_BASE, api, fetcher, type WhatsAppStatus } from "@/lib/api";
import { PageHead, Badge, CopyButton, useToast } from "@/components/ui";
import { NoTenant } from "@/components/common";
import { Icon } from "@/components/icons";

export default function ChannelsPage() {
  const { tenantId } = useTenant();
  const toast = useToast();
  const base = tenantId ? `/v1/tenants/${tenantId}` : null;

  const { data: wa, mutate: mutateWa } = useSWR<WhatsAppStatus>(base ? `${base}/channels/whatsapp` : null, fetcher);

  const [waba, setWaba] = useState("");
  const [phoneId, setPhoneId] = useState("");
  const [token, setToken] = useState("");
  const [displayPhone, setDisplayPhone] = useState("");
  const [savingWa, setSavingWa] = useState(false);

  const [widgetKey, setWidgetKey] = useState<string>("");
  const [minting, setMinting] = useState(false);

  async function connectWhatsApp() {
    if (!tenantId) return;
    setSavingWa(true);
    try {
      await api(`${base}/channels/whatsapp`, {
        method: "POST",
        body: JSON.stringify({ waba_id: waba, phone_number_id: phoneId, access_token: token, display_phone: displayPhone || null }),
      });
      toast("WhatsApp connected", "success");
      setToken("");
      void mutateWa();
    } catch (e) { toast(`Failed: ${String(e)}`, "error"); }
    finally { setSavingWa(false); }
  }

  async function mintKey() {
    if (!tenantId) return;
    setMinting(true);
    try {
      const r = await api<{ widget_key: string }>(`${base}/widget-keys`, { method: "POST", body: JSON.stringify({ allowed_origins: [] }) });
      setWidgetKey(r.widget_key);
      toast("Widget key generated", "success");
    } catch (e) { toast(`Failed: ${String(e)}`, "error"); }
    finally { setMinting(false); }
  }

  const snippet = useMemo(() => `<script src="https://cdn.your-domain.tld/widget.js" defer></script>
<script>
  window.addEventListener("load", function () {
    window.SmeChatbot.init({
      apiBase: "${API_BASE}",
      widgetKey: "${widgetKey || "YOUR_WIDGET_KEY"}",
      title: "Customer support"
    });
  });
</script>`, [widgetKey]);

  if (!tenantId) return (<><PageHead title="Channels" /><NoTenant /></>);

  return (
    <>
      <PageHead title="Channels" lede="Connect WhatsApp and embed the chat widget on your website." />

      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-head">
          <div className="row" style={{ gap: 10 }}>
            <span className="stat-ico" style={{ position: "static", background: "var(--brand-50)", color: "var(--brand-600)" }}><Icon name="whatsapp" /></span>
            <div><h3>WhatsApp Business</h3><div className="sub">Meta Cloud API</div></div>
          </div>
          {wa?.connected
            ? <Badge tone="green" dot>Connected{wa.display_phone ? ` · ${wa.display_phone}` : ""}</Badge>
            : <Badge tone="slate" dot>Not connected</Badge>}
        </div>
        <div className="card-pad">
          <div className="grid grid-2">
            <div className="field"><label>WhatsApp Business Account ID (WABA)</label><input value={waba} onChange={(e) => setWaba(e.target.value)} placeholder="1109270892277103" /></div>
            <div className="field"><label>Phone number ID</label><input value={phoneId} onChange={(e) => setPhoneId(e.target.value)} placeholder="994802799818814" /></div>
            <div className="field"><label>Display phone (optional)</label><input value={displayPhone} onChange={(e) => setDisplayPhone(e.target.value)} placeholder="+234 ..." /></div>
            <div className="field"><label>Permanent access token</label><input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="EAAO… (stored encrypted)" /></div>
          </div>
          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button className="btn" onClick={connectWhatsApp} disabled={savingWa || !waba || !phoneId || !token}>
              {savingWa ? "Saving…" : wa?.connected ? "Update credentials" : "Connect WhatsApp"}
            </button>
          </div>
          <div className="hint">Tokens are encrypted at rest. Inbound messages to this phone number route to this workspace automatically.</div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <div className="row" style={{ gap: 10 }}>
            <span className="stat-ico" style={{ position: "static", background: "#eff6ff", color: "#2563eb" }}><Icon name="globe" /></span>
            <div><h3>Website widget</h3><div className="sub">Drop-in chat bubble</div></div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={mintKey} disabled={minting}><Icon name="plus" size={14} /> {minting ? "Generating…" : "Generate key"}</button>
        </div>
        <div className="card-pad">
          {widgetKey && (
            <div className="field">
              <label>Widget key</label>
              <div className="row"><input readOnly value={widgetKey} className="mono" /><CopyButton text={widgetKey} /></div>
            </div>
          )}
          <label className="lbl">Embed snippet</label>
          <pre style={{ background: "var(--slate-900)", color: "#e2e8f0", padding: 16, borderRadius: 12, overflowX: "auto", fontSize: 12, marginTop: 6 }}>
            <code>{snippet}</code>
          </pre>
          <div className="row" style={{ justifyContent: "flex-end", marginTop: 10 }}>
            <CopyButton text={snippet} label="Copy snippet" />
          </div>
        </div>
      </div>
    </>
  );
}
