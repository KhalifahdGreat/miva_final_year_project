"use client";

import {
  createContext, useCallback, useContext, useEffect, useState, type ReactNode,
} from "react";
import { Icon, type IconName } from "./icons";

/* ----------------------------- Page header ----------------------------- */
export function PageHead({ title, lede, actions }: { title: string; lede?: string; actions?: ReactNode }) {
  return (
    <div className="page-head between" style={{ alignItems: "flex-start" }}>
      <div>
        <h1>{title}</h1>
        {lede && <p className="lede">{lede}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}

/* ------------------------------- Stat card ------------------------------ */
export function Stat({ label, value, icon, delta, deltaDir }: {
  label: string; value: ReactNode; icon?: IconName; delta?: string; deltaDir?: "up" | "down";
}) {
  return (
    <div className="stat">
      {icon && <div className="stat-ico"><Icon name={icon} size={20} /></div>}
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {delta && <div className={`delta ${deltaDir ?? ""}`}>{delta}</div>}
    </div>
  );
}

/* -------------------------------- Badge --------------------------------- */
const BADGE_TONE: Record<string, string> = {
  green: "badge-green", blue: "badge-blue", amber: "badge-amber",
  red: "badge-red", slate: "badge-slate",
};
export function Badge({ children, tone = "slate", dot }: { children: ReactNode; tone?: keyof typeof BADGE_TONE | string; dot?: boolean }) {
  return <span className={`badge ${BADGE_TONE[tone] ?? "badge-slate"} ${dot ? "dot" : ""}`}>{children}</span>;
}

/* ------------------------------- Spinner -------------------------------- */
export function Spinner({ dark }: { dark?: boolean }) {
  return <span className={`spinner ${dark ? "dark" : ""}`} />;
}

/* ----------------------------- Empty state ------------------------------ */
export function Empty({ icon = "grid", title, hint, action }: { icon?: IconName; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-ico"><Icon name={icon} size={24} /></div>
      <div style={{ fontWeight: 600, color: "var(--text)" }}>{title}</div>
      {hint && <div style={{ marginTop: 4 }}>{hint}</div>}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  );
}

/* ------------------------------- Skeleton ------------------------------- */
export function Skeleton({ h = 16, w = "100%", r = 8 }: { h?: number; w?: number | string; r?: number }) {
  return <div className="skeleton" style={{ height: h, width: w, borderRadius: r }} />;
}

/* -------------------------------- Modal --------------------------------- */
export function Modal({ title, onClose, children, footer, wide }: {
  title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={wide ? { maxWidth: 860 } : undefined} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close"><Icon name="x" /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-head" style={{ borderTop: "1px solid var(--border)", borderBottom: 0, justifyContent: "flex-end" }}>{footer}</div>}
      </div>
    </div>
  );
}

/* -------------------------------- Toasts -------------------------------- */
type Toast = { id: number; text: string; tone: "default" | "success" | "error" };
const ToastCtx = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "default") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3600);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toast-host">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tone}`}>
            {t.tone === "success" && <Icon name="check" size={16} />}
            {t.tone === "error" && <Icon name="alert" size={16} />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* --------------------------- Copy-to-clipboard -------------------------- */
export function CopyButton({ text, label = "Copy", className = "btn btn-ghost btn-sm" }: { text: string; label?: string; className?: string }) {
  const toast = useToast();
  const [done, setDone] = useState(false);
  return (
    <button
      className={className}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true); toast("Copied to clipboard", "success");
          setTimeout(() => setDone(false), 1500);
        } catch { toast("Copy failed", "error"); }
      }}
    >
      <Icon name={done ? "check" : "copy"} size={14} /> {done ? "Copied" : label}
    </button>
  );
}
