import { Layers, ShieldCheck, TriangleAlert } from "lucide-react";
import { solidityText } from "@/lib/claim-format";
import type { ClaimResult } from "@/lib/types";

/** How solid the verdict is, in words: Robust (8 of 8) / Fragile: flips when … / not tested. */
export default function SolidityTag({ result }: { result: ClaimResult }) {
  const { short } = solidityText(result);
  const robust = result.solidity === "holds_under_every_variant";
  const fragile = result.solidity === "holds_under_some_variants";
  const style = robust
    ? "border-rule-strong bg-sheet px-2.5 text-ink"
    : fragile
      ? "border-insufficient bg-insufficient-tint px-2.5 text-insufficient"
      : "border-transparent px-0 text-ink-soft";
  const Icon = robust ? ShieldCheck : fragile ? TriangleAlert : Layers;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-stamp border py-1 text-sm font-medium ${style}`}
    >
      <Icon aria-hidden="true" className="size-4" />
      {short}
    </span>
  );
}
