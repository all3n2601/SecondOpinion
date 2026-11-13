import Link from "next/link";
import { formatFact, TYPE_LABEL, VERDICT_LABEL } from "@/lib/claim-format";
import type { ClaimResult } from "@/lib/types";
import { focusRing } from "@/lib/ui";
import LadderText, { ladderChanges } from "./LadderText";
import SolidityTag from "./SolidityTag";
import StatementLabel from "./StatementLabel";
import VerdictBadge from "./VerdictBadge";

const EDGE: Record<ClaimResult["verdict"], string> = {
  supported: "border-l-emerald-800",
  contradicted: "border-l-red-800",
  insufficient_evidence: "border-l-amber-700",
};

function Row({ label, kind, children }: { label: string; kind?: React.ComponentProps<typeof StatementLabel>["kind"]; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[11rem_1fr] sm:gap-4">
      <dt className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-600">
        {label}
        {kind && <StatementLabel kind={kind} />}
      </dt>
      <dd className="min-w-0 text-slate-900">{children}</dd>
    </div>
  );
}

/** One claim on the audit board: verdict, how solid it is, the Claim Ladder and the number behind it. */
export default function ClaimCard({ result }: { result: ClaimResult }) {
  const { claim, verdict, fact, review } = result;
  const headingId = `card-${claim.id}`;
  const rawNote = fact?.extra?.note;
  const same = (a: string, b: string) => a.trim().replace(/\.$/, "").toLowerCase() === b.trim().replace(/\.$/, "").toLowerCase();
  // The engine sometimes repeats the fact's note as the limitation; show it once.
  const note = typeof rawNote === "string" && !(result.limitation && same(rawNote, result.limitation)) ? rawNote : undefined;

  return (
    <article
      aria-labelledby={headingId}
      className={`rounded-2xl border border-l-8 border-emerald-900/15 bg-white p-6 ${EDGE[verdict]}`}
    >
      <header className="flex flex-wrap items-center gap-3">
        <h2 id={headingId} className="text-lg font-semibold">
          <span className="font-mono">{claim.id}</span>
          <span className="sr-only">: {VERDICT_LABEL[verdict]}</span>
        </h2>
        <span className="rounded-full border border-emerald-900/30 bg-emerald-50 px-2.5 py-0.5 text-sm font-medium text-emerald-950">
          {TYPE_LABEL[claim.type]}
        </span>
        <VerdictBadge verdict={verdict} />
        <SolidityTag result={result} />
      </header>

      <dl className="mt-5 grid gap-4">
        <Row label="The report says" kind="Reported">
          <p className="leading-7">{claim.text}</p>
        </Row>

        {verdict === "contradicted" && result.correct_value && (
          <Row label="The data shows" kind="Computed">
            <p className="text-lg font-semibold">{result.correct_value}</p>
          </Row>
        )}
        {verdict === "supported" && fact && (
          <Row label="The data shows" kind="Computed">
            <p className="text-lg font-semibold">{formatFact(fact, claim.type)}</p>
          </Row>
        )}
        {verdict === "insufficient_evidence" && (
          <Row label="Why we can’t check it">
            <p>
              This data cannot answer it.
              {result.missing_evidence && (
                <>
                  {" "}
                  <strong>Would need: {result.missing_evidence}.</strong>
                </>
              )}
            </p>
          </Row>
        )}

        {ladderChanges(result.ladder) && (
          <Row label="Honest wording" kind="Interpretation">
            <LadderText segments={result.ladder} />
          </Row>
        )}

        {(result.limitation || typeof note === "string") && (
          <Row label="Keep in mind">
            <ul className="list-disc space-y-1 pl-5 text-slate-700">
              {result.limitation && <li>{result.limitation}</li>}
              {typeof note === "string" && <li>{note}</li>}
            </ul>
          </Row>
        )}
      </dl>

      <footer className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
        <p className="text-sm text-slate-600">
          {review
            ? review.decision === "override"
              ? `Reviewed: overridden to “${VERDICT_LABEL[review.final_verdict]}” by ${review.reviewer_role}.`
              : `Reviewed: accepted by ${review.reviewer_role}.`
            : "Not reviewed yet."}
        </p>
        <Link
          href={`/board/${encodeURIComponent(claim.id)}`}
          className={`rounded-lg font-medium text-emerald-900 underline underline-offset-4 hover:text-emerald-700 ${focusRing}`}
        >
          Open evidence for {claim.id} →
        </Link>
      </footer>
    </article>
  );
}
