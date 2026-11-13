import { CircleCheck, CircleHelp, CircleX } from "lucide-react";
import { VERDICT_LABEL } from "@/lib/claim-format";
import type { Verdict } from "@/lib/types";

const STYLE: Record<Verdict, string> = {
  supported: "border-supported bg-supported-tint text-supported",
  contradicted: "border-contradicted bg-contradicted-tint text-contradicted",
  insufficient_evidence: "border-insufficient bg-insufficient-tint text-insufficient",
};

const ICON = { supported: CircleCheck, contradicted: CircleX, insufficient_evidence: CircleHelp } as const;

/** Verdict as a stamp: icon + words + colour, never colour alone. */
export default function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" }) {
  const Icon = ICON[verdict];
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-stamp border-2 font-semibold ${STYLE[verdict]} ${
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm"
      }`}
    >
      <Icon aria-hidden="true" className={size === "sm" ? "size-3.5" : "size-4"} strokeWidth={2.25} />
      {VERDICT_LABEL[verdict]}
    </span>
  );
}
