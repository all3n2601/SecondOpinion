// Plain-words rendering of the optional AI helper's check plan. Pure functions, no React and only
// type imports, so they can be checked on their own with node. The plan is data the helper proposed;
// these functions only describe it, they never run it.

import type { ClaimParams, PlanFilter, Plan, PlanOp, Stated } from "./types";

const SAMPLE_NOUN: Record<string, string> = {
  primary: "primary tumors",
  normal_tissue: "normal tissue samples",
  metastatic: "metastatic samples",
};

const LAYER_WORDS: Record<string, string> = {
  survival: "survival data",
  mutation: "mutation data",
  copy_number: "copy number data",
  protein: "protein data",
  rna: "RNA data",
};

/** Words for a numeric comparison, after "an age at diagnosis". */
const AGE_OP_WORDS: Record<string, string> = {
  eq: "of",
  gt: "over",
  gte: "of at least",
  lt: "under",
  lte: "of at most",
};

const SUBTYPE_FIELD_WORDS: Record<string, string> = {
  subtype_rna: "RNA subtype",
  subtype_2012: "2012 study subtype",
};

const STAT_WORDS: Record<string, string> = { median: "median", mean: "mean", min: "lowest", max: "highest" };

/** Short plain label for each operation, for the type chip on a result. */
export const PLAN_OP_LABEL: Record<PlanOp, string> = {
  count: "Count",
  share: "Share",
  compare_means: "Comparison",
  summary_stat: "Summary statistic",
  rank: "Rank",
  order: "Order",
};

const underscored = (s: string) => s.replaceAll("_", " ");

function values(v: PlanFilter["value"]): string[] {
  if (Array.isArray(v)) return v.map(String);
  return v === null || v === undefined ? [] : [String(v)];
}

function orList(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} or ${items[items.length - 1]}`;
}

function andList(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/** "a Basal-like RNA subtype call", "ER-positive status", "survival data": a condition that follows "with". */
function clause(f: PlanFilter): string {
  const vs = values(f.value);
  const list = orList(vs);
  switch (f.field) {
    case "subtype_rna":
    case "subtype_2012": {
      const what = SUBTYPE_FIELD_WORDS[f.field];
      const call = f.field === "subtype_rna" ? "call" : "label";
      if (f.op === "is_known") return `${f.field === "subtype_rna" ? "an" : "a"} ${what} ${call}`;
      if (f.op === "eq" || f.op === "in") return `${/^[aeiou]/i.test(list) ? "an" : "a"} ${list} ${what} ${call}`;
      return `${what} ${f.op} ${list}`;
    }
    case "er_status":
    case "her2_status": {
      const name = f.field === "er_status" ? "ER" : "HER2";
      if (f.op === "is_known") return `a recorded ${name} status`;
      if (f.op === "eq" || f.op === "in") return `${orList(vs.map((v) => `${name}-${v}`))} status`;
      return `${name} status ${f.op} ${list}`;
    }
    case "has_layer": {
      const words = vs.map((v) => LAYER_WORDS[v] ?? `${underscored(v)} data`);
      return orList(words) || "a data file";
    }
    case "age_years": {
      if (f.op === "is_known") return "a recorded age at diagnosis";
      return `an age at diagnosis ${AGE_OP_WORDS[f.op] ?? f.op} ${list}`;
    }
    case "sex":
      return `sex ${f.op === "eq" || f.op === "in" ? "is" : underscored(f.op)} ${list}`;
    case "sample_type":
      return `sample type ${list}`;
    default:
      return `${underscored(String(f.field))} ${f.op === "eq" ? "is" : underscored(String(f.op))} ${list}`.trim();
  }
}

/** "female primary tumors with a Basal-like RNA subtype call and survival data". */
export function describePopulation(filters: PlanFilter[]): string {
  let noun = "samples";
  let adjective = "";
  const clauses: string[] = [];
  for (const f of filters) {
    const vs = values(f.value);
    if (f.field === "sample_type" && (f.op === "eq" || f.op === "in") && vs.length > 0) {
      noun = orList(vs.map((v) => SAMPLE_NOUN[v] ?? `${underscored(v)} samples`));
    } else if (f.field === "sex" && f.op === "eq" && vs.length === 1) {
      adjective = `${vs[0]} `;
    } else {
      clauses.push(clause(f));
    }
  }
  return `${adjective}${noun}${clauses.length ? ` with ${andList(clauses)}` : ""}`;
}

/** Filters that, as a share numerator, also narrow the denominator to rows where the field is known (mirrors the executor). */
const KNOWN_IN_DENOMINATOR = new Set(["subtype_rna", "subtype_2012", "er_status", "her2_status", "age_years"]);

function groupWords(field: string, value: string): string {
  if (field === "er_status") return `ER-${value}`;
  if (field === "her2_status") return `HER2-${value}`;
  return value;
}

/** One line per step, in plain words, from the structured plan. Never raw JSON. */
export function describePlan(plan: Plan): string[] {
  switch (plan.op) {
    case "count":
      return [
        plan.of === "patients"
          ? `Count the distinct patients behind ${describePopulation(plan.where)}.`
          : `Count ${describePopulation(plan.where)}.`,
      ];

    case "share": {
      const numerator = describePopulation([...plan.where, ...plan.numerator]);
      const known = plan.numerator
        .filter((f) => KNOWN_IN_DENOMINATOR.has(f.field) && (f.op === "eq" || f.op === "in"))
        .map((f): PlanFilter => ({ field: f.field, op: "is_known", value: null }));
      const denominator = describePopulation([...plan.where, ...known]);
      return [`Count ${numerator}, out of ${denominator}.`, "Report that as a percentage."];
    }

    case "compare_means": {
      const unrestricted = !plan.where.some((f) => f.field === "sample_type");
      const population = describePopulation(
        unrestricted ? [{ field: "sample_type", op: "eq", value: "primary" }, ...plan.where] : plan.where,
      );
      return [
        `Compare the mean ${plan.measure} protein level in ${groupWords(plan.group_field, plan.group_a)} samples with ${groupWords(plan.group_field, plan.group_b)} samples.`,
        `Use ${population}.`,
        "The result is the first group's mean minus the second group's mean.",
      ];
    }

    case "summary_stat":
      return [`Find the ${STAT_WORDS[plan.stat] ?? plan.stat} age at diagnosis, in years, among ${describePopulation(plan.where)}.`];

    case "rank": {
      const what = SUBTYPE_FIELD_WORDS[plan.category_field] ?? "subtype";
      return [
        `Rank ${plan.category} among the five ${what}s by number of samples, with 1 as the most common.`,
        `Count only ${describePopulation([...plan.where, { field: plan.category_field, op: "is_known", value: null }])}.`,
      ];
    }

    case "order": {
      const what = SUBTYPE_FIELD_WORDS[plan.category_field] ?? "subtype";
      return [
        `Count the samples called ${plan.category_a} and the samples called ${plan.category_b} by ${what}, and see which group is larger.`,
        `Count only ${describePopulation([...plan.where, { field: plan.category_field, op: "is_known", value: null }])}.`,
      ];
    }
  }
}

/** The claim the helper says the sentence makes, in a few plain words. */
export function describeStated(stated: Stated): string {
  const n = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
  const hedge = stated.approximate ? "about " : "";
  if (stated.value === null) {
    if (stated.relation) return stated.relation === "more" ? "that one group is larger or higher" : "that one group is smaller or lower";
    return "";
  }
  if (stated.high !== null) return `${n.format(stated.value)} to ${n.format(stated.high)}${stated.kind === "percent" ? "%" : ""}`;
  const value = `${hedge}${n.format(stated.value)}${stated.kind === "percent" ? "%" : ""}`;
  return stated.total !== null ? `${value} of ${n.format(stated.total)}` : value;
}

/**
 * Fill in what the rules left blank on a claim (a sentence the helper took on has empty params) from the
 * helper's reading, so the existing gauges can draw the stated figure. Values the rules did read are kept.
 */
export function paramsFromAiPlan(params: ClaimParams, plan: Plan | null, stated: Stated | null): ClaimParams {
  const out: ClaimParams = { ...params };
  if (stated) {
    out.stated_value ??= stated.value;
    out.stated_high ??= stated.high;
    out.stated_total ??= stated.total;
    if (stated.approximate) out.approximate = true;
    out.unit ??= stated.kind === "percent" ? "percent" : stated.kind === "count" ? "count" : null;
    if (stated.relation) out.direction ??= stated.relation === "more" ? "higher" : "lower";
  }
  if (plan?.op === "compare_means") {
    out.measure ??= plan.measure;
    out.group_a ??= plan.group_a;
    out.group_b ??= plan.group_b;
  }
  return out;
}
