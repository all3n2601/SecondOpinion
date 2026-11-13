import { container } from "@/lib/ui";

// Shown on every screen (rendered once in the root layout). Text is fixed by the plan's Global Constraints.

export const RESEARCH_NOTICE =
  "Research prototype. Not a clinical decision system. Verdicts need human review.";

export default function ResearchBanner() {
  return (
    <aside aria-label="Research notice" className="border-b border-amber-300 bg-amber-50 text-amber-950">
      <p className={`${container} flex items-center gap-2 py-1.5 text-[0.8rem] font-medium`}>
        <span
          aria-hidden="true"
          className="grid size-4 place-items-center rounded-full bg-amber-600 text-[0.65rem] font-bold text-white"
        >
          !
        </span>
        {RESEARCH_NOTICE}
      </p>
    </aside>
  );
}
