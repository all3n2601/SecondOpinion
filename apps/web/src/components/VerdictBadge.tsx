import { VERDICT_ICON, VERDICT_LABEL } from "@/lib/claim-format";
import type { Verdict } from "@/lib/types";

export const VERDICT_STYLE: Record<Verdict, string> = {
  supported: "border-emerald-700 bg-emerald-50 text-emerald-900",
  contradicted: "border-red-700 bg-red-50 text-red-900",
  insufficient_evidence: "border-amber-600 bg-amber-50 text-amber-900",
};

/** Verdict as icon + text + colour, never colour alone. */
export default function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm border font-semibold tracking-wide uppercase ${VERDICT_STYLE[verdict]} ${
        size === "sm" ? "px-1.5 py-0.5 text-[0.65rem]" : "px-2 py-0.5 text-xs"
      }`}
    >
      <span aria-hidden="true" className="text-[0.85em]">
        {VERDICT_ICON[verdict]}
      </span>
      {VERDICT_LABEL[verdict]}
    </span>
  );
}
