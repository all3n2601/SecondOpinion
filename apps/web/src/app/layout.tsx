import type { Metadata } from "next";
import AppFooter from "@/components/AppFooter";
import AppHeader from "@/components/AppHeader";
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
      <body className="flex min-h-screen flex-col antialiased">
        <a
          href="#content"
          className="sr-only rounded-md bg-white px-4 py-2 text-sm font-semibold text-slate-900 focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800"
        >
          Skip to content
        </a>
        <AuditProvider>
          <AppHeader />
          <ResearchBanner />
          <StepNav />
          <div id="content" tabIndex={-1} className="flex-1 focus:outline-none">
            {children}
          </div>
          <AppFooter />
        </AuditProvider>
      </body>
    </html>
  );
}
