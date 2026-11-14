import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Newsreader } from "next/font/google";
import AppShell from "@/components/AppShell";
import ResearchBanner from "@/components/ResearchBanner";
import { AuditProvider } from "@/lib/audit-context";
import "./globals.css";

// UI in Plex Sans; the report's own sentences in Newsreader; data, IDs and code in Plex Mono.
const sans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex-sans", display: "swap" });
const serif = Newsreader({ subsets: ["latin"], style: ["normal", "italic"], variable: "--font-newsreader", display: "swap" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-plex-mono", display: "swap" });

export const metadata: Metadata = {
  title: "SecondOpinion | Research Claim Auditor",
  description: "Trace research claims to their evidence and test how well they hold up.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable} ${mono.variable}`}>
      <body className="min-h-dvh antialiased">
        <a
          href="#content"
          className="sr-only rounded-control bg-pen px-4 py-2 font-semibold text-white focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50"
        >
          Skip to content
        </a>
        <ResearchBanner />
        <AuditProvider>
          <AppShell>{children}</AppShell>
        </AuditProvider>
      </body>
    </html>
  );
}
