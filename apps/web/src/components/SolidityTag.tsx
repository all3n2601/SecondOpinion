import { solidityText } from "@/lib/claim-format";
import type { ClaimResult } from "@/lib/types";
import { chip } from "@/lib/ui";

/** How solid the verdict is, in words: Robust (8 of 8) / Fragile: flips when … / not tested. */
export default function SolidityTag({ result }: { result: ClaimResult }) {
  const { short, long } = solidityText(result);
  const style =
    result.solidity === "holds_under_every_variant"
      ? "border-slate-400 bg-white text-slate-800"
      : result.solidity === "holds_under_some_variants"
        ? "border-amber-600 bg-amber-50 text-amber-900"
        : "border-dashed border-slate-300 bg-white font-medium text-slate-500";
  const icon =
    result.solidity === "holds_under_every_variant" ? "◆" : result.solidity === "holds_under_some_variants" ? "◇" : "–";

  return (
    <span className={`${chip} ${style}`} title={long}>
      <span aria-hidden="true">{icon}</span>
      {short}
    </span>
  );
}
