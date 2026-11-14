"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import StartOver from "@/components/StartOver";
import StepNav from "@/components/StepNav";
import Wordmark from "@/components/Wordmark";

/**
 * The audit's frame: the step rail on every screen except the front door. The landing page ("/") is not a
 * step, so it gets the whole width and no rail; the steps appear once you start an audit.
 */
export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/") {
    return (
      <div id="content" tabIndex={-1} className="min-w-0 focus:outline-none">
        {children}
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-[88rem] lg:grid-cols-[17.5rem_minmax(0,1fr)]">
      <header className="border-b border-rule bg-sheet/60 px-5 py-4 sm:px-8 lg:sticky lg:top-0 lg:h-dvh lg:self-start lg:border-r lg:border-b-0 lg:py-8 lg:pr-6 lg:pl-8">
        <Wordmark />
        <div className="mt-4 lg:mt-10">
          <StepNav />
          <div className="mt-3 lg:mt-6">
            <StartOver />
          </div>
        </div>
      </header>
      <div id="content" tabIndex={-1} className="min-w-0 focus:outline-none">
        {children}
      </div>
    </div>
  );
}
