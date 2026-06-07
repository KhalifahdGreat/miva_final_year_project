export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body || path}`);
  }
  return res.json() as Promise<T>;
}

/** SWR fetcher (GET). */
export const fetcher = <T,>(path: string) => api<T>(path);

/* ------------------------------- Types ---------------------------------- */
export type TenantSummary = {
  tenant_id: string;
  business_name: string;
  created_at: string | null;
  whatsapp_connected: boolean;
};

export type AnalyticsSummary = {
  tenant_id: string;
  window: string;
  messages_total: number;
  user_messages: number;
  escalations_total: number;
  deflection_rate: number;
  avg_latency_p50_ms: number;
  avg_latency_p95_ms: number;
  avg_latency_p99_ms: number;
  by_language: Record<string, number>;
};

export type TimeseriesPoint = { t: string | null; v: number };
export type Timeseries = { metric: string; window: string; points: TimeseriesPoint[] };

export type DocItem = {
  document_id: string;
  title: string;
  document_type: string;
  mime_type: string;
  byte_size: number;
  chunk_count: number;
  status: string;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
  has_file: boolean;
};

export type Conversation = {
  conversation_id: string;
  channel: string;
  sender_id?: string;
  started_at: string | null;
  last_turn_at: string | null;
  turn_count: number;
  languages_seen?: string[];
  has_escalation: boolean;
};

export type Turn = {
  turn_id?: string;
  role: string;
  content: string;
  detected_language?: string | null;
  escalated?: boolean;
  created_at?: string | null;
  received_at?: string | null;
};

export type WhatsAppStatus = {
  connected: boolean;
  display_phone?: string | null;
  phone_number_id?: string | null;
};

export const LANG_LABEL: Record<string, string> = {
  en: "English", pid: "Pidgin", pcm: "Pidgin", yo: "Yoruba", ha: "Hausa",
  ig: "Igbo", und: "Unknown", unknown: "Unknown",
};

export const LANG_COLOR: Record<string, string> = {
  en: "#059669", pid: "#2563eb", pcm: "#2563eb", yo: "#d97706",
  ha: "#7c3aed", ig: "#db2777", und: "#94a3b8", unknown: "#94a3b8",
};
