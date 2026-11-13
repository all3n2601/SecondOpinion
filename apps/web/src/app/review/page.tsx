"use client";

import Link from "next/link";
import NoAuditNotice from "@/components/NoAuditNotice";
import PageHeader from "@/components/PageHeader";
import RestoringState from "@/components/RestoringState";
import ReviewForm from "@/components/ReviewForm";
import RolePicker from "@/components/RolePicker";
import { useAudit } from "@/lib/audit-context";
import { plural, unreviewedIds } from "@/lib/review";
import { buttonPrimary, container } from "@/lib/ui";

export default function ReviewPage() {
  const { audit, restored } = useAudit();
  const total = audit?.claims.length ?? 0;
  const left = audit ? unreviewedIds(audit.claims).length : 0;
  const done = total - left;
  const percent = total ? Math.round((done / total) * 100) : 0;

  return (
    <main className={`${container} py-8`}>
      <title>Review | SecondOpinion</title>
      <PageHeader
        kicker="Step 4 of 5 · Review"
        title="Review every verdict"
        description="Accept the tool's verdict or override it with a reason. Both verdicts are kept."
        actions={<RolePicker />}
      />

      {!restored ? (
        <RestoringState />
      ) : !audit ? (
        <div className="mt-6">
          <NoAuditNotice />
        </div>
      ) : (
        <>
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <p role="status" className="text-sm font-semibold text-slate-900 tabular-nums">
              {done} of {total} reviewed
            </p>
            <div
              aria-hidden="true"
              className="h-2 min-w-[10rem] flex-1 overflow-hidden rounded-full bg-slate-200 sm:max-w-xs"
            >
              <div className="h-full rounded-full bg-emerald-700 transition-[width]" style={{ width: `${percent}%` }} />
            </div>
          </div>
          {total === 0 && <p className="mt-2 text-slate-700">The report had no claims to review.</p>}
          <div className="mt-4 space-y-5">
            {audit.claims.map((result) => (
              <ReviewForm key={result.claim.id} result={result} />
            ))}
          </div>

          <div className="sticky bottom-0 z-10 mt-6 -mx-6 border-t border-slate-200 bg-white/95 px-6 py-3 shadow-[0_-4px_12px_-8px_rgba(15,23,42,0.25)] backdrop-blur sm:mx-0 sm:rounded-md sm:border">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p id="review-gate" className="text-sm text-slate-700">
                {left === 0 ? "Every claim has a review." : `${plural(left, "claim still needs", "claims still need")} a review.`}
              </p>
              {left === 0 ? (
                <Link href="/decision" className={buttonPrimary}>
                  Continue to decision
                </Link>
              ) : (
                <button type="button" disabled aria-describedby="review-gate" className={buttonPrimary}>
                  Continue to decision
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
