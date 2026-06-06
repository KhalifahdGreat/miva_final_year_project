import Link from "next/link";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <nav className="sidebar" aria-label="Dashboard navigation">
        <h3>Workspace</h3>
        <Link href="/dashboard">Overview</Link>
        <Link href="/dashboard/knowledge">Knowledge</Link>
        <Link href="/dashboard/conversations">Conversations</Link>
        <Link href="/dashboard/persona">Persona &amp; tone</Link>
        <Link href="/dashboard/channels">Channels</Link>
        <Link href="/dashboard/analytics">Analytics</Link>
      </nav>
      <main className="with-sidebar">{children}</main>
    </>
  );
}
