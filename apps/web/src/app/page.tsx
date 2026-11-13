"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import ApiStatus from "@/components/ApiStatus";
import ReleasePicker from "@/components/ReleasePicker";
import ReportUpload from "@/components/ReportUpload";
import { extractClaims } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { buttonPrimary } from "@/lib/ui";

export default function StartPage() {
  const router = useRouter();
  const { reportText, setReportText, releaseDir, setReleaseDir, setExtract } = useAudit();
  const [finding, setFinding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function findClaims() {
    setFinding(true);
    setError(null);
    try {
      setExtract(await extractClaims(reportText));
      router.push("/claims");
    } catch (e) {
      setError((e as Error).message);
      setFinding(false);
    }
  }

  const hasReport = reportText.trim().length > 0;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold tracking-widest text-emerald-800 uppercase">
            SecondOpinion · Research Claim Auditor
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Can the data support this report?</h1>
          <p className="mt-3 max-w-2xl leading-7 text-slate-700">
            Give us a research report and the data it describes. We check every factual sentence against the data
            and show how solid each answer is.
          </p>
        </div>
        <ApiStatus />
      </header>

      <div className="mt-8 grid gap-6">
        <ReportUpload value={reportText} onChange={setReportText} />
        <ReleasePicker value={releaseDir} onChange={setReleaseDir} />

        <div className="flex flex-wrap items-center gap-4">
          <button type="button" onClick={findClaims} disabled={!hasReport || finding} className={buttonPrimary}>
            {finding ? "Finding claims…" : "Find claims →"}
          </button>
          {!hasReport && <p className="text-sm text-slate-600">Add a report first.</p>}
          <p aria-live="polite" className="font-medium text-red-800">
            {error && (
              <>
                <span aria-hidden="true">✕ </span>
                {error}
              </>
            )}
          </p>
        </div>
      </div>
    </main>
  );
}
