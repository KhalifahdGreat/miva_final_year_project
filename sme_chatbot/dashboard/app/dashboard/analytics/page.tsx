"use client";

export default function AnalyticsPage() {
  return (
    <>
      <h1>Analytics</h1>
      <p style={{ color: "var(--muted)" }}>
        Conversation volume, deflection rate, escalation reasons, language mix.
      </p>
      <div className="card">
        <p style={{ color: "var(--muted)" }}>
          Recharts visualisations land in Sprint 3 once the analytics endpoints return real data.
        </p>
      </div>
    </>
  );
}
