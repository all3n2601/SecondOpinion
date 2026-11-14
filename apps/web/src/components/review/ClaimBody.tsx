import { CircleCheck, CircleHelp, CircleX } from "lucide-react";
import type { ReactNode } from "react";
import { AiWordingStamp } from "@/components/AiStamp";
import ClaimVsData from "@/components/ClaimVsData";
import SolidityExplained from "@/components/SolidityExplained";
import VerdictBadge from "@/components/VerdictBadge";
import {
  CodeFor,
  CorrectedWording,
  RobustnessLine,
  SampleIds,
  SkepticLine,
} from "@/components/review/sections";
import { countText, finalVerdict, formatCount, keyNumber, VERDICT_LABEL } from "@/lib/review";
import type { ClaimResult, RoleView, Verdict } from "@/lib/types";
import { focusRing } from "@/lib/ui";

type Sentence = { text: string; ai: boolean };

/** Plain words for a verdict, for readers with little data background (story view, story overview). */
export const STORY_WORDS: Record<Verdict, { label: string; icon: typeof CircleCheck; ink: string; fill: string }> = {
  supported: { label: "Held up", icon: CircleCheck, ink: "text-supported", fill: "bg-supported" },
  contradicted: { label: "Wrong", icon: CircleX, ink: "text-contradicted", fill: "bg-contradicted" },
  insufficient_evidence: { label: "Can't tell", icon: CircleHelp, ink: "text-insufficient", fill: "bg-insufficient" },
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

function Facts({ children, mono = false }: { children: ReactNode; mono?: boolean }) {
  return (
    <dl
      className={`mt-4 grid items-center gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_minmax(0,1fr)] ${mono ? "font-mono" : ""}`}
    >
      {children}
    </dl>
  );
}

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
    </div>
  );
}

function ChecklistBody({ result, sentence }: { result: ClaimResult; sentence: Sentence }) {
  return (
    <div>
      <VerdictBadge verdict={result.verdict} />
      <blockquote className="reported mt-3 max-w-prose text-ink">{result.claim.text}</blockquote>
      <Narrated sentence={sentence} className="mt-2 max-w-prose text-sm text-ink-soft" />
      <Facts>
        <dt className="font-semibold text-ink">Key number</dt>
        <dd className="num text-ink">{keyNumber(result)}</dd>
        <dt className="font-semibold text-ink">Solidity</dt>
        <dd>
          <SolidityExplained result={result} />
        </dd>
      </Facts>
      <div className="mt-2">
        <ClaimVsData result={result} />
      </div>
    </div>
  );
}

function EvidenceBody({ result, sentence }: { result: ClaimResult; sentence: Sentence }) {
  const corrected = result.ladder.some((s) => s.struck || s.inserted);
  return (
    <div>
      <VerdictBadge verdict={result.verdict} size="sm" />
      <blockquote className="reported mt-3 max-w-prose text-ink">{result.claim.text}</blockquote>
      <Narrated sentence={sentence} className="mt-2 max-w-prose text-ink-soft" />
      <Facts>
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
      </Facts>
    </div>
  );
}

function RawBody({ result, sentence }: { result: ClaimResult; sentence: Sentence }) {
  const final = finalVerdict(result);
  const ids = result.fact?.sample_ids ?? [];
  return (
    <div className="text-sm">
      <p className="text-ink">{result.claim.text}</p>
      <Facts mono>
        <dt className="text-ink-soft">verdict</dt>
        <dd className="text-ink">
          {VERDICT_LABEL[result.verdict]}
          {final !== result.verdict && ` (overridden to ${VERDICT_LABEL[final]})`}
        </dd>
        <dt className="text-ink-soft">count</dt>
        <dd className="num text-ink">{countText(result.fact) ?? "none"}</dd>
        <dt className="text-ink-soft">summary</dt>
        <dd className="text-ink">
          <span className="break-words">{sentence.text}</span>
          {sentence.ai && (
            <span className="mt-1 block font-sans">
              <AiWordingStamp />
            </span>
          )}
        </dd>
      </Facts>
      <div className="mt-3 space-y-1">
        {ids.length > 0 && (
          <details>
            <summary
              className={`min-h-11 cursor-pointer rounded-control py-2 text-sm font-medium text-pen underline-offset-4 hover:underline ${focusRing}`}
            >
              Sample IDs for {result.claim.id} <span className="num font-mono">({formatCount(ids.length)})</span>
            </summary>
            <div
              role="region"
              aria-label={`Sample IDs for ${result.claim.id}`}
              tabIndex={0}
              className={`mt-1 max-h-60 overflow-y-auto rounded-control border border-rule bg-wash p-3 text-ink ${focusRing}`}
            >
              <SampleIds result={result} limit={ids.length} />
            </div>
          </details>
        )}
        <CodeFor result={result} />
      </div>
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
