"use client";

import type { ReactNode } from "react";
import { ClerkProvider } from "@clerk/nextjs";
import { ToastProvider } from "@/components/ui";
import { TenantProvider } from "@/lib/tenant";
import { clerkEnabled } from "@/lib/clerk";

// Shared theme so every Clerk surface (sign-in, sign-up, user button, account
// modal) matches the dashboard's emerald design system.
const clerkAppearance = {
  variables: {
    colorPrimary: "#059669",
    colorText: "#0f172a",
    colorTextSecondary: "#64748b",
    colorBackground: "#ffffff",
    colorInputBackground: "#ffffff",
    colorInputText: "#0f172a",
    borderRadius: "10px",
    fontFamily: '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  },
  elements: {
    card: { boxShadow: "0 18px 40px rgba(15,23,42,0.14)", borderRadius: "16px" },
    formButtonPrimary: {
      textTransform: "none" as const,
      fontWeight: 600,
      boxShadow: "none",
    },
    headerTitle: { fontWeight: 700 },
    socialButtonsBlockButton: { borderRadius: "10px" },
  },
};

export function Providers({ children }: { children: ReactNode }) {
  const tree = (
    <ToastProvider>
      <TenantProvider>{children}</TenantProvider>
    </ToastProvider>
  );
  return clerkEnabled ? (
    <ClerkProvider
      appearance={clerkAppearance}
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      signInFallbackRedirectUrl="/dashboard"
      signUpFallbackRedirectUrl="/dashboard"
      afterSignOutUrl="/"
    >
      {tree}
    </ClerkProvider>
  ) : (
    tree
  );
}
