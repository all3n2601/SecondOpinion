import { VERDICT_ICON, VERDICT_LABEL } from "@/lib/claim-format";
import type { Verdict } from "@/lib/types";

const STYLE: Record<Verdict, string> = {
  supported: "border-emerald-800 bg-emerald-50 text-emerald-950",
  contradicted: "border-red-800 bg-red-50 text-red-950",
  insufficient_evidence: "border-amber-700 bg-amber-50 text-amber-950",
};

/** Verdict as icon + text + colour, never colour alone. */
export default function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${STYLE[verdict]} ${
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm"
      }`}
    >
      <span aria-hidden="true">{VERDICT_ICON[verdict]}</span>
      {VERDICT_LABEL[verdict]}
    </span>
  );
}
