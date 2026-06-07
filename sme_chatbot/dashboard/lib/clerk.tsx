"use client";

/**
 * Feature-flagged Clerk integration.
 *
 * Auth is only active when NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is set (in
 * Netlify). Until then the dashboard runs open, so deploys never break while
 * keys are being provisioned. `clerkEnabled` is inlined at build time.
 */

import type { ReactNode } from "react";
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";

export const clerkEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

/** Top-bar auth control: user avatar when signed in, sign-in button otherwise. */
export function AuthControls() {
  if (!clerkEnabled) return null;
  return (
    <>
      <SignedIn>
        <UserButton afterSignOutUrl="/" appearance={{ elements: { avatarBox: { width: 32, height: 32 } } }} />
      </SignedIn>
      <SignedOut>
        <SignInButton mode="modal">
          <button className="btn btn-sm">Sign in</button>
        </SignInButton>
      </SignedOut>
    </>
  );
}

/** Marketing-page CTA that routes to the dashboard (sign-in handled by middleware). */
export function MaybeSignedOut({ children }: { children: ReactNode }) {
  if (!clerkEnabled) return <>{children}</>;
  return <SignedOut>{children}</SignedOut>;
}
