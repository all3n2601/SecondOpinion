// Deeper readings of one checked claim, from numbers the audit already computed and returned: the value under
// every way of counting, what a share rests on (and how far the left-out samples could move it), and which
// common slip, if any, gives the report's figure. Pure functions: no React, no fetch, no AI. Every number here
// is arithmetic on the audit's own facts.

import { paramsFromAiPlan } from "./ai-plan";
import { flipWords, PRIMARY_VARIANT_ID, variantChanges, variantWords } from "./claim-format";
import { formatCount } from "./review";
import type { ClaimParams, ClaimResult, Fact, Verdict } from "./types";

export type Measure = "percent" | "count";

/** The claim's params, with the AI helper's reading filling what the rules left blank (as ClaimVsData does). */
function paramsOf(result: ClaimResult): ClaimParams {
  const ai = result.ai_plan;
  return ai?.plan ? paramsFromAiPlan(result.claim.params, ai.plan, ai.stated) : result.claim.params;
}

/** Percent or count when the claim is one figure we can place on a number line; null for anything else. */
export function measureOf(result: ClaimResult): Measure | null {
  if (result.parts?.length) return null;
  const op = result.ai_plan?.plan?.op;
  if (op) return op === "share" ? "percent" : op === "count" ? "count" : null;
  const { type } = result.claim;
  const unit = result.claim.params.unit;
  if (unit === "percent" || (unit === null && (type === "SHARE" || type === "AGREEMENT"))) return "percent";
  if (type === "COUNT" && (unit === null || unit === "count")) return "count";
  return null;
}

/** The figure a fact gives under a measure: the percentage, or the count. */
export function factValue(fact: Fact | null, measure: Measure): number | null {
  if (!fact) return null;
  if (measure === "percent") {
    if (fact.numerator !== null && fact.denominator) return (100 * fact.numerator) / fact.denominator;
    return fact.value;
  }
  return fact.numerator ?? fact.value;
}

const oneDecimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

/** "49.9%" or "421". */
export function formatMeasure(value: number, measure: Measure): string {
  return measure === "percent" ? `${oneDecimal.format(value)}%` : formatCount(Math.round(value));
}

// ---- 1. The value under every way of counting ----

export interface WayOfCounting {
  id: string;
  /** "RNA-seq subtype label · everyone · all samples". */
  words: string;
  value: number;
  verdict: Verdict | null;
  primary: boolean;
}

export interface CountingRange {
  measure: Measure;
  ways: WayOfCounting[];
  low: WayOfCounting;
  high: WayOfCounting;
  /** How many different answers the ways give (several ways can land on the same one). */
  distinct: number;
}

/** Every way of counting that gave a value, sorted low to high; null with fewer than two. */
export function countingRange(result: ClaimResult): CountingRange | null {
  const measure = measureOf(result);
  if (!measure) return null;
  const ways: WayOfCounting[] = [];
  for (const v of result.variants) {
    const value = factValue(v.fact, measure);
    if (value === null || !Number.isFinite(value)) continue;
    ways.push({ id: v.variant_id, words: variantWords(v.variant_id), value, verdict: v.verdict, primary: v.variant_id === PRIMARY_VARIANT_ID });
  }
  if (ways.length < 2) return null;
  ways.sort((a, b) => a.value - b.value);
  const distinct = new Set(ways.map((w) => formatMeasure(w.value, measure))).size;
  return { measure, ways, low: ways[0], high: ways[ways.length - 1], distinct };
}

// ---- 2. What the figure rests on ----

export interface RestsOn {
  measure: Measure;
  /** Samples counted in the claim's group (the numerator). */
  inGroup: number;
  /** Samples with a value that is not the claim's. */
  otherValue: number;
  /** Samples with no value recorded, left out of the denominator. */
  leftOut: number;
  /** All samples the claim is about: in group + other value + left out. */
  total: number;
  /**
   * Percent only, and only with samples left out: the share if every left-out sample were outside the group,
   * and if every one were inside it. The true share lies between, whatever the missing values are.
   */
  bounds: [number, number] | null;
}

export function restsOn(result: ClaimResult): RestsOn | null {
  const measure = measureOf(result);
  const f = result.fact;
  if (!measure || !f || f.numerator === null || f.denominator === null) return null;
  const { numerator: n, denominator: d } = f;
  const leftOut = Math.max(0, f.unknown_count || 0);
  if (d <= 0 || n < 0 || n > d) return null;
  const total = d + leftOut;
  const bounds: [number, number] | null =
    measure === "percent" && leftOut > 0 ? [(100 * n) / total, (100 * (n + leftOut)) / total] : null;
  return { measure, inGroup: n, otherValue: d - n, leftOut, total, bounds };
}

// ---- 3. Which slip gives the report's figure ----

export interface Stated {
  value: number;
  high: number | null;
  approximate: boolean;
  decimals: number;
}

function inferDecimals(n: number): number {
  const text = String(n);
  const dot = text.indexOf(".");
  return dot < 0 || text.includes("e") ? 0 : text.length - dot - 1;
}

/** The one figure the report states; null for a bound ("more than"), "every one", a figure out of a stated total, or none. */
export function statedFigure(result: ClaimResult): Stated | null {
  const p = paramsOf(result);
  if (p.stated_value === null || p.bound || p.unit === "all" || p.stated_total !== null) return null;
  return {
    value: p.stated_value,
    high: p.stated_high,
    approximate: p.approximate,
    decimals: p.decimals ?? inferDecimals(p.stated_value),
  };
}

const roundTo = (x: number, decimals: number) => {
  const f = 10 ** decimals;
  return Math.round(x * f + 1e-9) / f;
};

/**
 * Whether `x` would pass as the stated figure. Mirrors the percent and count tolerance in second_opinion/verdict.py:
 * a range must contain it, "about" allows 2 points (percent) or 2% (count), an exact figure must match after
 * rounding to the report's own precision.
 */
export function matchesStated(x: number, stated: Stated, measure: Measure): boolean {
  if (stated.high !== null) return stated.value - 1e-9 <= x && x <= stated.high + 1e-9;
  if (stated.approximate) {
    return measure === "percent" ? Math.abs(x - stated.value) <= 2 + 1e-9 : Math.abs(x - stated.value) <= 0.02 * Math.abs(x) + 1e-9;
  }
  return measure === "percent" ? roundTo(x, stated.decimals) === stated.value : Math.abs(x - stated.value) < 1e-9;
}

export interface Alternative {
  /** Words that finish "…if you ": "count all samples, not primary tumors only". */
  how: string;
  value: number;
  /** A way of counting the audit itself ran (as opposed to a slip worked out from the counts). */
  way: boolean;
  /** `how` for readers with little data background, when it needs plainer words. */
  plain?: string;
}

export interface Diagnosis {
  measure: Measure;
  stated: Stated;
  /** Every other reading we tried, nearest to the stated figure first. */
  tried: Alternative[];
  /** The readings that give the report's figure. */
  matches: Alternative[];
}

const SCOPE_WORDS: Record<string, string> = {
  "sample_scope=all_samples": "count all samples, not primary tumors only",
  "sex_filter=women_only": "count women only",
  "subtype_source=study_2012_label": "use the 2012 study subtype label instead of the RNA-seq one",
};

function wayHow(variantId: string): string {
  const changes = variantChanges(variantId).map((c) => SCOPE_WORDS[c] ?? flipWords(c));
  return changes.length > 1 ? `${changes.slice(0, -1).join(", ")} and ${changes[changes.length - 1]}` : (changes[0] ?? "count it the standard way");
}

/**
 * For a contradicted figure: the readings a report author might have used by mistake, and which of them give
 * the stated figure. Null when the tool did not contradict the claim, or there is no single stated figure.
 */
export function diagnose(result: ClaimResult): Diagnosis | null {
  if (result.verdict !== "contradicted") return null;
  const measure = measureOf(result);
  const stated = statedFigure(result);
  if (!measure || !stated) return null;
  const tried: Alternative[] = [];

  for (const v of result.variants) {
    if (v.variant_id === PRIMARY_VARIANT_ID) continue;
    const value = factValue(v.fact, measure);
    if (value !== null && Number.isFinite(value)) tried.push({ how: wayHow(v.variant_id), value, way: true });
  }

  const f = result.fact;
  const rests = restsOn(result);
  if (measure === "percent" && rests) {
    const unknown = formatCount(rests.leftOut);
    if (rests.bounds) {
      tried.push({
        how: `count the ${unknown} samples with no value recorded as outside the group`,
        plain: "count every record missing this detail as not part of the group",
        value: rests.bounds[0],
        way: false,
      });
      tried.push({
        how: `count the ${unknown} samples with no value recorded as inside the group`,
        plain: "count every record missing this detail as part of the group",
        value: rests.bounds[1],
        way: false,
      });
    }
    tried.push({ how: "report the share outside the group instead of inside it", value: 100 - (100 * rests.inGroup) / (rests.inGroup + rests.otherValue), way: false });
  }
  if (measure === "count" && f) {
    if (f.denominator !== null) tried.push({ how: "count everyone checked, not only those in the group", value: f.denominator, way: false });
    if (f.denominator !== null && f.unknown_count > 0) {
      tried.push({ how: "count everyone, including those with no value recorded", value: f.denominator + f.unknown_count, way: false });
    }
  }

  // The same value reached two ways reads as one reading; keep the first (a way the audit ran comes first).
  const seen = new Set<string>();
  const unique = tried.filter((t) => {
    const key = formatMeasure(t.value, measure);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const target = stated.high !== null ? (stated.value + stated.high) / 2 : stated.value;
  unique.sort((a, b) => Math.abs(a.value - target) - Math.abs(b.value - target));
  return { measure, stated, tried: unique, matches: unique.filter((t) => matchesStated(t.value, stated, measure)) };
}

/** "about 62%", "55 to 62%", "421". */
export function statedWords(stated: Stated, measure: Measure): string {
  const n = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
  const unit = measure === "percent" ? "%" : "";
  if (stated.high !== null) return `${n.format(stated.value)} to ${n.format(stated.high)}${unit}`;
  return `${stated.approximate ? "about " : ""}${n.format(stated.value)}${unit}`;
}
