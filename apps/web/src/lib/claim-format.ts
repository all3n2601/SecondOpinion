// Plain-word labels for claims, shared by the claims list and the audit board.

import { PLAN_OP_LABEL } from "./ai-plan";
import type { Claim, ClaimResult, ClaimType, Fact, Verdict } from "./types";

export const TYPE_LABEL: Record<ClaimType, string> = {
  COUNT: "Count",
  SHARE: "Share",
  COMPARISON: "Comparison",
  AGREEMENT: "Agreement",
  COVERAGE: "Coverage",
  RANK: "Ranking",
  RATIO: "Ratio",
  STATISTIC: "Statistic",
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
  if (claim.source === "ai") return "The AI helper will propose a check plan when you run the audit";
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
  // "subtype_source=study_2012_label + sex_filter=women_only": several choices at once
  if (flip.includes("+")) return flip.split("+").map((part) => flipWords(part.trim())).join(" and ");
  const [choice, option] = flip.split("=");
  const words = CHOICE_WORDS[choice]?.[option] ?? flip.replaceAll("_", " ");
  if (choice === "subtype_source") return `using the ${words}`;
  if (choice === "sex_filter") return `counting ${words}`;
  if (choice === "sample_scope") return `counting ${words}`;
  return words;
}

/** Mirrors PRIMARY_VARIANT in second_opinion/variants.py: the organizers' definition. */
export const PRIMARY_VARIANT_ID = "rna_call|everyone|primary_tumors";

/** The choices a way of counting changes from the primary one, as flips: ["sample_scope=all_samples"]. */
export function variantChanges(variantId: string): string[] {
  const primary = PRIMARY_VARIANT_ID.split("|");
  return variantId
    .split("|")
    .flatMap((option, i) => (option !== primary[i] && CHOICE_ORDER[i] ? [`${CHOICE_ORDER[i]}=${option}`] : []));
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

  const x = fact.extra;
  if (type === "RATIO" && value !== null && num !== null && den !== null) {
    return `${value.toFixed(2)} to 1 (${count.format(num)} vs ${count.format(den)})`;
  }
  if (type === "RANK" && typeof x.ranks === "string") {
    const end = x.least ? "lowest" : "highest";
    // a group ranked by its mean protein level, or by its rate of something (deaths in Stage IV)
    if (typeof x.protein === "string") return `${x.ranks}; ${end} ${x.protein}: ${x.leader}`;
    if (x.rate) return `${x.ranks}; ${end} rate: ${x.leader}`;
    return `${x.ranks}; most common: ${x.leader} (${count.format(Number(x.leader_count))} of ${count.format(Number(x.total))})`;
  }
  if (type === "STATISTIC" && value !== null) {
    return `${value.toFixed(1)} years${den !== null ? ` (${count.format(den)} with a recorded age)` : ""}`;
  }
  if (type === "COMPARISON" && typeof x.share_a === "number" && typeof x.share_b === "number") {
    return `${x.group_a} ${x.share_a}% (${count.format(Number(x.hits_a))} of ${count.format(Number(x.n_a))}) vs ${x.group_b} ${x.share_b}% (${count.format(Number(x.hits_b))} of ${count.format(Number(x.n_b))})`;
  }
  if (type === "COMPARISON" && value !== null) {
    const n = fact.extra;
    const groups = n.n_a !== undefined && n.n_b !== undefined ? ` (groups of ${n.n_a} and ${n.n_b})` : "";
    return `difference in means ${signed.format(value)}${groups}`;
  }
  if (type === "SHARE" && value !== null && ofTotal) return `${value.toFixed(1)}% (${ofTotal})`;
  if (ofTotal) return ofTotal;
  return value !== null ? count.format(value) : "unknown";
}

const STAT_NAME: Record<string, string> = { median: "median", mean: "mean", min: "youngest", max: "oldest" };

function ordinal(n: number): string {
  const suffix = 10 <= n % 100 && n % 100 <= 20 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}

/**
 * The computed number for a result, with its denominator. Rule-based claims use `formatFact` as always;
 * a claim checked by an AI-proposed plan is formatted by what the plan measured.
 */
export function formatResultFact(result: ClaimResult): string {
  const { fact, claim } = result;
  if (!fact) return "";
  const plan = result.ai_plan?.plan;
  if (!plan) return formatFact(fact, claim.type);
  const x = fact.extra;
  switch (plan.op) {
    case "share":
      return formatFact(fact, "SHARE");
    case "count":
      return formatFact(fact, "COUNT");
    case "compare_means":
      return formatFact(fact, "COMPARISON");
    case "summary_stat": {
      if (fact.value === null) return "unknown";
      const n = typeof x.n === "number" ? ` (${count.format(x.n)} samples with an age)` : "";
      return `${STAT_NAME[plan.stat] ?? plan.stat} ${fact.value.toFixed(1)} years${n}`;
    }
    case "rank": {
      if (fact.value === null) return "unknown";
      const of = typeof x.ranked_of === "number" ? x.ranked_of : 5;
      return `${ordinal(fact.value)} of ${of}${x.tied ? " (tied)" : ""}`;
    }
    case "order": {
      const ca = x.count_a;
      const cb = x.count_b;
      if (typeof ca === "number" && typeof cb === "number") {
        return `${plan.category_a} ${count.format(ca)} vs ${plan.category_b} ${count.format(cb)}`;
      }
      return fact.value !== null ? `${plan.category_a} minus ${plan.category_b}: ${signed.format(fact.value)}` : "unknown";
    }
  }
}

/** The type chip for a result: what the check measured when an AI-proposed plan ran, else the claim's own type. */
export function resultTypeLabel(result: ClaimResult): string {
  const plan = result.ai_plan?.plan;
  return plan ? PLAN_OP_LABEL[plan.op] : TYPE_LABEL[result.claim.type];
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
    const reasons = result.flips_on.map(flipWords);
    const when = reasons.length ? reasons.join(" or ") : "counting differently";
    // The card shows the first two reasons in one line; the tooltip and the evidence page list them all.
    const shown = reasons.length > 2 ? `${reasons.slice(0, 2).join(" or ")}, and ${reasons.length - 2} more` : when;
    return {
      short: `Fragile: flips when ${shown}`,
      long: `The verdict holds in ${same} of ${checked.length} ways of counting; it flips when ${when}.`,
    };
  }
  return { short: "Robustness not tested", long: "Only shares and comparisons are recounted different ways." };
}
