// Shown on every screen (rendered once in the root layout). Text is fixed by the plan's Global Constraints.

export const RESEARCH_NOTICE =
  "Research prototype. Not a clinical decision system. Verdicts need human review.";

export default function ResearchBanner() {
  return (
    <aside aria-label="Research notice" className="border-b border-amber-300 bg-amber-50 text-amber-950">
      <p className="mx-auto max-w-5xl px-6 py-2 text-sm font-medium">
        <span aria-hidden="true">⚠ </span>
        {RESEARCH_NOTICE}
      </p>
    </aside>
  );
}
