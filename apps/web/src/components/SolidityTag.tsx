import { solidityText } from "@/lib/claim-format";
import type { ClaimResult } from "@/lib/types";

/** How solid the verdict is, in words: Robust (8 of 8) / Fragile: flips when … / not tested. */
export default function SolidityTag({ result }: { result: ClaimResult }) {
  const { short, long } = solidityText(result);
  const style =
    result.solidity === "holds_under_every_variant"
      ? "border-slate-500 text-slate-800"
      : result.solidity === "holds_under_some_variants"
        ? "border-amber-700 bg-amber-50 text-amber-950"
        : "border-dashed border-slate-400 text-slate-600";
  const icon =
    result.solidity === "holds_under_every_variant" ? "◆" : result.solidity === "holds_under_some_variants" ? "◇" : "–";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm ${style}`} title={long}>
      <span aria-hidden="true">{icon}</span>
      {short}
    </span>
  );
}
