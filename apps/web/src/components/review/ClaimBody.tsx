import { ChevronRight, CircleCheck, CircleHelp, CircleX } from "lucide-react";
import type { ReactNode } from "react";
import { AiWordingStamp } from "@/components/AiStamp";
import SolidityExplained from "@/components/SolidityExplained";
import VerdictBadge from "@/components/VerdictBadge";
import ClaimChart from "@/components/review/ClaimChart";
import { CauseNote, PartLabel, RawNumbers, readingTargets, RestsOnBar, StoryFindings, TriedList } from "@/components/review/Insights";
import { CodeBlock, CorrectedWording, RobustnessLine, SampleIds, SkepticLine } from "@/components/review/sections";
import { causeTeaser, diagnose, restsOn, restsTeaser, robustnessTeaser } from "@/lib/insights";
import { STORY_VERDICT_WORDS } from "@/lib/narrate";
import { countText, finalVerdict, formatCount, SOLIDITY_LABEL, VERDICT_LABEL } from "@/lib/review";
import type { ClaimResult, RoleView, Verdict } from "@/lib/types";
import { focusRing } from "@/lib/ui";

// A claim row reads the same way in every view: the answer, one chart, then folded detail. The review form
// that follows is ReviewForm's. The view decides how plain the words are and which folds exist and start open.

type Sentence = { text: string; ai: boolean };

/** Plain words for a verdict, for readers with little data background (story view, story overview). */
export const STORY_WORDS: Record<Verdict, { label: string; icon: typeof CircleCheck; ink: string; fill: string }> = {
  supported: { label: STORY_VERDICT_WORDS.supported, icon: CircleCheck, ink: "text-supported", fill: "bg-supported" },
  contradicted: { label: STORY_VERDICT_WORDS.contradicted, icon: CircleX, ink: "text-contradicted", fill: "bg-contradicted" },
  insufficient_evidence: { label: STORY_VERDICT_WORDS.insufficient_evidence, icon: CircleHelp, ink: "text-insufficient", fill: "bg-insufficient" },
};

/** The narrated sentence, with the AI marker when the AI helper chose the words. */
function Narrated({ sentence, className }: { sentence: Sentence; className: string }) {
  if (!sentence.text) return null;
  return (
    <div className={className}>
      <p>{sentence.text}</p>
      {sentence.ai && (
        <p className="mt-1.5">
          <AiWordingStamp />
        </p>
      )}
    </div>
  );
}

// ---- Folds ----

interface FoldSpec {
  key: string;
  title: string;
  /** One line a closed fold still shows. */
  teaser: string | null;
  open: boolean;
  content: ReactNode;
}

function Folds({ folds, mono = false }: { folds: (FoldSpec | null)[]; mono?: boolean }) {
  const shown = folds.filter((f): f is FoldSpec => f !== null);
  if (!shown.length) return null;
  return (
    <div className="mt-5 border-b border-rule">
      {shown.map((f) => (
        <details key={f.key} open={f.open} className="group border-t border-rule">
          <summary
            className={`flex min-h-11 cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-0.5 rounded-control py-2 [&::-webkit-details-marker]:hidden ${focusRing}`}
          >
            <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
              <ChevronRight aria-hidden="true" className="size-4 shrink-0 text-ink-soft transition-transform group-open:rotate-90" />
              {f.title}
            </span>
            {f.teaser && <span className={`num text-sm text-ink-soft ${mono ? "font-mono" : ""}`}>{f.teaser}</span>}
          </summary>
          <div className="pb-4 pl-5.5">{f.content}</div>
        </details>
      ))}
    </div>
  );
}

/** What the number rests on, for the claim or the first part that has it. */
function restsFold(result: ClaimResult, open: boolean): FoldSpec | null {
  const target = readingTargets(result).find((t) => restsOn(t.result));
  const rests = target && restsOn(target.result);
  if (!target || !rests) return null;
  return {
    key: "rests",
    title: "What the number rests on",
    teaser: restsTeaser(rests),
    open,
    content: (
      <>
        <PartLabel label={target.label} />
        <div className={target.label ? "mt-2" : undefined}>
          <RestsOnBar rests={rests} />
        </div>
      </>
    ),
  };
}

/** Where a contradicted figure might come from, for the claim or the first part that has it. */
function causeFold(result: ClaimResult, open: boolean): FoldSpec | null {
  const target = readingTargets(result).find((t) => diagnose(t.result));
  const diagnosis = target && diagnose(target.result);
  if (!target || !diagnosis) return null;
  return {
    key: "cause",
    title: "Where the report's figure might come from",
    teaser: causeTeaser(diagnosis),
    open,
    content: (
      <>
        <PartLabel label={target.label} />
        <div className={target.label ? "mt-2" : undefined}>
          <CauseNote diagnosis={diagnosis} />
          <TriedList diagnosis={diagnosis} />
        </div>
      </>
    ),
  };
}

/**
 * Robustness, skeptic tests and corrected wording. With no recount and no skeptic test, only the corrected
 * wording (when the ladder changed anything) under its own title; null when there is nothing to say.
 */
function robustnessFold(result: ClaimResult, open: boolean): FoldSpec | null {
  const corrected = result.ladder.some((s) => s.struck || s.inserted);
  if (!result.variants.length && !result.skeptic) {
    if (!corrected) return null;
    return {
      key: "corrected",
      title: "Corrected wording",
      teaser: null,
      open,
      content: (
        <p className="max-w-prose font-serif text-base text-ink">
          <CorrectedWording result={result} />
        </p>
      ),
    };
  }
  return {
    key: "robustness",
    title: "Robustness and skeptic tests",
    teaser: robustnessTeaser(result) ?? SOLIDITY_LABEL[result.solidity],
    open,
    content: (
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_minmax(0,1fr)]">
        {corrected && (
          <>
            <dt className="font-semibold text-ink">Corrected wording</dt>
            <dd className="font-serif text-base text-ink">
              <CorrectedWording result={result} />
            </dd>
          </>
        )}
        <dt className="font-semibold text-ink">Robustness</dt>
        <dd className="num text-ink">
          <RobustnessLine result={result} full />
        </dd>
        <dt className="font-semibold text-ink">Skeptic tests</dt>
        <dd className="num text-ink">
          <SkepticLine result={result} />
        </dd>
      </dl>
    ),
  };
}

function SampleIdList({ result }: { result: ClaimResult }) {
  const ids = result.fact?.sample_ids ?? [];
  return (
    <div
      role="region"
      aria-label={`Sample IDs for ${result.claim.id}`}
      tabIndex={0}
      className={`max-h-60 overflow-y-auto rounded-control border border-rule bg-wash p-3 text-sm text-ink ${focusRing}`}
    >
      <SampleIds result={result} limit={ids.length} />
    </div>
  );
}

function sampleIdsFold(result: ClaimResult, open: boolean): FoldSpec | null {
  const ids = result.fact?.sample_ids ?? [];
  if (!ids.length) return null;
  return { key: "ids", title: "Sample IDs", teaser: formatCount(ids.length), open, content: <SampleIdList result={result} /> };
}

function codeFold(result: ClaimResult, open: boolean): FoldSpec | null {
  if (!result.fact?.code) return null;
  return { key: "code", title: "Code", teaser: null, open, content: <CodeBlock result={result} /> };
}

/** Sample IDs and code together, for views where neither is the point. */
function codeAndIdsFold(result: ClaimResult): FoldSpec | null {
  const ids = sampleIdsFold(result, false);
  const code = codeFold(result, false);
  if (!ids && !code) return null;
  return {
    key: "code-ids",
    title: "Code and sample IDs",
    teaser: ids ? `${ids.teaser} sample IDs` : null,
    open: false,
    content: (
      <div className="space-y-3">
        {ids && <SampleIdList result={result} />}
        <CodeBlock result={result} />
      </div>
    ),
  };
}

// ---- Views ----

function StoryBody({ result, sentence }: { result: ClaimResult; sentence: Sentence }) {
  const final = finalVerdict(result);
  const { label, icon: Icon, ink } = STORY_WORDS[final];
  return (
    <div>
      <p className={`inline-flex items-center gap-1.5 text-sm font-semibold ${ink}`}>
        <Icon aria-hidden="true" className="size-4 shrink-0" strokeWidth={2.25} />
        {label}
        {final !== result.verdict && <span className="font-medium text-ink-soft">(changed by a reviewer)</span>}
      </p>
      <blockquote className="reported mt-2 max-w-prose text-ink">
        <span aria-hidden="true">&ldquo;</span>
        {result.claim.text}
        <span aria-hidden="true">&rdquo;</span>
      </blockquote>
      <Narrated sentence={sentence} className="mt-3 max-w-prose text-lg leading-relaxed text-ink" />
      <ClaimChart result={result} plain />
      <StoryFindings result={result} />
    </div>
  );
}

/** Badge and solidity chip, the claim, then the answer sentence. */
function Answer({ result, sentence, size }: { result: ClaimResult; sentence: Sentence; size?: "sm" }) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <VerdictBadge verdict={result.verdict} size={size} />
        <SolidityExplained result={result} />
      </div>
      <blockquote className="reported mt-3 max-w-prose text-ink">{result.claim.text}</blockquote>
      <Narrated sentence={sentence} className="mt-2 max-w-prose text-ink" />
    </>
  );
}

function ChecklistBody({ result, sentence }: { result: ClaimResult; sentence: Sentence }) {
  return (
    <div>
      <Answer result={result} sentence={sentence} />
      <ClaimChart result={result} plain={false} />
      <Folds folds={[restsFold(result, false), causeFold(result, false), robustnessFold(result, false)]} />
    </div>
  );
}

function EvidenceBody({ result, sentence }: { result: ClaimResult; sentence: Sentence }) {
  return (
    <div>
      <Answer result={result} sentence={sentence} size="sm" />
      <ClaimChart result={result} plain={false} />
      <Folds folds={[restsFold(result, true), causeFold(result, true), robustnessFold(result, false), codeAndIdsFold(result)]} />
    </div>
  );
}

function RawBody({ result, sentence }: { result: ClaimResult; sentence: Sentence }) {
  const final = finalVerdict(result);
  const hasReadings = readingTargets(result).length > 0;
  const numbers: FoldSpec | null = hasReadings
    ? { key: "numbers", title: "Numbers", teaser: null, open: true, content: <RawNumbers result={result} /> }
    : null;
  return (
    <div className="text-sm">
      <p className="text-ink">{result.claim.text}</p>
      <dl className="mt-4 grid items-center gap-x-6 gap-y-2 font-mono sm:grid-cols-[max-content_minmax(0,1fr)]">
        <dt className="text-ink-soft">verdict</dt>
        <dd className="text-ink">
          {VERDICT_LABEL[result.verdict]}
          {final !== result.verdict && ` (overridden to ${VERDICT_LABEL[final]})`}
        </dd>
        {!hasReadings && (
          <>
            <dt className="text-ink-soft">count</dt>
            <dd className="num text-ink">{countText(result.fact) ?? "none"}</dd>
          </>
        )}
        <dt className="text-ink-soft">summary</dt>
        <dd className="text-ink">
          <span className="break-words">{sentence.text}</span>
          {sentence.ai && (
            <span className="mt-1 block font-sans">
              <AiWordingStamp />
            </span>
          )}
        </dd>
      </dl>
      <Folds folds={[numbers, sampleIdsFold(result, true), codeFold(result, true)]} mono />
    </div>
  );
}

/** What a claim row shows above the Accept / Override form, worded for the viewer's role. */
export default function ClaimBody({ view, result, sentence }: { view: RoleView; result: ClaimResult; sentence: Sentence }) {
  switch (view) {
    case "story":
      return <StoryBody result={result} sentence={sentence} />;
    case "checklist":
      return <ChecklistBody result={result} sentence={sentence} />;
    case "evidence":
      return <EvidenceBody result={result} sentence={sentence} />;
    case "raw":
      return <RawBody result={result} sentence={sentence} />;
  }
}
