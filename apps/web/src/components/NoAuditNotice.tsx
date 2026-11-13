"use client";

import Link from "next/link";
import { useState } from "react";
import { useAudit } from "@/lib/audit-context";
import type { AuditResult } from "@/lib/types";

const DEV = process.env.NODE_ENV === "development";

/** Shown on /review and /decision before any audit exists. */
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
    <section className="rounded-xl border border-slate-300 bg-white p-6">
      <h2 className="text-lg font-semibold">No audit yet</h2>
      <p className="mt-2 text-slate-700">
        Audit a report first:{" "}
        <Link href="/" className="text-emerald-900 underline underline-offset-4">
          go to Start
        </Link>
        .
      </p>
      {DEV && (
        <div className="mt-4 border-t border-dashed border-slate-300 pt-4 text-sm">
          <p className="text-slate-600">
            Development only: load the hand-made expected result for the practice report (not computed from data).
          </p>
          <button
            type="button"
            onClick={loadSample}
            className="mt-2 rounded-md border border-emerald-900 px-3 py-1.5 text-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-900"
          >
            Load practice sample
          </button>
          {error && (
            <p role="alert" className="mt-2 text-rose-800">
              {error}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
