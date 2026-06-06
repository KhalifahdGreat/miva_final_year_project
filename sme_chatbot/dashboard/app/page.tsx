import Link from "next/link";

export default function HomePage() {
  return (
    <div className="container">
      <header style={{ marginBottom: 36 }}>
        <h1 style={{ marginBottom: 4 }}>SME Chatbot</h1>
        <p style={{ color: "var(--muted)", marginTop: 0 }}>
          Multilingual customer-service assistant for Nigerian small businesses.
        </p>
      </header>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Welcome</h2>
        <p>Sign in to manage your business, upload your knowledge, and review conversations.</p>
        <Link href="/dashboard" className="btn">Open dashboard</Link>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>What does this bot do?</h2>
        <ul>
          <li>Answers customer questions on WhatsApp and your website.</li>
          <li>Speaks English, Pidgin, and (best-effort) Yoruba, Hausa, Igbo.</li>
          <li>Grounded in your own catalogue, FAQs, and policies — never invents prices.</li>
          <li>Hands off to a human the moment it doesn't know.</li>
        </ul>
      </div>
    </div>
  );
}
