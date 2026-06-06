import Link from "next/link";

export default function DashboardOverview() {
  return (
    <>
      <h1>Overview</h1>
      <p style={{ color: "var(--muted)" }}>
        Welcome back. Here's a snapshot of how your bot is doing.
      </p>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <Stat label="Messages (7d)" value="—" />
        <Stat label="Deflection rate" value="—" />
        <Stat label="Escalations" value="—" />
        <Stat label="p95 latency" value="—" />
      </section>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Getting started</h3>
        <ol>
          <li>Tell us about your business (<Link href="/dashboard/persona">Persona &amp; tone</Link>)</li>
          <li>Upload your catalogue or FAQs (<Link href="/dashboard/knowledge">Knowledge</Link>)</li>
          <li>Connect WhatsApp or paste the widget snippet (<Link href="/dashboard/channels">Channels</Link>)</li>
          <li>Send a test message</li>
        </ol>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <div style={{ color: "var(--muted)", fontSize: 12, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, marginTop: 6 }}>{value}</div>
    </div>
  );
}
