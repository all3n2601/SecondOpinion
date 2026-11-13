import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SecondOpinion | Research Claim Auditor",
  description: "Trace research claims to their evidence and test how well they hold up.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
