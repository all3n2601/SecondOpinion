// Shared wording for reviews and decisions (Meghana: review queue, decision screen, role views).

import type { ClaimResult, Decision, Fact, Solidity, Verdict } from "./types";

export const VERDICTS: Verdict[] = ["supported", "contradicted", "insufficient_evidence"];
export const DECISIONS: Decision[] = ["Proceed", "Fix a problem", "Narrow the question", "Stop"];

export const VERDICT_LABEL: Record<Verdict, string> = {
  supported: "Supported",
  contradicted: "Contradicted",
  insufficient_evidence: "Insufficient evidence",
};

export const VERDICT_STYLE: Record<Verdict, string> = {
  supported: "border-supported bg-supported-tint text-supported",
  contradicted: "border-contradicted bg-contradicted-tint text-contradicted",
  insufficient_evidence: "border-insufficient bg-insufficient-tint text-insufficient",
};

export const SOLIDITY_LABEL: Record<Solidity, string> = {
  holds_under_every_variant: "Robust: same answer however it is counted",
  holds_under_some_variants: "Fragile: the answer changes with how it is counted",
  not_applicable: "Solidity does not apply",
};

export const DECISION_NEXT_STEP: Record<Decision, string> = {
  Proceed: "collect the sign-offs and publish",
  "Fix a problem": "reword the contradicted claims to what the data shows, then export again",
  "Narrow the question": "limit the report to what this data can answer",
  Stop: "re-fetch the release, confirm the checksums and rerun the audit",
};

/** The reviewer's verdict when there is one, else the tool's. */
export function finalVerdict(result: ClaimResult): Verdict {
  return result.review?.final_verdict ?? result.verdict;
}

export function formatCount(n: number): string {
  return n.toLocaleString("en-US");
}

/** "421 of 844" (always with its denominator), plus how many were unknown. */
export function countText(fact: Fact | null): string | null {
  if (!fact) return null;
  if (fact.numerator !== null && fact.denominator !== null) {
    const unknown = fact.unknown_count ? `; ${formatCount(fact.unknown_count)} unknown, left out` : "";
    return `${formatCount(fact.numerator)} of ${formatCount(fact.denominator)}${unknown}`;
  }
  if (fact.value === null) return null;
  // "1,101", never "1101"; a mean or a ratio keeps up to three decimals.
  return Number.isInteger(fact.value) ? formatCount(fact.value) : fact.value.toLocaleString("en-US", { maximumFractionDigits: 3 });
}

/**
 * How many samples a check lists, as text: "85"; "0" when it counted none; "not listed" when the check does not
 * list samples (a ranking, a rate or a mean), where a bare 0 would read as "no samples".
 */
export function samplesText(fact: Fact | null): string {
  if (!fact) return "none";
  if (fact.sample_ids.length > 0) return formatCount(fact.sample_ids.length);
  return fact.numerator === 0 ? "0" : "not listed";
}

/** The one number a reviewer needs to judge the tool's verdict. */
export function keyNumber(result: ClaimResult): string {
  if (result.verdict === "contradicted" && result.correct_value) return `The data shows ${result.correct_value}`;
  if (result.verdict === "insufficient_evidence") {
    return `Would need ${result.missing_evidence ?? result.claim.needed_data ?? "data this release does not have"}`;
  }
  const counted = countText(result.fact);
  return counted ? `Recomputed: ${counted}` : "No number for this claim";
}

export function unreviewedIds(claims: ClaimResult[]): string[] {
  return claims.filter((c) => c.review === null).map((c) => c.claim.id);
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}
