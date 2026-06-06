"use client";

import { useMemo, useState } from "react";

export default function ChannelsPage() {
  const [tenantId, setTenantId] = useState("");
  const [widgetKey, setWidgetKey] = useState("demo-widget-key-replace-me");

  const snippet = useMemo(
    () =>
      `<script src="https://cdn.your-domain.tld/widget.js" defer></script>
<script>
  window.addEventListener("load", function () {
    window.SmeChatbot.init({
      apiBase: "https://api.your-domain.tld",
      widgetKey: "${widgetKey}",
      title: "Customer support"
    });
  });
</script>`,
    [widgetKey],
  );

  return (
    <>
      <h1>Channels</h1>
      <p style={{ color: "var(--muted)" }}>
        Connect your WhatsApp Business number and drop the chat widget onto your website.
      </p>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>WhatsApp</h3>
        <p>Connecting your WhatsApp Business account uses Meta's official Cloud API.</p>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          (OAuth flow will live here in Sprint 2 — for now, configure credentials manually in the database.)
        </p>
        <label>Tenant ID (for credential association)</label>
        <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Website widget</h3>
        <p>Paste this snippet inside the <code>&lt;head&gt;</code> of your website:</p>
        <label>Widget key</label>
        <input value={widgetKey} onChange={(e) => setWidgetKey(e.target.value)} />
        <pre
          style={{
            background: "#0f172a",
            color: "#e2e8f0",
            padding: 16,
            borderRadius: 8,
            overflowX: "auto",
            fontSize: 12,
            marginTop: 12,
          }}
        >
          <code>{snippet}</code>
        </pre>
        <button className="btn-ghost" onClick={() => navigator.clipboard.writeText(snippet)}>
          Copy snippet
        </button>
      </div>
    </>
  );
}
