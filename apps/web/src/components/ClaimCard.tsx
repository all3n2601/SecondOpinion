import Link from "next/link";
import { formatFact, TYPE_LABEL, VERDICT_LABEL } from "@/lib/claim-format";
import type { ClaimResult } from "@/lib/types";
import { buttonSecondary, chip, eyebrow, panel } from "@/lib/ui";
import LadderText, { ladderChanges } from "./LadderText";
import SolidityTag from "./SolidityTag";
import StatementLabel, { type StatementKind } from "./StatementLabel";
import VerdictBadge from "./VerdictBadge";

const EDGE: Record<ClaimResult["verdict"], string> = {
  supported: "before:bg-emerald-700",
  contradicted: "before:bg-red-700",
  insufficient_evidence: "before:bg-amber-500",
};

function Row({ label, kind, children }: { label: string; kind?: StatementKind; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 py-3.5 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-6">
      <dt className="flex flex-wrap items-center gap-2">
        <span className={eyebrow}>{label}</span>
        {kind && <StatementLabel kind={kind} />}
      </dt>
      <dd className="min-w-0 text-[0.95rem] text-slate-900">{children}</dd>
    </div>
  );
}

const same = (a: string, b: string) =>
  a.trim().replace(/\.$/, "").toLowerCase() === b.trim().replace(/\.$/, "").toLowerCase();

/** One claim on the audit board: verdict, how solid it is, the Claim Ladder and the number behind it. */
export default function ClaimCard({ result }: { result: ClaimResult }) {
  const { claim, verdict, fact, review } = result;
  const headingId = `card-${claim.id}`;
  const rawNote = fact?.extra?.note;
  // The engine sometimes repeats the fact's note as the limitation; show it once.
  const note = typeof rawNote === "string" && !(result.limitation && same(rawNote, result.limitation)) ? rawNote : undefined;

  return (
    <article
      aria-labelledby={headingId}
      className={`${panel} relative overflow-hidden before:absolute before:inset-y-0 before:left-0 before:w-1 ${EDGE[verdict]}`}
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50/70 px-5 py-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 id={headingId} className="font-mono text-sm font-bold text-slate-900">
            {claim.id}
            <span className="sr-only">: {VERDICT_LABEL[verdict]}</span>
          </h2>
          <span className={`${chip} border-slate-300 bg-white text-slate-700`}>{TYPE_LABEL[claim.type]}</span>
          <VerdictBadge verdict={verdict} />
          <SolidityTag result={result} />
        </div>
        <Link href={`/board/${encodeURIComponent(claim.id)}`} className={`${buttonSecondary} h-8 px-3 text-xs`}>
          Open evidence for {claim.id} →
        </Link>
      </header>

      <dl className="divide-y divide-slate-100 px-5">
        <Row label="The report says" kind="Reported">
          <p className="leading-7">{claim.text}</p>
        </Row>

        {verdict === "contradicted" && result.correct_value && (
          <Row label="The data shows" kind="Computed">
            <p className="text-xl font-semibold tracking-tight tabular-nums">{result.correct_value}</p>
          </Row>
        )}
        {verdict === "supported" && fact && (
          <Row label="The data shows" kind="Computed">
            <p className="text-xl font-semibold tracking-tight tabular-nums">{formatFact(fact, claim.type)}</p>
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

        {(result.limitation || note) && (
          <Row label="Keep in mind">
            <ul className="list-disc space-y-1 pl-5 text-slate-700">
              {result.limitation && <li>{result.limitation}</li>}
              {note && <li>{note}</li>}
            </ul>
          </Row>
        )}
      </dl>

      <footer className="flex items-center gap-2 border-t border-slate-200 px-5 py-2.5 text-xs text-slate-600">
        <span
          aria-hidden="true"
          className={`size-1.5 rounded-full ${review ? "bg-emerald-700" : "bg-slate-300"}`}
        />
        {review
          ? review.decision === "override"
            ? `Reviewed: overridden to “${VERDICT_LABEL[review.final_verdict]}” by ${review.reviewer_role}.`
            : `Reviewed: accepted by ${review.reviewer_role}.`
          : "Not reviewed yet."}
      </footer>
    </article>
  );
}
