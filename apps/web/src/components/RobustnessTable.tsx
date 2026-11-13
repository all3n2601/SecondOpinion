import { CircleCheck, CircleHelp, CircleX, TriangleAlert } from "lucide-react";
import { formatFact, VERDICT_LABEL, variantWords } from "@/lib/claim-format";
import type { ClaimResult, Verdict } from "@/lib/types";
import { statedShare } from "./ClaimVsData";

/** Mirrors PRIMARY_VARIANT in second_opinion/variants.py: the organizers' definition. */
export const PRIMARY_VARIANT_ID = "rna_call|everyone|primary_tumors";

const ICON = { supported: CircleCheck, contradicted: CircleX, insufficient_evidence: CircleHelp } as const;
const TEXT: Record<Verdict, string> = {
  supported: "text-supported",
  contradicted: "text-contradicted",
  insufficient_evidence: "text-insufficient",
};
const BG: Record<Verdict, string> = {
  supported: "bg-supported",
  contradicted: "bg-contradicted",
  insufficient_evidence: "bg-insufficient",
};
const clamp = (n: number) => Math.min(100, Math.max(0, n));
const count = new Intl.NumberFormat("en-US");

/** One row per "count it differently" variant; rows whose verdict differs from the main one are highlighted. */
export default function RobustnessTable({ result }: { result: ClaimResult }) {
  const isShare = result.claim.type === "SHARE";
  const stated = isShare ? statedShare(result.claim.params) : null;
  const ticks = stated ? (stated.marker !== null ? [stated.marker] : (stated.band ?? [])) : [];
  const tone = TEXT[result.verdict];
  const toneBg = BG[result.verdict];

  return (
    <div>
      {isShare && stated && (
        <p className="mb-3 flex items-center gap-2 text-sm text-ink-soft">
          <span aria-hidden="true" className={`relative inline-block h-4 w-0.5 ${toneBg}`} />
          The vertical line in every row marks the report&apos;s figure ({stated.phrase}). Bars start at 0% and end at 100%.
        </p>
      )}
      <p className="mb-2 text-sm text-ink-faint sm:hidden">Scroll sideways to see every column.</p>
      <div
        role="region"
        aria-label={`Ways of counting for ${result.claim.id}, scrolls sideways`}
        tabIndex={0}
        className="overflow-x-auto rounded-panel border border-rule bg-sheet"
      >
        <table className={`w-full text-left text-sm ${isShare ? "min-w-[44rem]" : "min-w-[34rem]"}`}>
          <caption className="sr-only">
            The verdict for {result.claim.id} recomputed under {result.variants.length} ways of counting
            {stated ? `. The report says ${stated.phrase}.` : ""}
          </caption>
          <thead>
            <tr className="border-b border-rule-strong bg-wash text-ink-soft">
              <th scope="col" className="px-4 py-2.5 font-semibold">
                Way of counting
              </th>
              <th scope="col" className="px-4 py-2.5 font-semibold">
                Value
              </th>
              <th scope="col" className="px-4 py-2.5 font-semibold">
                Verdict
              </th>
              {isShare && (
                <th scope="col" className="w-60 px-4 py-2.5 font-semibold">
                  <span className="block">Against the report</span>
                  <span aria-hidden="true" className="num flex justify-between font-mono text-xs font-normal text-ink-faint">
                    <span>0%</span>
                    <span>50%</span>
                    <span>100%</span>
                  </span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {result.variants.map((v) => {
              const primary = v.variant_id === PRIMARY_VARIANT_ID;
              const flips = v.verdict !== null && v.verdict !== result.verdict;
              const Icon = v.verdict ? ICON[v.verdict] : null;
              const value = v.fact?.value ?? null;
              const num = v.fact?.numerator ?? null;
              const den = v.fact?.denominator ?? null;
              return (
                <tr
                  key={v.variant_id}
                  className={`border-b border-rule last:border-b-0 ${flips ? "bg-insufficient-tint" : ""}`}
                >
                  <th scope="row" className="px-4 py-3 align-middle font-normal text-ink">
                    {variantWords(v.variant_id)}
                    {primary && (
                      <span className="mt-1 block w-fit rounded-stamp border border-rule-strong bg-sheet px-1.5 py-px text-xs font-medium text-ink-soft">
                        Main definition
                      </span>
                    )}
                  </th>
                  <td className="num px-4 py-3 align-middle font-mono whitespace-nowrap">
                    {v.fact ? (
                      isShare && value !== null && num !== null && den !== null ? (
                        <>
                          <span className="block font-semibold">{value.toFixed(1)}%</span>
                          <span className="block text-ink-soft">
                            {count.format(num)} of {count.format(den)}
                          </span>
                        </>
                      ) : (
                        formatFact(v.fact, result.claim.type)
                      )
                    ) : (
                      "unknown"
                    )}
                  </td>
                  <td className="px-4 py-3 align-middle">
                    {v.verdict && Icon ? (
                      <>
                        <span className={`inline-flex items-center gap-1.5 font-semibold whitespace-nowrap ${TEXT[v.verdict]}`}>
                          <Icon aria-hidden="true" className="size-4 shrink-0" strokeWidth={2.25} />
                          {VERDICT_LABEL[v.verdict]}
                        </span>
                        {flips && (
                          <span className="mt-1 flex items-center gap-1.5 font-semibold whitespace-nowrap text-insufficient">
                            <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
                            Flips the verdict
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-ink-soft">Could not be checked</span>
                    )}
                  </td>
                  {isShare && (
                    <td className="relative h-14 p-0 align-middle">
                      <div aria-hidden="true" className="absolute inset-x-4 inset-y-0">
                        {stated?.band && (
                          <div
                            className={`absolute inset-y-0 opacity-30 ${tone}`}
                            style={{
                              left: `${clamp(Math.min(...stated.band))}%`,
                              width: `${Math.max(Math.abs(stated.band[1] - stated.band[0]), 0.5)}%`,
                              backgroundImage:
                                "repeating-linear-gradient(135deg, currentColor 0 1.5px, transparent 1.5px 6px)",
                            }}
                          />
                        )}
                        {value !== null && (
                          <div className="absolute inset-x-0 top-1/2 h-3 -translate-y-1/2 overflow-hidden rounded-stamp bg-wash">
                            <div className="h-full bg-ink" style={{ width: `${clamp(value)}%` }} />
                          </div>
                        )}
                        {ticks.map((t) => (
                          <div
                            key={t}
                            className={`absolute inset-y-0 w-0.5 -translate-x-1/2 ${toneBg}`}
                            style={{ left: `${clamp(t)}%` }}
                          />
                        ))}
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
