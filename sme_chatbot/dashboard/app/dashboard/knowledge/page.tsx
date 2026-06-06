"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type DocType = "catalogue" | "faq" | "policy" | "manual_faq" | "pricing";

export default function KnowledgePage() {
  const [tenantId, setTenantId] = useState("");
  const [docType, setDocType] = useState<DocType>("faq");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);

  async function upload() {
    if (!file || !tenantId) {
      setStatus("Tenant ID and file are both required.");
      return;
    }
    const fd = new FormData();
    fd.append("document_type", docType);
    fd.append("file", file);
    setBusy(true);
    setStatus("Uploading...");
    try {
      const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/documents`, {
        method: "POST",
        body: fd,
      });
      const data = await res.json();
      if (res.ok) {
        setStatus(
          `OK — ${data.chunks_created} chunks created in ${data.duration_s}s.`,
        );
      } else {
        setStatus(`Failed (${res.status}): ${JSON.stringify(data)}`);
      }
    } catch (err) {
      setStatus(`Network error: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Knowledge</h1>
      <p style={{ color: "var(--muted)" }}>
        Upload your catalogue, FAQs, return policy — anything the bot should ground its answers in.
      </p>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Upload a document</h3>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
          <div>
            <label>Tenant ID</label>
            <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} placeholder="uuid" />
          </div>
          <div>
            <label>Type</label>
            <select value={docType} onChange={(e) => setDocType(e.target.value as DocType)}>
              <option value="catalogue">Product catalogue</option>
              <option value="faq">FAQ</option>
              <option value="manual_faq">Curated Q/A pair</option>
              <option value="policy">Policy</option>
              <option value="pricing">Pricing</option>
            </select>
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label>File</label>
            <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                   accept=".pdf,.docx,.txt,.md,.csv,.xlsx" />
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center" }}>
          <button className="btn" disabled={busy} onClick={upload}>
            {busy ? "Uploading..." : "Upload"}
          </button>
          {status && <span style={{ color: "var(--muted)" }}>{status}</span>}
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Uploaded documents</h3>
        <table>
          <thead>
            <tr><th>Title</th><th>Type</th><th>Chunks</th><th>Status</th><th>Uploaded</th></tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={5} style={{ color: "var(--muted)" }}>(Document listing will appear after Sprint 2.)</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
