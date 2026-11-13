"use client";

import Link from "next/link";
import Breadcrumb from "@/components/Breadcrumb";
import NoAuditNotice from "@/components/NoAuditNotice";
import ReviewForm from "@/components/ReviewForm";
import RolePicker from "@/components/RolePicker";
import { useAudit } from "@/lib/audit-context";
import { plural, unreviewedIds } from "@/lib/review";

export default function ReviewPage() {
  const { audit } = useAudit();
  const total = audit?.claims.length ?? 0;
  const left = audit ? unreviewedIds(audit.claims).length : 0;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <title>Review | SecondOpinion</title>
      <Breadcrumb items={[{ label: "Audit board", href: "/board" }, { label: "Review" }]} />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Review every verdict</h1>
          <p className="mt-2 max-w-2xl text-slate-700">
            Accept the tool&apos;s verdict or override it with a reason. Both verdicts are kept.
          </p>
        </div>
        <RolePicker />
      </div>

      {!audit ? (
        <div className="mt-8">
          <NoAuditNotice />
        </div>
      ) : (
        <>
          <p role="status" className="mt-6 font-medium">
            {total - left} of {total} reviewed
          </p>
          {total === 0 && <p className="mt-2 text-slate-700">The report had no claims to review.</p>}
          <div className="mt-4 space-y-6">
            {audit.claims.map((result) => (
              <ReviewForm key={result.claim.id} result={result} />
            ))}
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            {left === 0 ? (
              <Link
                href="/decision"
                className="rounded-lg bg-emerald-900 px-5 py-3 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-900"
              >
                Continue to decision
              </Link>
            ) : (
              <>
                <button
                  type="button"
                  disabled
                  aria-describedby="review-gate"
                  className="cursor-not-allowed rounded-lg bg-slate-300 px-5 py-3 font-medium text-slate-700"
                >
                  Continue to decision
                </button>
                <p id="review-gate" className="text-sm text-slate-700">
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
