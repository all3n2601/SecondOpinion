import type { Metadata } from "next";
import ResearchBanner from "@/components/ResearchBanner";
import StepNav from "@/components/StepNav";
import { AuditProvider } from "@/lib/audit-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "SecondOpinion | Research Claim Auditor",
  description: "Trace research claims to their evidence and test how well they hold up.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <a
          href="#content"
          className="sr-only rounded-md bg-emerald-900 px-4 py-2 font-medium text-white focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-900"
        >
          Skip to content
        </a>
        <ResearchBanner />
        <StepNav />
        <div id="content" tabIndex={-1} className="focus:outline-none">
          <AuditProvider>{children}</AuditProvider>
        </div>
      </body>
    </html>
  );
}
