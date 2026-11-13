import { formatFact, VERDICT_ICON, VERDICT_LABEL, variantWords } from "@/lib/claim-format";
import type { ClaimResult } from "@/lib/types";

/** Mirrors PRIMARY_VARIANT in second_opinion/variants.py: the organizers' definition. */
export const PRIMARY_VARIANT_ID = "rna_call|everyone|primary_tumors";

/** One row per "count it differently" variant; rows whose verdict differs from the main one are highlighted. */
export default function RobustnessTable({ result }: { result: ClaimResult }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-left text-sm">
        <caption className="sr-only">
          The verdict for {result.claim.id} recomputed under {result.variants.length} ways of counting
        </caption>
        <thead>
          <tr className="border-b border-slate-300 text-slate-700">
            <th scope="col" className="py-2 pr-3 font-semibold">
              Way of counting
            </th>
            <th scope="col" className="py-2 pr-3 font-semibold">
              Value
            </th>
            <th scope="col" className="py-2 font-semibold">
              Verdict
            </th>
          </tr>
        </thead>
        <tbody>
          {result.variants.map((v) => {
            const primary = v.variant_id === PRIMARY_VARIANT_ID;
            const flips = v.verdict !== null && v.verdict !== result.verdict;
            return (
              <tr
                key={v.variant_id}
                className={`border-b border-slate-200 ${flips ? "bg-amber-50 font-semibold text-amber-950" : ""}`}
              >
                <th scope="row" className="py-2 pr-3 font-normal">
                  {variantWords(v.variant_id)}
                  {primary && <span className="ml-2 text-xs font-semibold text-emerald-900 uppercase">main definition</span>}
                </th>
                <td className="py-2 pr-3">{v.fact ? formatFact(v.fact, result.claim.type) : "unknown"}</td>
                <td className="py-2">
                  {v.verdict ? (
                    <>
                      <span aria-hidden="true">{VERDICT_ICON[v.verdict]} </span>
                      {VERDICT_LABEL[v.verdict]}
                      {flips && " (flips)"}
                    </>
                  ) : (
                    "Could not be checked"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
