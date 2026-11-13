import { formatFact, VERDICT_ICON, VERDICT_LABEL, variantWords } from "@/lib/claim-format";
import type { ClaimResult } from "@/lib/types";
import { tableHead } from "@/lib/ui";

/** Mirrors PRIMARY_VARIANT in second_opinion/variants.py: the organizers' definition. */
export const PRIMARY_VARIANT_ID = "rna_call|everyone|primary_tumors";

/** One row per "count it differently" variant; rows whose verdict differs from the main one are highlighted. */
export default function RobustnessTable({ result }: { result: ClaimResult }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <caption className="sr-only">
          The verdict for {result.claim.id} recomputed under {result.variants.length} ways of counting
        </caption>
        <thead className={tableHead}>
          <tr>
            <th scope="col" className="px-5 py-2.5">
              Way of counting
            </th>
            <th scope="col" className="px-5 py-2.5">
              Value
            </th>
            <th scope="col" className="px-5 py-2.5">
              Verdict
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {result.variants.map((v) => {
            const primary = v.variant_id === PRIMARY_VARIANT_ID;
            const flips = v.verdict !== null && v.verdict !== result.verdict;
            return (
              <tr key={v.variant_id} className={flips ? "bg-amber-50 font-semibold text-amber-950" : primary ? "bg-emerald-50/40" : ""}>
                <th scope="row" className="px-5 py-2.5 font-normal">
                  {variantWords(v.variant_id)}
                  {primary && (
                    <span className="ml-2 rounded-sm border border-emerald-800 px-1 py-px text-[0.65rem] font-semibold tracking-wider text-emerald-900 uppercase">
                      Main definition
                    </span>
                  )}
                </th>
                <td className="px-5 py-2.5 tabular-nums">{v.fact ? formatFact(v.fact, result.claim.type) : "unknown"}</td>
                <td className="px-5 py-2.5 whitespace-nowrap">
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
