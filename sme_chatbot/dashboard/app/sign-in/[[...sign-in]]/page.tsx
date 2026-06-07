"use client";

import Link from "next/link";
import { SignIn } from "@clerk/nextjs";
import { clerkEnabled } from "@/lib/clerk";

export default function SignInPage() {
  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24,
                  background: "radial-gradient(900px 500px at 50% -10%, #d1fae5, transparent 60%), var(--bg)" }}>
      {clerkEnabled ? (
        <SignIn appearance={{ elements: { rootBox: { boxShadow: "var(--shadow-lg)" } } }} />
      ) : (
        <div className="card card-pad" style={{ textAlign: "center", maxWidth: 380 }}>
          <h2>Authentication is off</h2>
          <p className="muted" style={{ margin: "8px 0 16px" }}>Sign-in isn't configured yet.</p>
          <Link href="/dashboard" className="btn">Open console</Link>
        </div>
      )}
    </div>
  );
}
