"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { useTenant } from "@/lib/tenant";
import { API_BASE, fetcher, type DocItem } from "@/lib/api";
import { PageHead, Badge, Empty, Skeleton, useToast } from "@/components/ui";
import { NoTenant } from "@/components/common";
import { Icon } from "@/components/icons";
import { fmtBytes, timeAgo } from "@/lib/format";

const DOC_TYPES = [
  { v: "faq", label: "FAQ" },
  { v: "catalogue", label: "Catalogue" },
  { v: "pricing", label: "Pricing" },
  { v: "policy", label: "Policy" },
  { v: "manual_faq", label: "Manual / guide" },
];

const STATUS_TONE: Record<string, string> = {
  ready: "green", processing: "blue", queued: "slate", failed: "red",
};

export default function KnowledgePage() {
  const { tenantId } = useTenant();
  const toast = useToast();
  const base = tenantId ? `/v1/tenants/${tenantId}/documents` : null;
  const [docType, setDocType] = useState("faq");
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data, isLoading, mutate } = useSWR<{ items: DocItem[] }>(base, fetcher, {
    refreshInterval: (d) => (d?.items.some((x) => ["queued", "processing"].includes(x.status)) ? 2500 : 0),
  });

  async function upload(files: FileList | null) {
    if (!files || !files.length || !tenantId) return;
    setUploading(true);
    let ok = 0;
    for (const file of Array.from(files)) {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("document_type", docType);
      try {
        const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/documents`, { method: "POST", body: fd });
        if (!res.ok) throw new Error(await res.text());
        ok++;
      } catch (e) { toast(`Upload failed: ${String(e)}`, "error"); }
    }
    if (ok) toast(`${ok} file${ok > 1 ? "s" : ""} uploaded — indexing…`, "success");
    setUploading(false);
    void mutate();
  }

  async function remove(id: string) {
    if (!tenantId || !confirm("Remove this document from the knowledge base?")) return;
    try {
      await fetch(`${API_BASE}/v1/tenants/${tenantId}/documents/${id}`, { method: "DELETE" });
      toast("Document removed", "success");
      void mutate();
    } catch (e) { toast(`Delete failed: ${String(e)}`, "error"); }
  }

  async function download(id: string) {
    try {
      const r = await fetch(`${API_BASE}/v1/tenants/${tenantId}/documents/${id}/download`);
      if (!r.ok) throw new Error(await r.text());
      const { url } = await r.json();
      window.open(url, "_blank");
    } catch (e) { toast(`No file available: ${String(e)}`, "error"); }
  }

  if (!tenantId) return (<><PageHead title="Knowledge" /><NoTenant /></>);

  const items = data?.items ?? [];
  const ready = items.filter((d) => d.status === "ready").length;
  const chunks = items.reduce((s, d) => s + (d.chunk_count || 0), 0);

  return (
    <>
      <PageHead title="Knowledge base" lede="Upload your catalogue, FAQs and policies. The bot only answers from what you provide here." />

      <div className="grid grid-3" style={{ marginBottom: 18 }}>
        <div className="card card-pad"><div className="muted" style={{ fontSize: 12.5, fontWeight: 600 }}>DOCUMENTS</div><div style={{ fontSize: 24, fontWeight: 800, marginTop: 6 }}>{items.length}</div></div>
        <div className="card card-pad"><div className="muted" style={{ fontSize: 12.5, fontWeight: 600 }}>INDEXED</div><div style={{ fontSize: 24, fontWeight: 800, marginTop: 6 }}>{ready}</div></div>
        <div className="card card-pad"><div className="muted" style={{ fontSize: 12.5, fontWeight: 600 }}>SEARCHABLE CHUNKS</div><div style={{ fontSize: 24, fontWeight: 800, marginTop: 6 }}>{chunks}</div></div>
      </div>

      <div className="card card-pad" style={{ marginBottom: 18 }}>
        <div className="row" style={{ marginBottom: 14, flexWrap: "wrap", gap: 8 }}>
          <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>Document type:</span>
          {DOC_TYPES.map((t) => (
            <span key={t.v} className={`chip ${docType === t.v ? "on" : ""}`} onClick={() => setDocType(t.v)}>{t.label}</span>
          ))}
        </div>
        <div
          className={`dropzone ${drag ? "drag" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); void upload(e.dataTransfer.files); }}
        >
          <div style={{ display: "grid", placeItems: "center", gap: 8 }}>
            {uploading ? <span className="spinner dark" /> : <Icon name="upload" size={26} />}
            <div style={{ fontWeight: 600 }}>{uploading ? "Uploading…" : "Drop files here or click to browse"}</div>
            <div className="hint">PDF, DOCX, TXT, CSV, MD · up to ~10 MB each</div>
          </div>
          <input ref={inputRef} type="file" multiple hidden accept=".pdf,.docx,.txt,.csv,.md"
                 onChange={(e) => void upload(e.target.files)} />
        </div>
      </div>

      <div className="card">
        <div className="card-head"><div><h3>Documents</h3></div></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Title</th><th>Type</th><th>Size</th><th>Chunks</th><th>Status</th><th>Updated</th><th></th></tr></thead>
            <tbody>
              {isLoading && [0, 1, 2].map((i) => (
                <tr key={i}><td colSpan={7}><Skeleton h={20} /></td></tr>
              ))}
              {!isLoading && items.map((d) => (
                <tr key={d.document_id}>
                  <td style={{ fontWeight: 600 }}>{d.title}</td>
                  <td><Badge tone="slate">{d.document_type}</Badge></td>
                  <td className="muted">{fmtBytes(d.byte_size)}</td>
                  <td>{d.chunk_count || "—"}</td>
                  <td>
                    <Badge tone={STATUS_TONE[d.status] ?? "slate"} dot>
                      {d.status === "processing" || d.status === "queued" ? <>{d.status}…</> : d.status}
                    </Badge>
                    {d.status === "failed" && d.error_message && <div className="hint" style={{ color: "var(--danger)" }}>{d.error_message.slice(0, 80)}</div>}
                  </td>
                  <td className="muted">{timeAgo(d.updated_at)}</td>
                  <td>
                    <div className="row" style={{ justifyContent: "flex-end", gap: 4 }}>
                      {d.has_file && <button className="btn btn-ghost btn-icon btn-sm" title="Download original" onClick={() => download(d.document_id)}><Icon name="download" size={15} /></button>}
                      <button className="btn btn-ghost btn-icon btn-sm" title="Remove" onClick={() => remove(d.document_id)}><Icon name="trash" size={15} /></button>
                    </div>
                  </td>
                </tr>
              ))}
              {!isLoading && items.length === 0 && (
                <tr><td colSpan={7}><Empty icon="book" title="No documents yet" hint="Upload your first FAQ or catalogue above to teach the bot." /></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
