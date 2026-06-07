"use client";

import { Empty } from "./ui";

export const WINDOWS = [
  { v: "24h", label: "24h" },
  { v: "7d", label: "7 days" },
  { v: "30d", label: "30 days" },
] as const;

export function WindowPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="row" style={{ gap: 6 }}>
      {WINDOWS.map((w) => (
        <span key={w.v} className={`chip ${value === w.v ? "on" : ""}`} onClick={() => onChange(w.v)}>
          {w.label}
        </span>
      ))}
    </div>
  );
}

export function NoTenant() {
  return (
    <div className="card card-pad">
      <Empty
        icon="grid"
        title="No workspace selected"
        hint="Create or pick a workspace from the switcher at the top-left to get started."
      />
    </div>
  );
}
