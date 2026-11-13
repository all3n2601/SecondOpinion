"use client";

import { CircleAlert, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import ReleasePicker from "@/components/ReleasePicker";
import ReportUpload from "@/components/ReportUpload";
import { extractClaims } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { buttonSecondary } from "@/lib/ui";

/** The two-part form for your own report: the report, the data folder, then Find claims. */
export default function OwnReportForm() {
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
  const hasFolder = releaseDir.trim().length > 0;
  const missing = [!hasReport && "the report", !hasFolder && "the data folder"].filter(Boolean).join(" and ");

  return (
    <div className="divide-y divide-rule rounded-panel border border-rule bg-sheet">
      <div className="p-5 sm:p-6">
        <ReportUpload value={reportText} onChange={setReportText} />
      </div>
      <div className="p-5 sm:p-6">
        <ReleasePicker value={releaseDir} onChange={setReleaseDir} />
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 p-5 sm:p-6">
        <button
          type="button"
          onClick={findClaims}
          disabled={!hasReport || !hasFolder || finding}
          aria-describedby="find-claims-note"
          className={buttonSecondary}
        >
          {finding && <Loader2 aria-hidden="true" size={16} strokeWidth={1.75} className="motion-safe:animate-spin" />}
          {finding ? "Finding claims…" : "Find claims"}
        </button>
        <p id="find-claims-note" className="text-sm text-ink-soft">
          {missing ? `Add ${missing} to continue.` : ""}
        </p>
        <p aria-live="polite" className="basis-full font-medium text-contradicted">
          {error && (
            <span className="flex items-start gap-2">
              <CircleAlert aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0" />
              <span>{error}</span>
            </span>
          )}
        </p>
      </div>
    </div>
  );
}
