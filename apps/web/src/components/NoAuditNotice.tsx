"use client";

import Link from "next/link";
import { useState } from "react";
import { useAudit } from "@/lib/audit-context";
import type { AuditResult } from "@/lib/types";
import { buttonPrimary, buttonSecondary, panel } from "@/lib/ui";

const DEV = process.env.NODE_ENV === "development";

/** Shown on /board, /review and /decision before any audit exists. */
export default function NoAuditNotice() {
  const { setAudit } = useAudit();
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

  return (
    <section aria-labelledby="no-audit-title" className={`${panel} px-6 py-12 text-center`}>
      <div
        aria-hidden="true"
        className="mx-auto grid size-12 place-items-center rounded-full border border-slate-200 bg-slate-50 text-xl text-slate-500"
      >
        ∅
      </div>
      <h2 id="no-audit-title" className="mt-4 text-base font-semibold text-slate-900">
        No audit yet
      </h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-slate-600">
        Audit a report first. Add the report and the data on the Start screen, then run the audit.
      </p>
      <Link href="/" className={`${buttonPrimary} mt-5`}>
        Go to Start
      </Link>
      {DEV && (
        <div className="mx-auto mt-8 max-w-md border-t border-dashed border-slate-300 pt-5 text-sm">
          <p className="text-slate-600">
            Development only: load the hand-made expected result for the practice report (not computed from data).
          </p>
          <button type="button" onClick={loadSample} className={`${buttonSecondary} mt-3`}>
            Load practice sample
          </button>
          {error && (
            <p role="alert" className="mt-2 text-red-800">
              {error}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
