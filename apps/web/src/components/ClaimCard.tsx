import Link from "next/link";
import { Clock, FileSearch, Sparkles, UserCheck } from "lucide-react";
import { formatResultFact, resultTypeLabel, VERDICT_LABEL } from "@/lib/claim-format";
import { NOT_FULLY_READ, notFullyRead, notFullyReadText } from "@/lib/coverage";
import type { ClaimResult } from "@/lib/types";
import { buttonSecondary } from "@/lib/ui";
import { AiAssistedStamp } from "./AiStamp";
import LadderText, { ladderChanges } from "./LadderText";
import GlossaryTerm from "./GlossaryTerm";
import SolidityExplained from "./SolidityExplained";
import StatementLabel from "./StatementLabel";
import VerdictBadge from "./VerdictBadge";

// The 3px left edge in the verdict colour (the stamp and the word say the same thing, so colour is never alone).
const EDGE: Record<ClaimResult["verdict"], string> = {
  supported: "border-l-supported",
  contradicted: "border-l-contradicted",
  insufficient_evidence: "border-l-insufficient",
};

function Row({
  label,
  kind,
  children,
}: {
  label: string;
  kind?: React.ComponentProps<typeof StatementLabel>["kind"];
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[9.5rem_1fr] sm:gap-4">
      <dt className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-soft">
        {label}
        {kind && <StatementLabel kind={kind} />}
      </dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </div>
  );
}

/** One entry in the audit ledger: verdict, how solid it is, the Claim Ladder and the number behind it. */
export default function ClaimCard({ result }: { result: ClaimResult }) {
  const { claim, verdict, fact, review } = result;
  const headingId = `card-${claim.id}`;
  const rawNote = fact?.extra?.note;
  const same = (a: string, b: string) => a.trim().replace(/\.$/, "").toLowerCase() === b.trim().replace(/\.$/, "").toLowerCase();
  // The engine sometimes repeats the fact's note as the limitation; show it once.
  const note = typeof rawNote === "string" && !(result.limitation && same(rawNote, result.limitation)) ? rawNote : undefined;
  const edited = ladderChanges(result.ladder);

  return (
    <article
      aria-labelledby={headingId}
      className={`grid gap-4 border-l-[3px] p-5 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-6 sm:p-6 ${EDGE[verdict]}`}
    >
      {/* Margin column: who this is and how it came out. */}
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 sm:flex-col sm:items-start sm:gap-2.5">
        <h2 id={headingId} className="text-base font-semibold text-ink">
          <span className="font-mono">{claim.id}</span>
          <span className="sr-only">: {VERDICT_LABEL[verdict]}</span>
        </h2>
        <span className="text-sm text-ink-soft sm:order-last">{resultTypeLabel(result)}</span>
        <VerdictBadge verdict={verdict} />
        {result.ai_plan && <AiAssistedStamp />}
        <SolidityExplained result={result} />
      </header>

      {/* Main column: the sentence, then the facts behind it. */}
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-soft">
          {edited ? (
            <span>
              The report says, <GlossaryTerm term="claimLadder">with our edits</GlossaryTerm>
            </span>
          ) : (
            "The report says"
          )}
          <StatementLabel kind={edited ? "Interpretation" : "Reported"} />
        </div>
        <div className="mt-1.5">
          {edited ? <LadderText segments={result.ladder} /> : <p className="reported text-ink">{claim.text}</p>}
        </div>

        <dl className="mt-4 grid gap-3 border-t border-rule pt-4">
          {verdict === "contradicted" && result.correct_value && (
            <Row label="The data shows" kind="Computed">
              <p className="num font-mono text-base font-semibold">{result.correct_value}</p>
            </Row>
          )}
          {verdict === "supported" && fact && (
            <Row label="The data shows" kind="Computed">
              <p className="num font-mono text-base font-semibold">{formatResultFact(result)}</p>
            </Row>
          )}
          {verdict === "insufficient_evidence" && notFullyRead(result.claim) && (
            <Row label={NOT_FULLY_READ}>
              <p>{notFullyReadText(result)}</p>
            </Row>
          )}
          {verdict === "insufficient_evidence" && !notFullyRead(result.claim) && (
            <Row label="Why we can’t check it">
              <p>
                This data cannot answer it.
                {result.missing_evidence && (
                  <>
                    {" "}
                    <strong className="font-semibold">Would need: {result.missing_evidence}.</strong>
                  </>
                )}
              </p>
            </Row>
          )}

          {(result.limitation || typeof note === "string" || (result.notes?.length ?? 0) > 0) && (
            <Row label="Keep in mind">
              <ul className="space-y-1 text-ink-soft">
                {result.notes?.map((n) => <li key={n} className="font-medium text-ink">{n}</li>)}
                {result.limitation && <li>{result.limitation}</li>}
                {typeof note === "string" && <li>{note}</li>}
              </ul>
            </Row>
          )}
        </dl>

        {result.ai_plan && (
          <p className="mt-3 flex items-start gap-2 text-sm text-ink-soft">
            <Sparkles aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>The AI helper proposed how to test this; our code ran it on the release and set the verdict.</span>
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <p className="flex items-start gap-2 text-sm text-ink-soft">
            {review ? (
              <UserCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            ) : (
              <Clock aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            )}
            <span>
              {review
                ? review.decision === "override"
                  ? `Reviewed: overridden to “${VERDICT_LABEL[review.final_verdict]}” by ${review.reviewer_role}.`
                  : `Reviewed: accepted by ${review.reviewer_role}.`
                : "Not reviewed yet."}
            </span>
          </p>
          <Link href={`/board/${encodeURIComponent(claim.id)}`} className={buttonSecondary}>
            <FileSearch aria-hidden="true" className="size-4" />
            Open evidence for {claim.id}
          </Link>
        </div>
      </div>
    </article>
  );
}
