import ClaimVsData from "@/components/ClaimVsData";
import { CountingStrip } from "@/components/review/Insights";
import { formatResultFact, VERDICT_LABEL } from "@/lib/claim-format";
import { countingRange, statedFigure } from "@/lib/insights";
import type { ClaimResult } from "@/lib/types";
import { sectionTitle } from "@/lib/ui";

/** The dot strip when the claim was counted several ways; null otherwise. */
function Strip({ result, plain }: { result: ClaimResult; plain: boolean }) {
  if (result.verdict === "insufficient_evidence") return null;
  const range = countingRange(result);
  if (!range) return null;
  return <CountingStrip range={range} stated={statedFigure(result)} verdict={result.verdict} plain={plain} />;
}

function partFinding(part: ClaimResult): string {
  if (part.verdict === "contradicted" && part.correct_value) return `: data shows ${part.correct_value}`;
  if (part.verdict === "supported" && part.fact) return `: ${formatResultFact(part)}`;
  if (part.verdict === "insufficient_evidence" && part.missing_evidence) return `: ${part.missing_evidence}`;
  return "";
}

/** A sentence with several checks: one line per part, each followed by its strip when it has one. */
function PartsChart({ result, plain }: { result: ClaimResult; plain: boolean }) {
  const parts = result.parts ?? [];
  return (
    <section aria-label="Each part of the sentence" className="mt-6">
      <h3 className={`${sectionTitle} text-base`}>Each part of the sentence</h3>
      <p className="mt-0.5 text-sm text-ink-soft">The sentence takes the verdict of its worst part.</p>
      <ul className="mt-2 divide-y divide-rule border-y border-rule">
        {parts.map((part) => (
          <li key={part.claim.id} className="py-3">
            <p className="grid gap-1 sm:grid-cols-[1fr_auto] sm:gap-4">
              <q className="reported text-ink">{part.claim.part_label || part.claim.text}</q>
              <span className="text-sm font-medium text-ink">
                {VERDICT_LABEL[part.verdict]}
                {partFinding(part)}
              </span>
            </p>
            <Strip result={part} plain={plain} />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The claim's one chart: the dot strip, the report-versus-data figure, or one line per part of the sentence. */
export default function ClaimChart({ result, plain }: { result: ClaimResult; plain: boolean }) {
  if (result.parts && result.parts.length > 1) return <PartsChart result={result} plain={plain} />;
  if (result.verdict !== "insufficient_evidence" && countingRange(result)) return <Strip result={result} plain={plain} />;
  return <ClaimVsData result={result} />;
}
