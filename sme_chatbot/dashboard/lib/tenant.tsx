"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import useSWR from "swr";
import { api, fetcher, type TenantSummary } from "./api";

const STORAGE_KEY = "sme.activeTenant";

type Ctx = {
  tenantId: string | null;
  active: TenantSummary | null;
  tenants: TenantSummary[];
  loading: boolean;
  setActive: (id: string) => void;
  refresh: () => void;
  createTenant: (name: string) => Promise<TenantSummary>;
};

const TenantCtx = createContext<Ctx | null>(null);

export function TenantProvider({ children }: { children: ReactNode }) {
  const { data, isLoading, mutate } = useSWR<{ items: TenantSummary[] }>("/v1/tenants", fetcher);
  const tenants = useMemo(() => data?.items ?? [], [data]);
  const [tenantId, setTenantId] = useState<string | null>(null);

  // Hydrate from localStorage once.
  useEffect(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    if (saved) setTenantId(saved);
  }, []);

  // Default to first tenant if nothing valid selected.
  useEffect(() => {
    if (tenants.length === 0) return;
    const valid = tenantId && tenants.some((t) => t.tenant_id === tenantId);
    if (!valid) setTenantId(tenants[0].tenant_id);
  }, [tenants, tenantId]);

  const setActive = useCallback((id: string) => {
    setTenantId(id);
    try { window.localStorage.setItem(STORAGE_KEY, id); } catch { /* ignore */ }
  }, []);

  const createTenant = useCallback(async (name: string) => {
    const created = await api<{ tenant_id: string }>("/v1/tenants", {
      method: "POST",
      body: JSON.stringify({ business_name: name }),
    });
    await mutate();
    const summary: TenantSummary = {
      tenant_id: created.tenant_id, business_name: name,
      created_at: new Date().toISOString(), whatsapp_connected: false,
    };
    setActive(created.tenant_id);
    return summary;
  }, [mutate, setActive]);

  const active = useMemo(
    () => tenants.find((t) => t.tenant_id === tenantId) ?? null,
    [tenants, tenantId],
  );

  const value: Ctx = {
    tenantId, active, tenants, loading: isLoading,
    setActive, refresh: () => { void mutate(); }, createTenant,
  };
  return <TenantCtx.Provider value={value}>{children}</TenantCtx.Provider>;
}

export function useTenant() {
  const ctx = useContext(TenantCtx);
  if (!ctx) throw new Error("useTenant must be used within TenantProvider");
  return ctx;
}
