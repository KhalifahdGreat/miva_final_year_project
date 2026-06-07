import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// Auth is feature-flagged: only enforce when a Clerk publishable key is
// configured. Otherwise this is a pass-through so the site keeps working
// before keys are provisioned.
const clerkEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

const isProtected = createRouteMatcher(["/dashboard(.*)"]);

const enforced = clerkMiddleware((auth, req) => {
  if (isProtected(req)) auth().protect();
});

export default clerkEnabled ? enforced : () => NextResponse.next();

export const config = {
  matcher: ["/((?!_next|.*\\.[\\w]+$|favicon.ico).*)"],
};
