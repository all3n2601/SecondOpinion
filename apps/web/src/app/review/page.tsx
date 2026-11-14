"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";
import Breadcrumb from "@/components/Breadcrumb";
import NoAuditNotice from "@/components/NoAuditNotice";
import ReviewForm from "@/components/ReviewForm";
import RolePicker from "@/components/RolePicker";
import ClaimBody from "@/components/review/ClaimBody";
import ReviewList, { VerdictStack } from "@/components/review/ReviewList";
import ReviewOverview from "@/components/review/ReviewOverview";
import { useAudit } from "@/lib/audit-context";
import { plural, unreviewedIds } from "@/lib/review";
import { nextToReview, OVERVIEW, previousEntry, type Entry } from "@/lib/review-nav";
import { useRoleView } from "@/lib/roles";
import type { RoleView } from "@/lib/types";
import { narrationClaims, useNarration } from "@/lib/use-narration";
import { useReviewSelection } from "@/lib/use-review-selection";
import { buttonPrimary, buttonQuiet, pageTitle } from "@/lib/ui";

const INTRO: Record<RoleView, string> = {
  story: "A short read on what the audit found. Look at each claim, then accept the check or change it with a reason.",
  checklist: "Accept the tool's verdict or override it with a reason. Both verdicts are kept.",
  evidence:
    "Each claim with its corrected wording, how many ways of counting agree and what the skeptic tests found. " +
    "Accept the verdict or override it with a reason; both are kept.",
  raw: "Counts, sample IDs, file checksums and the code behind each check. Accept each verdict or override it with a reason; both are kept.",
};

/** The two columns sit side by side from Tailwind's `lg` breakpoint. */
const WIDE = "(min-width: 64rem)";

export default function ReviewPage() {
  const { audit, hydrated } = useAudit();
  const { view, ready } = useRoleView();
  // No AI request until saved state has loaded and the role's real view is known; the layout renders meanwhile.
  const narration = useNarration(view, narrationClaims(hydrated, ready, audit?.claims ?? null));
  const claims = useMemo(() => audit?.claims ?? [], [audit]);
  const ids = useMemo(() => claims.map((c) => c.claim.id), [claims]);
  const [selected, select] = useReviewSelection(ids);
  const pane = useRef<HTMLElement>(null);
  const total = claims.length;
  const left = audit ? unreviewedIds(claims).length : 0;
  const done = total - left;
  const current = claims.find((c) => c.claim.id === selected) ?? null;
  const firstToReview = nextToReview(claims, OVERVIEW);

  const open = (entry: Entry) => select(entry);

  // Whenever the open entry changes (list, buttons, a "#review-C2" link, back / forward), start its pane at the top
  // and move focus there; on a narrow screen, scroll to it. Not on first load: the reader has not asked to move yet.
  const shown = useRef<Entry | null>(null);
  useEffect(() => {
    const first = shown.current === null;
    shown.current = selected;
    const el = pane.current;
    if (first || !el) return;
    el.scrollTop = 0;
    const wide = window.matchMedia(WIDE).matches;
    el.focus({ preventScroll: wide });
    if (!wide) el.scrollIntoView({ block: "start" });
  }, [selected]);

  return (
    <main className="mx-auto w-full max-w-7xl px-5 py-8 sm:px-8 sm:py-10">
      <title>Review | SecondOpinion</title>
      {!audit ? (
        <div className="max-w-4xl">
          <Breadcrumb items={[{ label: "Audit board", href: "/board" }, { label: "Review" }]} />
          <h1 className={pageTitle}>Review every verdict</h1>
          <p className="mt-2 max-w-prose text-ink-soft">{INTRO[view]}</p>
          <div className="mt-8">
            <NoAuditNotice />
          </div>
        </div>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[minmax(17rem,30%)_minmax(0,1fr)] lg:items-start">
          <div className="min-w-0">
            <Breadcrumb items={[{ label: "Audit board", href: "/board" }, { label: "Review" }]} />
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Review every verdict</h1>
            <div className="mt-4">
              <RolePicker />
            </div>
            <div className="mt-5">
              <VerdictStack claims={claims} />
            </div>
            <div className="mt-4">
              <p role="status" aria-live="polite" className="num text-sm font-semibold text-ink">
                {done} of {total} reviewed
              </p>
              <div
                role="progressbar"
                aria-label="Claims reviewed"
                aria-valuemin={0}
                aria-valuemax={total}
                aria-valuenow={done}
                className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-wash"
              >
                <div
                  className="h-full rounded-full bg-pen transition-[width] duration-200"
                  style={{ width: total ? `${(done / total) * 100}%` : "0%" }}
                />
              </div>
            </div>
            <div className="mt-4">
              <ReviewList claims={claims} selected={selected} onSelect={open} />
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-3">
              {left === 0 ? (
                <Link href="/decision" className={buttonPrimary}>
                  Continue to decision
                </Link>
              ) : (
                <>
                  <button type="button" disabled aria-describedby="review-gate" className={buttonPrimary}>
                    Continue to decision
                  </button>
                  <p id="review-gate" className="text-sm text-ink-soft">
                    {plural(left, "claim still needs", "claims still need")} a review.
                  </p>
                </>
              )}
            </div>
          </div>

          <section
            ref={pane}
            tabIndex={-1}
            aria-label={current ? `Claim ${current.claim.id}` : "Overview"}
            className="min-w-0 scroll-mt-6 focus:outline-none lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:overflow-y-auto lg:pr-1"
          >
            {/* Every claim's form stays mounted, hidden unless open, so a half-written review survives switching. */}
            {claims.map((result) => {
              const id = result.claim.id;
              const previous = previousEntry(ids, id);
              return (
                <div key={id} hidden={id !== selected} className="rounded-panel border border-rule bg-sheet">
                  <ReviewForm
                    result={result}
                    saveLabel="Save and next →"
                    onSaved={() => open(nextToReview(claims, id))}
                    body={<ClaimBody view={view} result={result} sentence={narration.claims[id] ?? { text: "", ai: false }} />}
                  />
                  <div className="border-t border-rule px-5 py-2 sm:px-6">
                    <button type="button" onClick={() => open(previous)} className={buttonQuiet}>
                      <ArrowLeft aria-hidden="true" className="size-4" />
                      {previous === OVERVIEW ? "Overview" : "Previous claim"}
                    </button>
                  </div>
                </div>
              );
            })}
            {!current && (
              <>
                <p className="mb-4 max-w-prose text-ink-soft">{INTRO[view]}</p>
                {/* Shown once the narrated text is real: before that it would read as an empty audit. */}
                {hydrated && ready && <ReviewOverview view={view} audit={audit} narration={narration} />}
                {total === 0 ? (
                  <p className="mt-4 text-ink-soft">The report had no claims to review.</p>
                ) : left === 0 ? (
                  <div className="mt-5">
                    <Link href="/decision" className={buttonPrimary}>
                      Every claim is reviewed: continue to decision
                      <ArrowRight aria-hidden="true" className="size-4" />
                    </Link>
                  </div>
                ) : (
                  firstToReview !== OVERVIEW && (
                    <div className="mt-5">
                      <button type="button" onClick={() => open(firstToReview)} className={buttonPrimary}>
                        {done === 0 ? "Start reviewing" : "Continue reviewing"}
                        <ArrowRight aria-hidden="true" className="size-4" />
                      </button>
                    </div>
                  )
                )}
              </>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
