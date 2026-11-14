"use client";

import {
  CircleAlert,
  CircleCheck,
  Database,
  Download,
  FileText,
  LoaderCircle,
  Play,
  RotateCcw,
  UserCheck,
} from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import ClaimVsData from "@/components/ClaimVsData";
import LadderText, { ladderChanges } from "@/components/LadderText";
import MarkedReport from "@/components/MarkedReport";
import SolidityTag from "@/components/SolidityTag";
import VerdictBadge from "@/components/VerdictBadge";
import { EASE } from "@/components/landing/motion";
import { exportAudit, suggestDecision } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { actionSummary, DECISION_HEADLINE } from "@/lib/decision-report";
import { download } from "@/lib/download";
import { renderNarration } from "@/lib/narrate";
import { markReport, type MarkSegment } from "@/lib/report-marks";
import { finalVerdict, keyNumber, plural, unreviewedIds, VERDICTS } from "@/lib/review";
import { agreedReason } from "@/lib/storyboard";
import type { AuditResult, Claim, ClaimResult, DecisionSuggestion, Verdict } from "@/lib/types";
import { buttonPrimary, buttonQuiet, buttonSecondary, focusRing } from "@/lib/ui";

// ---- Shared pieces ---------------------------------------------------------------------------------------------

/** The scene's heading and one sentence on what is happening, in the tool's voice. */
export function SceneTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="max-w-[46rem]">
      <h2 className="text-3xl font-semibold tracking-tight text-ink sm:text-[2.5rem] sm:leading-[1.1]">{title}</h2>
      {children && <p className="mt-3 text-lg text-ink-soft">{children}</p>}
    </div>
  );
}

/** One thing that arrives on its beat. It keeps its room before then, so nothing below it jumps. */
export function Beat({ show, children, className }: { show: boolean; children: ReactNode; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={false}
      animate={{ opacity: show ? 1 : 0, y: show ? 0 : 10 }}
      transition={{ duration: 0.45, ease: EASE }}
      aria-hidden={!show || undefined}
      inert={!show || undefined}
    >
      {children}
    </motion.div>
  );
}

function N({ children }: { children: ReactNode }) {
  return <span className="num font-mono font-medium">{children}</span>;
}

function Waiting({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-ink-soft">
      <LoaderCircle aria-hidden="true" className="size-5 animate-spin" />
      {children}
    </p>
  );
}

const TALLY: Record<Verdict, { words: string; fill: string }> = {
  supported: { words: "supported", fill: "bg-supported" },
  contradicted: { words: "contradicted", fill: "bg-contradicted" },
  insufficient_evidence: { words: "need more evidence", fill: "bg-insufficient" },
};

function Tally({ claims, final = false }: { claims: ClaimResult[]; final?: boolean }) {
  const counts = VERDICTS.map((v) => ({
    verdict: v,
    n: claims.filter((c) => (final ? finalVerdict(c) : c.verdict) === v).length,
  }));
  return (
    <div className="grid gap-3">
      <div aria-hidden="true" className="flex h-3 gap-0.5 overflow-hidden rounded-stamp bg-wash">
        {counts.map(({ verdict, n }) =>
          n > 0 ? <span key={verdict} className={TALLY[verdict].fill} style={{ flexGrow: n, flexBasis: 0 }} /> : null,
        )}
      </div>
      <ul aria-label="Claims by verdict" className="flex flex-wrap gap-x-5 gap-y-2">
        {counts.map(({ verdict, n }) => (
          <li key={verdict} className="flex items-center gap-2">
            <VerdictBadge verdict={verdict} size="sm" />
            <span className="text-ink">
              <N>{n}</N>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ErrorLine({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="mt-6 flex max-w-prose flex-wrap items-start gap-x-4 gap-y-2">
      <p className="flex items-start gap-2 font-medium text-contradicted">
        <CircleAlert aria-hidden="true" className="mt-1 size-4 shrink-0" />
        <span>{message}</span>
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry} className={buttonSecondary}>
          <RotateCcw aria-hidden="true" className="size-4" />
          Try again
        </button>
      )}
    </div>
  );
}

// ---- Cover -----------------------------------------------------------------------------------------------------

export function CoverScene({
  hasAudit,
  onPractice,
  onCurrent,
}: {
  hasAudit: boolean;
  onPractice: () => void;
  onCurrent: () => void;
}) {
  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:items-center">
      <div>
        <SceneTitle title="Watch an audit, start to finish">
          SecondOpinion reads a research report, recounts every number it states from the data, and marks what holds.
          This plays the whole audit as it runs.
        </SceneTitle>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={onPractice}
            className={`${buttonPrimary} min-h-12 px-6 text-base active:scale-[0.98]`}
            autoFocus
          >
            <Play aria-hidden="true" className="size-5" />
            Play the practice audit
          </button>
          {hasAudit && (
            <button type="button" onClick={onCurrent} className={`${buttonSecondary} min-h-12 px-6 text-base`}>
              Play the audit already in this tab
            </button>
          )}
        </div>
        <p className="mt-3 text-sm text-ink-faint">
          {hasAudit ? "The practice audit replaces the one in this tab. " : ""}
          Space pauses, the arrow keys step through.
        </p>
      </div>
      <ol className="grid gap-4 border-l-2 border-rule pl-6">
        {[
          ["It reads the report", "and picks out each sentence the data can check."],
          ["It recounts the data", "with ordinary code, then says what holds and writes the honest wording."],
          ["You confirm and sign off", "with one click each. A person makes every final call."],
        ].map(([head, rest], i) => (
          <li key={head} className="flex gap-3">
            <span
              aria-hidden="true"
              className="num grid size-8 shrink-0 place-items-center rounded-full border border-rule-strong bg-sheet text-sm font-semibold text-ink-soft"
            >
              {i + 1}
            </span>
            <p className="pt-1 text-ink-soft">
              <span className="font-semibold text-ink">{head}</span> {rest}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ---- The report ------------------------------------------------------------------------------------------------

/** Markdown emphasis and code marks, dropped for reading aloud on screen. */
const plainText = (s: string) => s.replace(/[*_`]+/g, "");

export function ReportScene({
  reportText,
  claims,
  beat,
  reading,
  error,
  onRetry,
}: {
  reportText: string;
  claims: Claim[];
  beat: number;
  reading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const marked = reportText.trim() ? markReport(reportText, claims) : null;
  // Beat 0 shows the report; beat n lights up the nth claim.
  const order = new Map(claims.map((c, i) => [c.id, i + 1]));
  const lit = (id: string) => (order.get(id) ?? Infinity) <= beat;
  const found = Math.min(beat, claims.length);

  const segment = (s: MarkSegment, i: number) =>
    s.kind === "text" ? (
      <span key={i}>{plainText(s.text)}</span>
    ) : (
      <mark
        key={i}
        className={`rounded-sm px-0.5 text-ink transition-colors duration-500 ${
          lit(s.claimId) ? "bg-blush-tint underline decoration-pen decoration-2 underline-offset-4" : "bg-transparent"
        }`}
      >
        {plainText(s.text)}
        <span
          className={`ml-1.5 inline-block rounded-stamp border px-1.5 align-middle font-mono text-xs not-italic transition-opacity duration-500 ${
            lit(s.claimId) ? "border-pen text-pen opacity-100" : "border-transparent opacity-0"
          }`}
        >
          {s.claimId}
        </span>
      </mark>
    );

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-12">
      <div>
        <SceneTitle title="It reads the report">
          Every sentence is read in order. The ones that state something the data can check are picked out as claims.
        </SceneTitle>
        <div aria-live="polite" className="mt-6 text-ink">
          {reading ? (
            <Waiting>Reading the report…</Waiting>
          ) : claims.length > 0 ? (
            <p className="text-lg">
              <N>{found}</N> of <N>{claims.length}</N> checkable {claims.length === 1 ? "claim" : "claims"} found
            </p>
          ) : null}
        </div>
        {error && <ErrorLine message={error} onRetry={onRetry} />}
      </div>
      <article
        aria-label="The report"
        className="max-h-[58dvh] overflow-y-auto rounded-panel border border-rule bg-sheet p-6 font-serif text-lg leading-relaxed sm:p-8"
      >
        {!marked ? (
          <Waiting>Opening the report…</Waiting>
        ) : (
          marked.blocks.map((block, i) => {
            if (block.kind === "heading") {
              return (
                <h3 key={i} className="mb-4 font-sans text-xl font-semibold text-ink">
                  {plainText(block.text)}
                </h3>
              );
            }
            if (block.kind === "paragraph") {
              return (
                <p key={i} className="mb-4 text-ink-soft last:mb-0">
                  {block.segments.map(segment)}
                </p>
              );
            }
            if (block.kind === "table") {
              return (
                <div key={i} className="mb-4 font-mono text-sm">
                  {block.rows.map((row, r) => (
                    <p key={r}>{row.map(segment)}</p>
                  ))}
                </div>
              );
            }
            return (
              <pre key={i} className="mb-4 overflow-x-auto font-mono text-sm">
                {block.text}
              </pre>
            );
          })
        )}
      </article>
    </div>
  );
}

// ---- The data --------------------------------------------------------------------------------------------------

export function DataScene({
  audit,
  beat,
  error,
  onRetry,
}: {
  audit: AuditResult | null;
  beat: number;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-12">
      <div>
        <SceneTitle title="It recounts the data">
          Each claim is counted again from the data files the report describes, with ordinary code. Then the count is
          repeated eight other reasonable ways, to see if the answer holds.
        </SceneTitle>
        {error && <ErrorLine message={error} onRetry={onRetry} />}
      </div>
      <div className="grid gap-6" aria-live="polite">
        {!audit ? (
          !error && <Waiting>Checking every claim against the data…</Waiting>
        ) : (
          <>
            <Beat show={beat >= 0}>
              <p className="flex items-center gap-3 text-xl text-ink">
                <Database aria-hidden="true" className="size-6 shrink-0 text-pen" />
                <span>
                  Release <N>{audit.release.name}</N>, {plural(audit.release.files.length, "file", "files")}, each
                  fingerprinted
                </span>
              </p>
            </Beat>
            <Beat show={beat >= 1}>
              <ul
                aria-label="Files and checksums"
                className="divide-y divide-rule overflow-hidden rounded-panel border border-rule bg-sheet"
              >
                {audit.release.files.map((f) => (
                  <li key={f.file} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 px-4 py-2">
                    <span className="flex items-center gap-2 font-mono text-sm text-ink">
                      <FileText aria-hidden="true" className="size-4 shrink-0 text-ink-faint" />
                      {f.file}
                    </span>
                    <span className="font-mono text-xs text-ink-faint" title={f.sha256}>
                      sha256 {f.sha256.slice(0, 12)}…
                    </span>
                  </li>
                ))}
              </ul>
              {audit.notes.length > 0 && (
                <ul className="mt-3 space-y-1 text-sm text-ink-soft">
                  {audit.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              )}
            </Beat>
            <Beat show={beat >= 2}>
              <p className="mb-3 text-lg text-ink">
                {plural(audit.claims.length, "claim", "claims")} checked
              </p>
              <Tally claims={audit.claims} />
            </Beat>
          </>
        )}
      </div>
    </div>
  );
}

// ---- One claim -------------------------------------------------------------------------------------------------

export function ClaimScene({ result, beat, index, total }: { result: ClaimResult; beat: number; index: number; total: number }) {
  const { claim } = result;
  const changes = ladderChanges(result.ladder);
  return (
    <div>
      <p className="text-sm font-medium text-ink-soft">
        Claim <span className="num font-mono text-ink">{claim.id}</span>, {index + 1} of {total}
      </p>
      <blockquote className="mt-3 max-w-[52rem] border-l-4 border-pen pl-5 font-serif text-2xl leading-snug text-ink sm:text-[1.875rem]">
        {plainText(claim.original_text || claim.text)}
      </blockquote>

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:gap-12">
        <Beat show={beat >= 1} className="min-w-0">
          <h3 className="text-sm font-semibold text-ink-soft">What the data shows</h3>
          <div className="mt-2">
            <ClaimVsData result={result} />
          </div>
        </Beat>

        <div className="grid content-start gap-6">
          <Beat show={beat >= 2}>
            <h3 className="text-sm font-semibold text-ink-soft">Verdict</h3>
            <motion.div
              className="mt-2 inline-block origin-left"
              initial={false}
              animate={{ scale: beat >= 2 ? 1 : 1.25, rotate: beat >= 2 ? 0 : -4 }}
              transition={{ duration: 0.35, ease: EASE }}
            >
              <span className="inline-block text-lg [&>span]:px-3 [&>span]:py-1.5 [&>span]:text-base">
                <VerdictBadge verdict={result.verdict} />
              </span>
            </motion.div>
            <p className="mt-3 text-lg text-ink">{keyNumber(result)}</p>
            <div className="mt-3">
              <SolidityTag result={result} />
            </div>
          </Beat>

          <Beat show={beat >= 3}>
            <h3 className="text-sm font-semibold text-ink-soft">
              {changes ? "The wording the data supports" : "The wording"}
            </h3>
            <div className="mt-2 text-xl [&_.reported]:text-xl! [&_.reported]:leading-relaxed!">
              {changes ? (
                <LadderText segments={result.ladder} />
              ) : (
                <p className="text-ink">The sentence stands as written.</p>
              )}
            </div>
          </Beat>
        </div>
      </div>
    </div>
  );
}

// ---- Findings --------------------------------------------------------------------------------------------------

export function FindingsScene({ audit, beat }: { audit: AuditResult; beat: number }) {
  const plain = renderNarration("story", audit.claims, null).claims;
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-12">
      <div>
        <SceneTitle title="What it found">
          Every verdict comes from code counting the data. None of it is a guess, and nothing here is a clinical
          finding.
        </SceneTitle>
      </div>
      <div className="grid gap-8">
        <Beat show={beat >= 0}>
          <Tally claims={audit.claims} />
        </Beat>
        <Beat show={beat >= 1}>
          <ol className="divide-y divide-rule overflow-hidden rounded-panel border border-rule bg-sheet">
            {audit.claims.map((c) => (
              <li key={c.claim.id} className="grid gap-2 p-5 sm:grid-cols-[3rem_minmax(0,1fr)_auto] sm:items-start sm:gap-4">
                <span className="num font-mono font-semibold text-ink">{c.claim.id}</span>
                <p className="text-ink">{plain[c.claim.id]?.text || keyNumber(c)}</p>
                <VerdictBadge verdict={c.verdict} size="sm" />
              </li>
            ))}
          </ol>
        </Beat>
      </div>
    </div>
  );
}

// ---- Review: one click, by a person ----------------------------------------------------------------------------

export function ReviewScene({ audit, onDone }: { audit: AuditResult; onDone: () => void }) {
  const { setReview, role } = useAudit();
  const left = unreviewedIds(audit.claims);
  const done = left.length === 0;

  function acceptAll() {
    for (const c of audit.claims) {
      if (c.review === null) {
        setReview(c.claim.id, { decision: "accept", final_verdict: c.verdict, reason: "", reviewer_role: role });
      }
    }
    onDone();
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-12">
      <div>
        <SceneTitle title="A person confirms each verdict">
          The tool never has the last word. Accept its verdicts here, or override any of them with a reason on the
          Review screen. Both are kept.
        </SceneTitle>
        <div className="mt-8 flex flex-wrap items-center gap-3" aria-live="polite">
          {done ? (
            <p className="flex items-center gap-2 text-lg font-semibold text-supported">
              <CircleCheck aria-hidden="true" className="size-5" />
              Every verdict reviewed by {role}
            </p>
          ) : (
            <button type="button" onClick={acceptAll} className={`${buttonPrimary} min-h-12 px-6 text-base`} autoFocus>
              <UserCheck aria-hidden="true" className="size-5" />
              Accept {left.length === audit.claims.length ? "all" : "the remaining"} {plural(left.length, "verdict", "verdicts")}
            </button>
          )}
          {!done && (
            <Link href="/review" className={buttonQuiet}>
              Override one instead
            </Link>
          )}
        </div>
        {!done && <p className="mt-2 text-sm text-ink-faint">Reviewing as {role}.</p>}
      </div>
      <ol className="divide-y divide-rule overflow-hidden rounded-panel border border-rule bg-sheet">
        {audit.claims.map((c) => (
          <li key={c.claim.id} className="flex flex-wrap items-start gap-x-4 gap-y-2 p-5">
            <span className="num w-10 font-mono font-semibold text-ink">{c.claim.id}</span>
            <div className="min-w-0 flex-1">
              <p className="reported line-clamp-2 text-ink">{plainText(c.claim.text)}</p>
              <p className="mt-1 text-sm text-ink-soft">{keyNumber(c)}</p>
            </div>
            <div className="flex flex-col items-end gap-1.5">
              <VerdictBadge verdict={finalVerdict(c)} size="sm" />
              <span
                className={`flex items-center gap-1 text-xs font-medium transition-opacity duration-300 ${
                  c.review ? "text-supported opacity-100" : "opacity-0"
                }`}
              >
                <CircleCheck aria-hidden="true" className="size-3.5" />
                {c.review?.decision === "override" ? "Overridden" : "Accepted"}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ---- Decision: one click, by a person --------------------------------------------------------------------------

export function DecisionScene({ audit, onDone }: { audit: AuditResult; onDone: () => void }) {
  const { role, decision, setDecision } = useAudit();
  const [loaded, setLoaded] = useState<{ audit: AuditResult; suggestion?: DecisionSuggestion; error?: string } | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    suggestDecision(audit)
      .then((suggestion) => live && setLoaded({ audit, suggestion }))
      .catch((err: Error) => live && setLoaded({ audit, error: err.message }));
    return () => {
      live = false;
    };
  }, [audit]);
  const current = loaded?.audit === audit ? loaded : null;
  const suggestion = current?.suggestion ?? null;

  async function signOff() {
    if (!suggestion) return;
    const choice = { choice: suggestion.decision, reason: agreedReason(suggestion.rule), reviewer_role: role };
    setExporting(true);
    setExportError(null);
    try {
      setDecision({ ...choice, files: await exportAudit(audit, choice) });
      onDone();
    } catch (err) {
      setExportError(`${(err as Error).message} Nothing was exported.`);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-12">
      <div>
        {suggestion ? (
          <SceneTitle title={`The tool suggests: ${suggestion.decision}`}>{suggestion.rule}.</SceneTitle>
        ) : (
          <SceneTitle title="One decision for the report">
            The tool suggests a decision from the reviewed verdicts. A person signs it off.
          </SceneTitle>
        )}
        <div className="mt-8" aria-live="polite">
          {!current && <Waiting>Working out the suggested decision…</Waiting>}
          {current?.error && <ErrorLine message={`Could not get a suggestion: ${current.error}`} />}
          {suggestion &&
            (decision ? (
              <p className="flex items-center gap-2 text-lg font-semibold text-supported">
                <CircleCheck aria-hidden="true" className="size-5" />
                Signed off: {decision.choice}, by {decision.reviewer_role}
              </p>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={signOff}
                  disabled={exporting}
                  className={`${buttonPrimary} min-h-12 px-6 text-base`}
                  autoFocus
                >
                  {exporting ? (
                    <LoaderCircle aria-hidden="true" className="size-5 animate-spin" />
                  ) : (
                    <UserCheck aria-hidden="true" className="size-5" />
                  )}
                  {exporting ? "Recording…" : `Sign off: ${suggestion.decision}`}
                </button>
                <Link href="/decision" className={buttonQuiet}>
                  Choose a different decision
                </Link>
              </div>
            ))}
          {suggestion && !decision && (
            <p className="mt-2 text-sm text-ink-faint">Signing as {role}. This records the decision and builds the export.</p>
          )}
          {exportError && <ErrorLine message={exportError} />}
        </div>
      </div>

      {suggestion && (
        <div className="grid content-start gap-6 rounded-panel border border-rule bg-sheet p-6">
          <div>
            <h3 className="text-sm font-semibold text-ink">Why</h3>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-ink-soft marker:text-ink-faint">
              {suggestion.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
          <div className="border-t border-rule pt-5">
            <h3 className="text-sm font-semibold text-ink">Who must sign off</h3>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-ink-soft marker:text-ink-faint">
              {suggestion.sign_off.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

// ---- Result ----------------------------------------------------------------------------------------------------

export function ResultScene({ audit, onReplay }: { audit: AuditResult; onReplay: () => void }) {
  const { decision, reportText } = useAudit();
  if (!decision) return null;
  const files = decision.files;
  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <SceneTitle title="The report, after the decision">
          <span className="font-semibold text-ink">{decision.choice}.</span> {DECISION_HEADLINE[decision.choice]}{" "}
          {actionSummary(audit.claims, decision.choice)}.
        </SceneTitle>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => download("audit.json", JSON.stringify(files.audit_json, null, 2), "application/json")}
            className={buttonPrimary}
          >
            <Download aria-hidden="true" className="size-4" />
            Download audit.json
          </button>
          <button
            type="button"
            onClick={() => download("decision_record.md", files.decision_record_md, "text/markdown")}
            className={buttonSecondary}
          >
            <Download aria-hidden="true" className="size-4" />
            Decision record
          </button>
        </div>
      </div>
      {reportText.trim() && (
        <MarkedReport
          audit={audit}
          reportText={reportText}
          from="decision"
          decision={decision.choice}
          label="The report after this decision"
        />
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-rule pt-6">
        <Link href="/board" className={buttonSecondary}>
          Open the full audit board
        </Link>
        <button type="button" onClick={onReplay} className={`${buttonQuiet} ${focusRing}`}>
          <RotateCcw aria-hidden="true" className="size-4" />
          Watch it again
        </button>
      </div>
    </div>
  );
}
