"use client";

import Link from "next/link";
import Breadcrumb from "@/components/Breadcrumb";
import NoAuditNotice from "@/components/NoAuditNotice";
import ReviewForm from "@/components/ReviewForm";
import RolePicker from "@/components/RolePicker";
import { useAudit } from "@/lib/audit-context";
import { plural, unreviewedIds } from "@/lib/review";
import { buttonPrimary, pageTitle, pageWidth } from "@/lib/ui";

export default function ReviewPage() {
  const { audit } = useAudit();
  const total = audit?.claims.length ?? 0;
  const left = audit ? unreviewedIds(audit.claims).length : 0;
  const done = total - left;

  return (
    <main className={pageWidth}>
      <title>Review | SecondOpinion</title>
      <Breadcrumb items={[{ label: "Audit board", href: "/board" }, { label: "Review" }]} />
      <h1 className={pageTitle}>Review every verdict</h1>
      <p className="mt-2 max-w-prose text-ink-soft">
        Accept the tool&apos;s verdict or override it with a reason. Both verdicts are kept.
      </p>
      <div className="mt-6">
        <RolePicker />
      </div>

      {!audit ? (
        <div className="mt-8">
          <NoAuditNotice />
        </div>
      ) : (
        <>
          <div className="mt-8">
            <p role="status" aria-live="polite" className="num text-base font-semibold text-ink">
              {done} of {total} reviewed
            </p>
            <div
              role="progressbar"
              aria-label="Claims reviewed"
              aria-valuemin={0}
              aria-valuemax={total}
              aria-valuenow={done}
              className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-wash"
            >
              <div
                className="h-full rounded-full bg-pen transition-[width] duration-200"
                style={{ width: total ? `${(done / total) * 100}%` : "0%" }}
              />
            </div>
          </div>
          {total === 0 && <p className="mt-4 text-ink-soft">The report had no claims to review.</p>}
          {total > 0 && (
            <div className="mt-6 divide-y divide-rule rounded-panel border border-rule bg-sheet">
              {audit.claims.map((result) => (
                <ReviewForm key={result.claim.id} result={result} />
              ))}
            </div>
          )}

          <div className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-3">
            {left === 0 ? (
              <Link href="/decision" className={buttonPrimary}>
                Continue to decision
              </Link>
            ) : (
              <>
                <button type="button" disabled aria-describedby="review-gate" className={buttonPrimary}>
                  Continue to decision
                </button>
                <p id="review-gate" className="text-sm text-ink-soft">
                  {plural(left, "claim still needs", "claims still need")} a review.
                </p>
              </>
            )}
          </div>
        </>
      )}
    </main>
  );
}
