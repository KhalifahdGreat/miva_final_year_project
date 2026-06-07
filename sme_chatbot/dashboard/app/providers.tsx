"use client";

import type { ReactNode } from "react";
import { ClerkProvider } from "@clerk/nextjs";
import { ToastProvider } from "@/components/ui";
import { TenantProvider } from "@/lib/tenant";
import { clerkEnabled } from "@/lib/clerk";

export function Providers({ children }: { children: ReactNode }) {
  const tree = (
    <ToastProvider>
      <TenantProvider>{children}</TenantProvider>
    </ToastProvider>
  );
  return clerkEnabled ? (
    <ClerkProvider
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
