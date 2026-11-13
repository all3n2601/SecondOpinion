"use client";

import { FileSearch } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useAudit } from "@/lib/audit-context";
import type { AuditResult } from "@/lib/types";
import { buttonSecondary, buttonQuiet, sectionTitle } from "@/lib/ui";

const DEV = process.env.NODE_ENV === "development";

/** Shown on /review and /decision before any audit exists. */
export default function NoAuditNotice() {
  const { setAudit, hydrated } = useAudit();
  const [error, setError] = useState<string | null>(null);

  async function loadSample() {
    try {
      const response = await fetch("/dev/practice_audit_result.json");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setAudit((await response.json()) as AuditResult);
    } catch (err) {
      setError(`Could not load the sample: ${(err as Error).message}`);
    }
  }

  // Until any stored audit has been restored we do not know that there is none, so show nothing
  // (a same-height placeholder keeps the layout from jumping when the real content arrives).
  if (!hydrated) return <div aria-hidden="true" className="min-h-40 max-w-prose" />;

  return (
    <section className="max-w-prose border-y border-rule py-6">
      <div className="flex items-start gap-3">
        <FileSearch aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ink-soft" />
        <div>
          <h2 className={sectionTitle}>No audit yet</h2>
          <p className="mt-1 text-ink-soft">
            There is nothing to show until a report has been checked against the data.
          </p>
          <Link href="/start" className={`${buttonSecondary} mt-4`}>
            Go to Start
          </Link>
        </div>
      </div>
      {DEV && (
        <div className="mt-6 border-t border-dashed border-rule-strong pt-4 text-sm">
          <p className="text-ink-soft">
            Development only: load the hand-made expected result for the practice report (not computed from data).
          </p>
          <button type="button" onClick={loadSample} className={`${buttonQuiet} mt-2 border border-pen/40`}>
            Load practice sample
          </button>
          {error && (
            <p role="alert" className="mt-2 text-contradicted">
              {error}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
