import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SME Chatbot — Admin",
  description: "Manage your multilingual customer-service bot.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
