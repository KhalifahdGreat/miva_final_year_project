"use client";

import { useEffect, useRef, useState } from "react";
import { useTenant } from "@/lib/tenant";
import { useToast } from "./ui";
import { Icon } from "./icons";

function initials(name: string) {
  return (name || "?").trim().slice(0, 2).toUpperCase();
}

export function TenantSwitcher() {
  const { active, tenants, setActive, createTenant } = useTenant();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) { setOpen(false); setCreating(false); }
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  async function doCreate() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await createTenant(name.trim());
      toast(`Workspace "${name.trim()}" created`, "success");
      setName(""); setCreating(false); setOpen(false);
    } catch (e) {
      toast(`Could not create: ${String(e)}`, "error");
    } finally { setBusy(false); }
  }

  return (
    <div className="ws-switch" ref={ref}>
      <button className="ws-trigger" onClick={() => setOpen((o) => !o)}>
        <span className="ws-ava">{initials(active?.business_name ?? "SME")}</span>
        <span style={{ textAlign: "left", flex: 1 }}>
          <div className="ws-name">{active?.business_name ?? "Select workspace"}</div>
          <div className="ws-sub">{tenants.length} workspace{tenants.length === 1 ? "" : "s"}</div>
        </span>
        <Icon name="chevron" size={16} />
      </button>

      {open && (
        <div className="ws-menu">
          <div style={{ maxHeight: 280, overflowY: "auto" }}>
            {tenants.map((t) => (
              <div
                key={t.tenant_id}
                className={`ws-item ${t.tenant_id === active?.tenant_id ? "active" : ""}`}
                onClick={() => { setActive(t.tenant_id); setOpen(false); }}
              >
                <span className="ws-ava" style={{ width: 26, height: 26, fontSize: 12 }}>{initials(t.business_name)}</span>
                <span style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{t.business_name}</div>
                  <div className="faint" style={{ fontSize: 11 }}>{t.whatsapp_connected ? "WhatsApp connected" : "Web only"}</div>
                </span>
                {t.tenant_id === active?.tenant_id && <Icon name="check" size={15} />}
              </div>
            ))}
            {tenants.length === 0 && <div className="muted" style={{ padding: 10, fontSize: 13 }}>No workspaces yet.</div>}
          </div>

          <div className="divider" style={{ margin: "8px 0" }} />

          {creating ? (
            <div style={{ padding: "0 4px 4px" }}>
              <input
                autoFocus value={name} placeholder="Business name"
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && doCreate()}
              />
              <div className="row" style={{ marginTop: 8, justifyContent: "flex-end" }}>
                <button className="btn btn-ghost btn-sm" onClick={() => setCreating(false)}>Cancel</button>
                <button className="btn btn-sm" onClick={doCreate} disabled={busy}>
                  {busy ? "Creating…" : "Create"}
                </button>
              </div>
            </div>
          ) : (
            <div className="ws-item" onClick={() => setCreating(true)} style={{ color: "var(--brand-700)", fontWeight: 600 }}>
              <Icon name="plus" size={16} /> New workspace
            </div>
          )}
        </div>
      )}
    </div>
  );
}
