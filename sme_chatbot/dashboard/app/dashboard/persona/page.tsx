"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { useTenant } from "@/lib/tenant";
import { fetcher, api } from "@/lib/api";
import { PageHead, useToast } from "@/components/ui";
import { NoTenant } from "@/components/common";

const TONES = [
  { value: "formal", label: "Formal", hint: "Full sentences, polite English" },
  { value: "casual", label: "Casual", hint: "Friendly conversational English" },
  { value: "pidgin_friendly", label: "Pidgin-friendly", hint: "Mirrors the customer's register" },
  { value: "youthful", label: "Youthful", hint: "Gen-Z, lively, light emoji ok" },
];

const LANGUAGES = [
  { code: "en", label: "English" }, { code: "pid", label: "Pidgin" },
  { code: "yo", label: "Yoruba" }, { code: "ha", label: "Hausa" }, { code: "ig", label: "Igbo" },
];

type Cfg = { business_name: string; tone: string; languages: string[]; tagline?: string; greeting?: string; fallback?: string };

export default function PersonaPage() {
  const { tenantId } = useTenant();
  const toast = useToast();
  const { data, mutate } = useSWR<Cfg>(tenantId ? `/v1/tenants/${tenantId}` : null, fetcher);

  const [tone, setTone] = useState("casual");
  const [languages, setLanguages] = useState<string[]>(["en", "pid"]);
  const [tagline, setTagline] = useState("");
  const [greeting, setGreeting] = useState("");
  const [fallback, setFallback] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!data) return;
    setTone(data.tone ?? "casual");
    setLanguages(data.languages?.length ? data.languages : ["en", "pid"]);
    setTagline(data.tagline ?? "");
    setGreeting(data.greeting ?? "");
    setFallback(data.fallback ?? "");
  }, [data]);

  function toggleLang(code: string) {
    setLanguages((p) => (p.includes(code) ? p.filter((c) => c !== code) : [...p, code]));
  }

  async function save() {
    if (!tenantId) return;
    setSaving(true);
    try {
      await api(`/v1/tenants/${tenantId}/config`, {
        method: "PATCH",
        body: JSON.stringify({ tone, languages, tagline, greeting, fallback }),
      });
      toast("Persona saved", "success");
      void mutate();
    } catch (e) { toast(`Save failed: ${String(e)}`, "error"); }
    finally { setSaving(false); }
  }

  if (!tenantId) return (<><PageHead title="Persona & tone" /><NoTenant /></>);

  return (
    <>
      <PageHead title="Persona & tone" lede="Shape how your assistant sounds and which languages it speaks." />

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <div className="card card-pad">
          <h3 style={{ marginBottom: 14 }}>Voice</h3>

          <div className="field">
            <label>Tone</label>
            <div className="grid grid-2" style={{ gap: 10 }}>
              {TONES.map((t) => (
                <div key={t.value} className={`chip ${tone === t.value ? "on" : ""}`}
                     style={{ display: "block", padding: "10px 12px", borderRadius: 12 }}
                     onClick={() => setTone(t.value)}>
                  <div style={{ fontWeight: 600 }}>{t.label}</div>
                  <div className="faint" style={{ fontSize: 11.5 }}>{t.hint}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="field">
            <label>Languages</label>
            <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
              {LANGUAGES.map((l) => (
                <span key={l.code} className={`chip ${languages.includes(l.code) ? "on" : ""}`} onClick={() => toggleLang(l.code)}>
                  {l.label}
                </span>
              ))}
            </div>
            <div className="hint">English &amp; Pidgin are strongest; Yoruba / Hausa / Igbo are best-effort.</div>
          </div>

          <div className="field" style={{ marginBottom: 0 }}>
            <label>Tagline (optional)</label>
            <input value={tagline} onChange={(e) => setTagline(e.target.value)}
                   placeholder="e.g. Mama Ngozi's Kitchen — Lagos's best jollof" />
          </div>
        </div>

        <div className="card card-pad">
          <h3 style={{ marginBottom: 14 }}>Messages</h3>
          <div className="field">
            <label>Greeting</label>
            <textarea rows={3} value={greeting} onChange={(e) => setGreeting(e.target.value)}
                      placeholder="Hi! How can I help you today?" />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Fallback (when the bot doesn't know)</label>
            <textarea rows={3} value={fallback} onChange={(e) => setFallback(e.target.value)}
                      placeholder="I'm not sure about that one — let me get a colleague to help." />
          </div>
        </div>
      </div>

      <div className="row" style={{ marginTop: 18, justifyContent: "flex-end" }}>
        <button className="btn" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save persona"}</button>
      </div>
    </>
  );
}
