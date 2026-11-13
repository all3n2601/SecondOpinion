// Plain-word labels for claims, shared by the claims list and the audit board.

import type { Claim, ClaimResult, ClaimType, Fact, Verdict } from "./types";

export const TYPE_LABEL: Record<ClaimType, string> = {
  COUNT: "Count",
  SHARE: "Share",
  COMPARISON: "Comparison",
  AGREEMENT: "Agreement",
  COVERAGE: "Coverage",
  NOT_ANSWERABLE: "Not answerable",
  UNMAPPED: "No check yet",
};

const SUBJECT_LABEL: Record<string, string> = {
  primary_tumors: "primary tumors",
  all_five_layers: "all five data layers",
  samples: "samples",
  patients: "patients",
  has_protein: "protein data",
  has_survival: "survival data",
  has_mutation: "mutation data",
  has_copy_number: "copy number data",
  has_rna: "RNA data",
};

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

function fmt(value: number, unit: string | null): string {
  return unit === "percent" ? `${number.format(value)}%` : number.format(value);
}

/** What we read from the sentence, in words: "62%, approximate, Luminal A". */
export function describeParams(claim: Claim): string {
  const p = claim.params;
  const parts: string[] = [];

  if (claim.type === "NOT_ANSWERABLE") {
    if (claim.clinical_terms.length) parts.push(`flagged words: ${claim.clinical_terms.join(", ")}`);
    if (claim.needed_data) parts.push(`would need: ${claim.needed_data}`);
    return parts.join(" · ") || "The data cannot answer this kind of claim";
  }
  if (claim.type === "UNMAPPED") return "No check exists yet for this kind of claim";

  if (p.unit === "all") {
    parts.push("every one");
  } else if (p.stated_value !== null) {
    let stated = fmt(p.stated_value, p.unit);
    if (p.stated_high !== null) stated = `${fmt(p.stated_value, null)}–${fmt(p.stated_high, p.unit)}`;
    if (p.stated_total !== null) stated += ` of ${number.format(p.stated_total)}`;
    parts.push(stated);
  }
  if (p.approximate) parts.push("approximate");
  if (p.subtype) parts.push(p.subtype);
  if (p.subject) parts.push(SUBJECT_LABEL[p.subject] ?? p.subject.replaceAll("_", " "));
  if (p.measure) parts.push(p.measure);
  if (p.direction && p.group_a && p.group_b) parts.push(`${p.direction} in ${p.group_a} than ${p.group_b}`);
  else if (p.direction) parts.push(p.direction);

  return parts.join(", ") || "No details read from this sentence";
}

// ---- Results (audit board and evidence panel) ----


export const VERDICT_LABEL: Record<Verdict, string> = {
  supported: "Supported",
  contradicted: "Contradicted",
  insufficient_evidence: "Insufficient evidence",
};

export const VERDICT_ICON: Record<Verdict, string> = {
  supported: "✓",
  contradicted: "✕",
  insufficient_evidence: "?",
};

/** Plain words for each "count it differently" choice (mirrors second_opinion/variants.py). */
const CHOICE_WORDS: Record<string, Record<string, string>> = {
  subtype_source: { rna_call: "RNA-seq subtype label", study_2012_label: "2012 study subtype label" },
  sex_filter: { everyone: "everyone", women_only: "women only" },
  sample_scope: { primary_tumors: "primary tumors only", all_samples: "all samples" },
};
const CHOICE_ORDER = ["subtype_source", "sex_filter", "sample_scope"] as const;

/** "subtype_source=study_2012_label" -> "using the 2012 study subtype label". */
export function flipWords(flip: string): string {
  const [choice, option] = flip.split("=");
  const words = CHOICE_WORDS[choice]?.[option] ?? flip.replaceAll("_", " ");
  if (choice === "subtype_source") return `using the ${words}`;
  if (choice === "sex_filter") return `counting ${words}`;
  if (choice === "sample_scope") return `counting ${words}`;
  return words;
}

/** "rna_call|women_only|primary_tumors" -> "RNA-seq subtype label · women only · primary tumors only". */
export function variantWords(variantId: string): string {
  return variantId
    .split("|")
    .map((option, i) => CHOICE_WORDS[CHOICE_ORDER[i]]?.[option] ?? option.replaceAll("_", " "))
    .join(" · ");
}

const count = new Intl.NumberFormat("en-US");
const signed = new Intl.NumberFormat("en-US", { maximumFractionDigits: 3, signDisplay: "always" });

/** A computed number with its denominator, never a bare percentage. */
export function formatFact(fact: Fact, type: Claim["type"]): string {
  const { value, numerator: num, denominator: den } = fact;
  const ofTotal = num !== null && den !== null ? `${count.format(num)} of ${count.format(den)}` : null;

  if (type === "COMPARISON" && value !== null) {
    const n = fact.extra;
    const groups = n.n_a !== undefined && n.n_b !== undefined ? ` (groups of ${n.n_a} and ${n.n_b})` : "";
    return `difference in means ${signed.format(value)}${groups}`;
  }
  if (type === "SHARE" && value !== null && ofTotal) return `${value.toFixed(1)}% (${ofTotal})`;
  if (ofTotal) return ofTotal;
  return value !== null ? count.format(value) : "unknown";
}

export type SolidityText = { short: string; long: string };

/** "Robust (8 of 8)" / "Fragile: flips when using the 2012 study subtype label" / not tested. */
export function solidityText(result: ClaimResult): SolidityText {
  const checked = result.variants.filter((v) => v.verdict !== null);
  const same = checked.filter((v) => v.verdict === result.verdict).length;
  if (result.solidity === "holds_under_every_variant") {
    return {
      short: `Robust (${same} of ${checked.length})`,
      long: `The verdict is the same under all ${checked.length} ways of counting.`,
    };
  }
  if (result.solidity === "holds_under_some_variants") {
    const when = result.flips_on.length ? result.flips_on.map(flipWords).join(" or ") : "counting differently";
    return {
      short: `Fragile: flips when ${when}`,
      long: `The verdict holds in ${same} of ${checked.length} ways of counting; it flips when ${when}.`,
    };
  }
  return { short: "Robustness not tested", long: "Only shares and comparisons are recounted different ways." };
}
