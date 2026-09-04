import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Lenny Growth Assistant",
  description: "A grounded assistant over Lenny's Podcast transcripts.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-paper text-ink antialiased">{children}</body>
    </html>
  );
}
