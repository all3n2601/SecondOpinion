"use client";

import { useId, useMemo } from "react";
import { AiWordingStamp } from "@/components/AiStamp";
import ChecklistOverview from "@/components/review/ChecklistOverview";
import EvidenceOverview from "@/components/review/EvidenceOverview";
import RawOverview from "@/components/review/RawOverview";
import StoryOverview from "@/components/review/StoryOverview";
import { renderNarration, type Narration } from "@/lib/narrate";
import type { AuditResult, RoleView } from "@/lib/types";

const TITLE: Record<RoleView, string> = {
  story: "What the audit found",
  checklist: "Review checklist",
  evidence: "Evidence at a glance",
  raw: "Raw audit data",
};

/** The panel above the review rows: headline and caption (AI-worded or template), plus the view's own visual. */
export default function ReviewOverview({ view, audit, narration }: {
  view: RoleView;
  audit: AuditResult;
  narration: Narration & { pending: boolean };
}) {
  const titleId = useId();
  const claims = audit.claims;
  // Narration flags AI text only overall and per claim; the headline and caption are the AI's when they differ
  // from our own template for this view.
  const template = useMemo(() => renderNarration(view, claims, null), [view, claims]);
  const aiWorded = narration.ai && (narration.headline !== template.headline || narration.caption !== template.caption);
  const words = { claims, headline: narration.headline, caption: narration.caption };

  return (
    <section aria-labelledby={titleId} className="rounded-panel border border-rule bg-sheet p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 id={titleId} className="text-sm font-semibold text-ink-soft">
          {TITLE[view]}
        </h2>
        {aiWorded && <AiWordingStamp />}
      </div>
      {view === "story" && <StoryOverview {...words} />}
      {view === "checklist" && <ChecklistOverview {...words} />}
      {view === "evidence" && <EvidenceOverview {...words} />}
      {view === "raw" && <RawOverview {...words} release={audit.release} />}
      <p role="status" className={`text-xs text-ink-faint ${narration.pending ? "mt-3" : ""}`}>
        {narration.pending ? "The AI helper is wording this view; the text above may change." : ""}
      </p>
    </section>
  );
}
