"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const TONES = [
  { value: "formal", label: "Formal — full sentences, polite English" },
  { value: "casual", label: "Casual — friendly conversational English" },
  { value: "pidgin_friendly", label: "Pidgin-friendly — mirror the customer's register" },
  { value: "youthful", label: "Youthful — Gen-Z, lively, light emoji ok" },
] as const;

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "pid", label: "Pidgin" },
  { code: "yo", label: "Yoruba" },
  { code: "ha", label: "Hausa" },
  { code: "ig", label: "Igbo" },
] as const;

export default function PersonaPage() {
  const [tenantId, setTenantId] = useState("");
  const [tagline, setTagline] = useState("");
  const [tone, setTone] = useState<string>("casual");
  const [languages, setLanguages] = useState<string[]>(["en", "pid"]);
  const [greeting, setGreeting] = useState("");
  const [fallback, setFallback] = useState("");
  const [status, setStatus] = useState("");

  function toggleLang(code: string) {
    setLanguages((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  }

  async function save() {
    if (!tenantId) {
      setStatus("Tenant ID required.");
      return;
    }
    setStatus("Saving...");
    try {
      const res = await fetch(`${API_BASE}/v1/tenants/${tenantId}/config`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ tagline, tone, languages, greeting, fallback }),
      });
      const data = await res.json();
      setStatus(res.ok ? `Saved (version ${data.version}).` : `Failed: ${JSON.stringify(data)}`);
    } catch (err) {
      setStatus(`Network error: ${String(err)}`);
    }
  }

  return (
    <>
      <h1>Persona &amp; tone</h1>
      <p style={{ color: "var(--muted)" }}>How should your bot sound?</p>

      <div className="card">
        <label>Tenant ID</label>
        <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} />

        <label style={{ marginTop: 14 }}>Tagline (one line, optional)</label>
        <input value={tagline} onChange={(e) => setTagline(e.target.value)}
               placeholder="e.g. Mama Ngozi's Kitchen — Lagos's best jollof" />

        <label style={{ marginTop: 14 }}>Tone</label>
        <select value={tone} onChange={(e) => setTone(e.target.value)}>
          {TONES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        <label style={{ marginTop: 14 }}>Languages</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
          {LANGUAGES.map((l) => (
            <label key={l.code} style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 400, color: "var(--text)" }}>
              <input type="checkbox" checked={languages.includes(l.code)} onChange={() => toggleLang(l.code)} style={{ width: "auto" }} />
              {l.label}
            </label>
          ))}
        </div>

        <label style={{ marginTop: 14 }}>Greeting</label>
        <textarea rows={2} value={greeting} onChange={(e) => setGreeting(e.target.value)}
                  placeholder="Hi! How can I help you today?" />

        <label style={{ marginTop: 14 }}>Fallback (used when the bot doesn't know the answer)</label>
        <textarea rows={2} value={fallback} onChange={(e) => setFallback(e.target.value)}
                  placeholder="I'm not sure about that one — let me get a colleague to help." />

        <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center" }}>
          <button className="btn" onClick={save}>Save</button>
          {status && <span style={{ color: "var(--muted)" }}>{status}</span>}
        </div>
      </div>
    </>
  );
}
