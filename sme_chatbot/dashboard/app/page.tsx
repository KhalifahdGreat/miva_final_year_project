import Link from "next/link";
import { Icon } from "@/components/icons";

const FEATURES = [
  { icon: "whatsapp", title: "WhatsApp + Web", text: "One assistant across your WhatsApp Business number and a drop-in website widget." },
  { icon: "language", title: "Multilingual", text: "English and Pidgin out of the box, with best-effort Yoruba, Hausa and Igbo." },
  { icon: "book", title: "Grounded in your data", text: "Answers only from your catalogue, FAQs and policies — it never invents prices." },
  { icon: "shield", title: "Knows its limits", text: "Hands off to a human the moment it isn't confident, so customers never get stuck." },
] as const;

export default function HomePage() {
  return (
    <div style={{ minHeight: "100vh", background: "radial-gradient(1200px 600px at 80% -10%, #d1fae5 0%, transparent 55%), var(--bg)" }}>
      <header style={{ maxWidth: 1100, margin: "0 auto", padding: "22px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div className="row" style={{ gap: 10 }}>
          <div className="logo" style={{ width: 34, height: 34, borderRadius: 10, background: "linear-gradient(135deg, var(--brand-400), var(--brand-700))", display: "grid", placeItems: "center", color: "#fff", fontWeight: 800 }}>S</div>
          <strong>SME Chatbot</strong>
        </div>
        <Link href="/dashboard" className="btn">Open console</Link>
      </header>

      <section style={{ maxWidth: 1100, margin: "0 auto", padding: "56px 24px 36px", textAlign: "center" }}>
        <span className="badge badge-green dot" style={{ marginBottom: 18 }}>Multilingual customer-service AI</span>
        <h1 style={{ fontSize: 46, lineHeight: 1.08, letterSpacing: "-0.03em", maxWidth: 760, margin: "0 auto" }}>
          A customer-service assistant that speaks your customers' language
        </h1>
        <p className="muted" style={{ fontSize: 17, maxWidth: 620, margin: "18px auto 0" }}>
          Built for Nigerian small businesses. Answers in English and Pidgin, grounded in your own
          knowledge, on WhatsApp and your website — around the clock.
        </p>
        <div className="row" style={{ justifyContent: "center", marginTop: 28, gap: 12 }}>
          <Link href="/dashboard" className="btn" style={{ padding: "12px 22px", fontSize: 15 }}>Open the console <Icon name="external" size={15} /></Link>
          <Link href="/dashboard/playground" className="btn btn-ghost" style={{ padding: "12px 22px", fontSize: 15 }}>Try the demo</Link>
        </div>
      </section>

      <section style={{ maxWidth: 1100, margin: "0 auto", padding: "16px 24px 72px" }}>
        <div className="grid grid-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="card card-pad">
              <span className="stat-ico" style={{ position: "static", marginBottom: 12 }}><Icon name={f.icon} size={20} /></span>
              <h3 style={{ marginBottom: 6 }}>{f.title}</h3>
              <p className="muted" style={{ fontSize: 13.5 }}>{f.text}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
