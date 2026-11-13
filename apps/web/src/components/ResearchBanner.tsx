import { FlaskConical } from "lucide-react";

// Shown on every screen (rendered once in the root layout). Text is fixed by the plan's Global Constraints.

export const RESEARCH_NOTICE =
  "Research prototype. Not a clinical decision system. Verdicts need human review.";

export default function ResearchBanner() {
  return (
    <aside aria-label="Research notice" className="border-b border-rule bg-sheet">
      <p className="mx-auto flex max-w-[88rem] items-center gap-2 px-5 py-2 text-sm text-ink-soft sm:px-8">
        <FlaskConical aria-hidden="true" className="size-4 shrink-0 text-insufficient" />
        <span>{RESEARCH_NOTICE}</span>
      </p>
    </aside>
  );
}
