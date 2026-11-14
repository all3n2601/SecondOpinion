"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useSyncExternalStore } from "react";
import CodeBlock from "@/components/CodeBlock";
import LadderText from "@/components/LadderText";
import VerdictBadge from "@/components/VerdictBadge";
import { actionLabel, claimAction } from "@/lib/decision-report";
import { markReport, type MarkSegment, type ReportBlock } from "@/lib/report-marks";
import { evidenceHref, markAnchor, markIdFromHash, returnHref, type ReturnView } from "@/lib/report-nav";
import { finalVerdict } from "@/lib/review";
import type { AuditResult, ClaimResult, Decision, Verdict } from "@/lib/types";
import { buttonQuiet, focusRing, sectionTitle } from "@/lib/ui";

// A marked sentence: its verdict's tint behind it and a line under it. The stamp after it carries the icon and the
// word, so colour is never alone.
const MARK: Record<Verdict, string> = {
  supported: "bg-supported-tint decoration-supported",
  contradicted: "bg-contradicted-tint decoration-contradicted",
  insufficient_evidence: "bg-insufficient-tint decoration-insufficient",
};

// The ring that shows where you came back to. It fades as `data-flash` is removed; with reduced motion the global
// rule drops the transition, so it simply goes.
const FLASH = "transition-[box-shadow] duration-700 ease-out data-flash:ring-2 data-flash:ring-pen";
const FLASH_MS = 1600;

const HEADING_SIZE: Record<number, string> = { 1: "text-2xl", 2: "text-xl" };

// The mark to return to lives in the URL hash. Reload, Back and a "#mark-C2" link change it; our own
// replaceState (on click, just before leaving) fires no event, which is what we want.
function subscribeHash(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  window.addEventListener("popstate", onChange);
  return () => {
    window.removeEventListener("hashchange", onChange);
    window.removeEventListener("popstate", onChange);
  };
}
const readHash = () => window.location.hash;
const serverHash = () => "";

interface MarkContext {
  byId: Map<string, ClaimResult>;
  from: ReturnView;
  /** Set once a decision is recorded: each claim then shows what the decision does to it. */
  decision?: Decision;
  onOpen: (id: string) => void;
}

/** "Reworded, Contradicted, claim C2" after the sentence: seen as a stamp, heard as part of the link's name. */
function MarkStamp({ result, decision }: { result: ClaimResult; decision?: Decision }) {
  const overridden = result.review?.decision === "override";
  return (
    <span className="ml-1.5 inline-flex items-center gap-1.5 whitespace-nowrap align-middle font-sans text-xs leading-none not-italic">
      {decision && (
        <span className="font-semibold text-ink">
          <span className="sr-only">, </span>
          {actionLabel(claimAction(result, decision), decision)}
        </span>
      )}
      <span className="sr-only">, </span>
      <VerdictBadge verdict={finalVerdict(result)} size="sm" />
      {overridden && (
        <span className="text-ink-soft">
          <span className="sr-only">, </span>overridden
        </span>
      )}
      <span className="font-mono text-ink-soft">
        <span className="sr-only">, claim </span>
        {result.claim.id}
      </span>
    </span>
  );
}

/** The claim's words: as written, or with the Claim Ladder's rewrite when the decision rewrites it. */
function ClaimWords({ result, text, decision }: { result: ClaimResult; text: string; decision?: Decision }) {
  if (decision && claimAction(result, decision) === "rewritten") return <LadderText inline segments={result.ladder} />;
  return <>{text}</>;
}

// markReport marks each claim at most once, as one segment, so its element id is unique on the page.
function Segments({ segments, byId, from, decision, onOpen }: { segments: MarkSegment[] } & MarkContext) {
  return segments.map((segment, i) => {
    const result = segment.kind === "claim" ? byId.get(segment.claimId) : undefined;
    if (!result) return <Fragment key={i}>{segment.text}</Fragment>;
    const id = result.claim.id;
    return (
      <Link
        key={i}
        id={markAnchor(id)}
        href={evidenceHref(id, from)}
        onClick={() => onOpen(id)}
        className={`cursor-pointer rounded-stamp box-decoration-clone px-0.5 text-ink underline decoration-2 underline-offset-4 hover:decoration-[3px] ${MARK[finalVerdict(result)]} ${FLASH} ${focusRing}`}
      >
        <ClaimWords result={result} text={segment.text} decision={decision} />
        <MarkStamp result={result} decision={decision} />
      </Link>
    );
  });
}

function Block({ block, ...context }: { block: ReportBlock } & MarkContext) {
  switch (block.kind) {
    case "heading": {
      // One level down, so the page title stays the only h1.
      const Tag = `h${Math.min(block.level + 1, 6)}` as "h2" | "h3" | "h4" | "h5" | "h6";
      return (
        <Tag className={`font-serif font-semibold tracking-tight text-ink ${HEADING_SIZE[block.level] ?? "text-lg"}`}>
          {block.text}
        </Tag>
      );
    }
    case "paragraph":
      // A "\n" inside the text is a line break the report had (list items), so keep it.
      return (
        <p className="reported whitespace-pre-line text-ink">
          <Segments segments={block.segments} {...context} />
        </p>
      );
    case "table":
      return (
        <figure>
          <figcaption className="mb-1.5 text-sm text-ink-soft">Table, as written in the report</figcaption>
          {/* Long lines scroll inside this box, never the page. */}
          <div
            role="region"
            aria-label="Table, as written in the report"
            tabIndex={0}
            className={`overflow-x-auto rounded-control border border-rule bg-wash ${focusRing}`}
          >
            <pre className="w-max min-w-full px-4 py-3 font-mono text-sm leading-8 text-ink">
              {block.rows.map((row, i) => (
                <span key={i} className="block">
                  <Segments segments={row} {...context} />
                </span>
              ))}
            </pre>
          </div>
        </figure>
      );
    case "code":
      return <CodeBlock code={block.text} label="Code from the report" />;
  }
}

interface Props {
  audit: AuditResult;
  /** Non-empty: the caller says what to show when there is no report text. */
  reportText: string;
  /** The page this report sits on, so a claim's evidence leads back to it. */
  from: ReturnView;
  /** Mark each claim with what this decision does to it, as well as its verdict. */
  decision?: Decision;
  /** The accessible name of the report. */
  label: string;
}

/**
 * The report as written, each claim marked where it sits and linked to its evidence. Keeps the reader's place:
 * a click first points this history entry at the mark, and on arrival (reload, Back, a "#mark-C2" link) the mark
 * named in the hash is centred, focused and ringed for a moment.
 */
export default function MarkedReport({ audit, reportText, from, decision, label }: Props) {
  const hash = useSyncExternalStore(subscribeHash, readHash, serverHash);
  const marked = useMemo(() => markReport(reportText, audit.claims.map((r) => r.claim)), [audit, reportText]);
  const byId = useMemo(() => new Map(audit.claims.map((r) => [r.claim.id, r])), [audit]);

  // Before Next navigates to the evidence, point this history entry at the mark, so the browser's Back button
  // lands on it as well as the evidence page's own way back.
  const remember = useCallback((id: string) => window.history.replaceState(null, "", returnHref(from, id)), [from]);

  // The marks are on the page once this component renders (callers wait for the stored audit to be restored).
  useEffect(() => {
    const id = markIdFromHash(hash);
    const el = id !== null ? document.getElementById(markAnchor(id)) : null;
    if (!el) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // A frame later, so ours is the scroll that sticks after Next's own jump to the hash.
    const frame = requestAnimationFrame(() => {
      el.scrollIntoView({ block: "center", behavior: still ? "auto" : "smooth" });
      el.focus({ preventScroll: true });
      el.setAttribute("data-flash", "");
    });
    const timer = window.setTimeout(() => el.removeAttribute("data-flash"), FLASH_MS);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(timer);
      el.removeAttribute("data-flash");
    };
  }, [hash, marked]);

  const context: MarkContext = { byId, from, decision, onOpen: remember };

  return (
    <>
      <article aria-label={label} className="rounded-panel border border-rule bg-sheet px-5 py-6 sm:px-10 sm:py-10">
        <div className="max-w-prose space-y-5">
          {marked.blocks.map((block, i) => (
            <Block key={i} block={block} {...context} />
          ))}
        </div>
      </article>

      {marked.unplaced.length > 0 && (
        <section aria-label="Claims not found in the text" className="mt-10">
          <h2 className={sectionTitle}>Claims not found in the text</h2>
          <p className="mt-1 max-w-prose text-ink-soft">
            The report may have changed since the audit. These claims are listed here so none is hidden.
          </p>
          <ul className="mt-4 divide-y divide-rule border-y border-rule">
            {marked.unplaced.map((id) => {
              const result = byId.get(id);
              if (!result) return null;
              return (
                <li key={id} className="grid gap-2 py-4">
                  <p className="reported text-ink">
                    <ClaimWords result={result} text={result.claim.text} decision={decision} />
                  </p>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    {decision && (
                      <span className="text-sm font-semibold text-ink">
                        {actionLabel(claimAction(result, decision), decision)}
                      </span>
                    )}
                    <VerdictBadge verdict={finalVerdict(result)} size="sm" />
                    {result.review?.decision === "override" && (
                      <span className="text-sm text-ink-soft">overridden by a reviewer</span>
                    )}
                    <Link
                      id={markAnchor(id)}
                      href={evidenceHref(id, from)}
                      onClick={() => remember(id)}
                      className={`${buttonQuiet} ${FLASH}`}
                    >
                      Open evidence for <span className="font-mono">{id}</span>
                    </Link>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </>
  );
}
