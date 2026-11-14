"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useSyncExternalStore } from "react";
import BoardViewSwitch from "@/components/BoardViewSwitch";
import Breadcrumb from "@/components/Breadcrumb";
import CodeBlock from "@/components/CodeBlock";
import NoAuditNotice from "@/components/NoAuditNotice";
import VerdictBadge from "@/components/VerdictBadge";
import { useAudit } from "@/lib/audit-context";
import { markReport, type MarkSegment, type ReportBlock } from "@/lib/report-marks";
import { evidenceHref, markAnchor, markIdFromHash, reportHref } from "@/lib/report-nav";
import { finalVerdict, VERDICTS } from "@/lib/review";
import type { ClaimResult, Verdict } from "@/lib/types";
import { buttonPrimary, buttonQuiet, focusRing, pageTitle, pageWidth, sectionTitle } from "@/lib/ui";

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

/** "Contradicted, overridden, claim C2" after the sentence: seen as a stamp, heard as part of the link's name. */
function MarkStamp({ result }: { result: ClaimResult }) {
  const overridden = result.review?.decision === "override";
  return (
    <span className="ml-1.5 inline-flex items-center gap-1.5 whitespace-nowrap align-middle font-sans text-xs leading-none not-italic">
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

interface MarkProps {
  byId: Map<string, ClaimResult>;
  onOpen: (id: string) => void;
}

// markReport marks each claim at most once, as one segment, so its element id is unique on the page.
function Segments({ segments, byId, onOpen }: { segments: MarkSegment[] } & MarkProps) {
  return segments.map((segment, i) => {
    const result = segment.kind === "claim" ? byId.get(segment.claimId) : undefined;
    if (!result) return <Fragment key={i}>{segment.text}</Fragment>;
    const id = result.claim.id;
    return (
      <Link
        key={i}
        id={markAnchor(id)}
        href={evidenceHref(id, true)}
        onClick={() => onOpen(id)}
        className={`cursor-pointer rounded-stamp box-decoration-clone px-0.5 text-ink underline decoration-2 underline-offset-4 hover:decoration-[3px] ${MARK[finalVerdict(result)]} ${FLASH} ${focusRing}`}
      >
        {segment.text}
        <MarkStamp result={result} />
      </Link>
    );
  });
}

function Block({ block, ...props }: { block: ReportBlock } & MarkProps) {
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
          <Segments segments={block.segments} {...props} />
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
                  <Segments segments={row} {...props} />
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

export default function ReportViewPage() {
  const { audit, reportText, hydrated } = useAudit();
  const hash = useSyncExternalStore(subscribeHash, readHash, serverHash);

  const marked = useMemo(
    () => (audit && reportText.trim() ? markReport(reportText, audit.claims.map((r) => r.claim)) : null),
    [audit, reportText],
  );
  const byId = useMemo(() => new Map((audit?.claims ?? []).map((r) => [r.claim.id, r])), [audit]);
  const ready = hydrated && marked !== null;

  // Before Next navigates to the evidence, point this history entry at the mark, so the browser's Back button
  // lands on it as well as "Back to the report".
  const remember = useCallback((id: string) => {
    window.history.replaceState(null, "", reportHref(id));
  }, []);

  // Coming back (reload, Back, "Back to the report", "Show in report"): centre the mark, move focus to it and ring
  // it for a moment. The audit is restored after mount, so this waits until the marks exist.
  useEffect(() => {
    const id = markIdFromHash(hash);
    const el = ready && id !== null ? document.getElementById(markAnchor(id)) : null;
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
  }, [hash, ready]);

  const markProps: MarkProps = { byId, onOpen: remember };

  return (
    <main className={pageWidth}>
      <title>Report | SecondOpinion</title>
      <Breadcrumb items={[{ label: "Audit board", href: "/board" }, { label: "Report" }]} />
      <h1 className={pageTitle}>The report, with its claims marked</h1>

      {!audit ? (
        <div className="mt-6">
          <NoAuditNotice />
        </div>
      ) : (
        <>
          <p className="mt-3 max-w-prose text-ink-soft">
            Each claim checked against release {audit.release.name}, marked where it sits in the report. The verdict
            shown is the final one, after any review.
          </p>

          <div className="mt-5">
            <BoardViewSwitch current="report" />
          </div>

          {marked === null ? (
            <p className="mt-8 max-w-prose text-ink">
              There is no report text to show, so nothing can be marked. The checked claims are still on the board:{" "}
              <Link href="/board" className="rounded-control font-medium text-pen underline underline-offset-4 hover:text-pen-deep">
                see them as a list
              </Link>
              .
            </p>
          ) : (
            <>
              <div className="mt-6 border-y border-rule py-4">
                <ul aria-label="What the marks mean" className="flex flex-wrap gap-x-4 gap-y-2">
                  {VERDICTS.map((v) => (
                    <li key={v}>
                      <VerdictBadge verdict={v} size="sm" />
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-sm text-ink-soft">
                  Click a marked sentence to open its evidence; you come back to the same place.
                </p>
              </div>

              <article
                aria-label="The report"
                className="mt-8 rounded-panel border border-rule bg-sheet px-5 py-6 sm:px-10 sm:py-10"
              >
                <div className="max-w-prose space-y-5">
                  {marked.blocks.map((block, i) => (
                    <Block key={i} block={block} {...markProps} />
                  ))}
                </div>
              </article>

              {marked.unplaced.length > 0 && (
                <section aria-labelledby="unplaced-title" className="mt-10">
                  <h2 id="unplaced-title" className={sectionTitle}>
                    Claims not found in the text
                  </h2>
                  <p className="mt-1 max-w-prose text-ink-soft">
                    The report may have changed since the audit. These claims are listed here so none is hidden.
                  </p>
                  <ul className="mt-4 divide-y divide-rule border-y border-rule">
                    {marked.unplaced.map((id) => {
                      const result = byId.get(id);
                      if (!result) return null;
                      return (
                        <li key={id} className="grid gap-2 py-4">
                          <p className="reported text-ink">{result.claim.text}</p>
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                            <VerdictBadge verdict={finalVerdict(result)} size="sm" />
                            {result.review?.decision === "override" && (
                              <span className="text-sm text-ink-soft">overridden by a reviewer</span>
                            )}
                            <Link
                              id={markAnchor(id)}
                              href={evidenceHref(id, true)}
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
          )}

          <div className="mt-10">
            <Link href="/review" className={buttonPrimary}>
              Continue to review
            </Link>
          </div>
        </>
      )}
    </main>
  );
}
