import { describe, expect, it } from "vitest";
import {
  causeTeaser,
  countingRange,
  diagnose,
  matchesStated,
  measureOf,
  restsOn,
  restsTeaser,
  robustnessTeaser,
  statedFigure,
  statedWords,
  storyLines,
} from "./insights";
import type { ClaimParams, ClaimResult, ClaimType, Fact, VariantResult, Verdict } from "./types";

const PARAMS: ClaimParams = {
  stated_value: 62,
  stated_high: null,
  stated_total: null,
  unit: "percent",
  decimals: null,
  approximate: true,
  subject: null,
  subtype: null,
  direction: null,
  measure: null,
  group_a: null,
  group_b: null,
};

function fact(numerator: number, denominator: number, unknown = 0, value?: number): Fact {
  return {
    label: "",
    value: value ?? (100 * numerator) / denominator,
    numerator,
    denominator,
    sample_ids: [],
    files: [],
    code: "",
    unknown_count: unknown,
    extra: {},
  };
}

function variant(id: string, f: Fact | null, verdict: Verdict | null = "contradicted"): VariantResult {
  return { variant_id: id, fact: f, verdict };
}

function result(o: { type?: ClaimType; params?: Partial<ClaimParams>; verdict?: Verdict; fact?: Fact | null; variants?: VariantResult[] } = {}): ClaimResult {
  return {
    claim: {
      id: "C2",
      text: "Luminal A is about 62% of primary tumors.",
      sentence_index: 1,
      type: o.type ?? "SHARE",
      params: { ...PARAMS, ...o.params },
      needed_data: null,
      clinical_terms: [],
    },
    verdict: o.verdict ?? "contradicted",
    solidity: "holds_under_every_variant",
    fact: o.fact === undefined ? fact(421, 844, 257) : o.fact,
    correct_value: null,
    missing_evidence: null,
    variants: o.variants ?? [],
    flips_on: [],
    skeptic: null,
    ladder: [],
    limitation: null,
    review: null,
  };
}

// The practice report's C2, as the audit returns it on release A (values from a real run).
const C2_VARIANTS = [
  variant("rna_call|everyone|primary_tumors", fact(421, 844, 257)),
  variant("rna_call|everyone|all_samples", fact(434, 956, 0, 45.39748953974895)),
  variant("rna_call|women_only|primary_tumors", fact(416, 833, 0, 49.93997599039616)),
  variant("study_2012_label|everyone|primary_tumors", fact(231, 522, 0, 44.252873563218394)),
  variant("study_2012_label|everyone|all_samples", fact(231, 522, 0, 44.252873563218394)),
];

describe("measureOf", () => {
  it("reads a share as percent and a count as count", () => {
    expect(measureOf(result())).toBe("percent");
    expect(measureOf(result({ type: "COUNT", params: { unit: null } }))).toBe("count");
  });
  it("skips ranks, ratios and multi-part sentences", () => {
    expect(measureOf(result({ type: "RANK", params: { unit: "rank" } }))).toBeNull();
    expect(measureOf(result({ type: "RATIO", params: { unit: "ratio" } }))).toBeNull();
    expect(measureOf({ ...result(), parts: [result()] })).toBeNull();
  });
});

describe("countingRange", () => {
  it("sorts every way low to high and marks the primary one", () => {
    const range = countingRange(result({ variants: C2_VARIANTS }))!;
    expect(range.ways.map((w) => w.value.toFixed(1))).toEqual(["44.3", "44.3", "45.4", "49.9", "49.9"]);
    expect(range.low.value).toBeCloseTo(44.25, 2);
    expect(range.high.value).toBeCloseTo(49.94, 2);
    expect(range.ways.filter((w) => w.primary)).toHaveLength(1);
    expect(range.distinct).toBe(3);
  });
  it("is null with fewer than two values", () => {
    expect(countingRange(result())).toBeNull();
    expect(countingRange(result({ variants: [C2_VARIANTS[0], variant("rna_call|everyone|all_samples", null)] }))).toBeNull();
  });
  it("uses the count, not a share, for a count claim", () => {
    const counts = [variant("rna_call|everyone|primary_tumors", fact(535, 1101)), variant("rna_call|everyone|all_samples", fact(560, 1200))];
    const range = countingRange(result({ type: "COUNT", params: { unit: null, stated_value: 535 }, variants: counts }))!;
    expect(range.ways.map((w) => w.value)).toEqual([535, 560]);
  });
});

describe("restsOn", () => {
  it("splits the population and bounds the share whatever the missing values are", () => {
    const r = restsOn(result())!;
    expect(r).toMatchObject({ inGroup: 421, otherValue: 423, leftOut: 257, total: 1101 });
    expect(r.bounds![0]).toBeCloseTo(38.24, 2);
    expect(r.bounds![1]).toBeCloseTo(61.58, 2);
  });
  it("has no bounds when nothing was left out, or for a count", () => {
    expect(restsOn(result({ fact: fact(421, 844) }))!.bounds).toBeNull();
    expect(restsOn(result({ type: "COUNT", params: { unit: null }, fact: fact(535, 1101, 10) }))!.bounds).toBeNull();
  });
  it("is null without a numerator and denominator, or with a numerator above the denominator", () => {
    expect(restsOn(result({ fact: { ...fact(1, 2), numerator: null } }))).toBeNull();
    expect(restsOn(result({ fact: fact(5, 3) }))).toBeNull();
  });
});

describe("matchesStated", () => {
  const about = { value: 62, high: null, approximate: true, decimals: 0 };
  it("allows two points for an approximate share", () => {
    expect(matchesStated(60, about, "percent")).toBe(true);
    expect(matchesStated(59.9, about, "percent")).toBe(false);
  });
  it("rounds to the report's precision for an exact share", () => {
    const exact = { value: 49.9, high: null, approximate: false, decimals: 1 };
    expect(matchesStated(49.88, exact, "percent")).toBe(true);
    expect(matchesStated(49.84, exact, "percent")).toBe(false);
  });
  it("allows 2% of the count for an approximate count, nothing for an exact one", () => {
    expect(matchesStated(102, { value: 100, high: null, approximate: true, decimals: 0 }, "count")).toBe(true);
    expect(matchesStated(101, { value: 100, high: null, approximate: false, decimals: 0 }, "count")).toBe(false);
  });
  it("needs a value inside a stated range", () => {
    const range = { value: 40, high: 45, approximate: false, decimals: 0 };
    expect(matchesStated(44.3, range, "percent")).toBe(true);
    expect(matchesStated(45.4, range, "percent")).toBe(false);
  });
});

describe("statedFigure", () => {
  it("skips bounds, 'every one' and figures out of a stated total", () => {
    expect(statedFigure(result({ params: { bound: "gt" } }))).toBeNull();
    expect(statedFigure(result({ params: { unit: "all" } }))).toBeNull();
    expect(statedFigure(result({ params: { stated_total: 12 } }))).toBeNull();
    expect(statedFigure(result())).toEqual({ value: 62, high: null, approximate: true, decimals: 0 });
  });
  it("reads the AI helper's figure when the rules found none", () => {
    const r = result({ params: { stated_value: null, approximate: false } });
    r.ai_plan = {
      answerable: true,
      needed_data: null,
      plan: { op: "share", where: [], numerator: [] },
      stated: { kind: "percent", span: "62%", value: 62, high: null, total: null, approximate: false, relation: null },
      rationale: "",
    };
    expect(statedFigure(r)!.value).toBe(62);
  });
});

describe("diagnose", () => {
  it("is null unless the tool contradicted a single stated figure", () => {
    expect(diagnose(result({ verdict: "supported", variants: C2_VARIANTS }))).toBeNull();
    expect(diagnose(result({ params: { bound: "gt" }, variants: C2_VARIANTS }))).toBeNull();
  });
  it("tries every other way and the slips from the counts, nearest first, without repeats", () => {
    const d = diagnose(result({ variants: C2_VARIANTS }))!;
    const values = d.tried.map((t) => t.value.toFixed(1));
    expect(new Set(values).size).toBe(values.length);
    // nearest to 62: the upper bound (every left-out sample counted in the group), 61.6
    expect(values[0]).toBe("61.6");
    expect(values).toContain("38.2");
    expect(values).toContain("50.1"); // the share outside the group
    expect(d.matches.map((m) => m.value.toFixed(1))).toEqual(["61.6"]);
  });
  it("names a way of counting in plain words", () => {
    const d = diagnose(result({ params: { stated_value: 45.4, approximate: false }, fact: fact(421, 844), variants: C2_VARIANTS }))!;
    expect(d.matches).toHaveLength(1);
    expect(d.matches[0]).toMatchObject({ way: true, how: "count all samples, not primary tumors only" });
  });
  it("joins several changed choices", () => {
    const d = diagnose(result({ params: { stated_value: 44.3, approximate: false }, fact: fact(421, 844), variants: C2_VARIANTS }))!;
    expect(d.matches[0].how).toBe("use the 2012 study subtype label instead of the RNA-seq one");
  });
  it("tries the whole group for a count", () => {
    const d = diagnose(
      result({ type: "COUNT", params: { unit: null, stated_value: 1101, approximate: false }, fact: fact(535, 1101, 0, 535) }),
    )!;
    expect(d.matches.map((m) => m.how)).toEqual(["count everyone checked, not only those in the group"]);
  });
});

describe("statedWords", () => {
  it("words the figure as the report does", () => {
    expect(statedWords({ value: 62, high: null, approximate: true, decimals: 0 }, "percent")).toBe("about 62%");
    expect(statedWords({ value: 40, high: 45, approximate: false, decimals: 0 }, "percent")).toBe("40 to 45%");
    expect(statedWords({ value: 535, high: null, approximate: false, decimals: 0 }, "count")).toBe("535");
  });
});

describe("teasers", () => {
  it("says how many have a value, and none missing when none are", () => {
    expect(restsTeaser(restsOn(result())!)).toBe("844 of 1,101 have a value");
    expect(restsTeaser(restsOn(result({ type: "COUNT", params: { unit: null }, fact: fact(535, 1101) }))!)).toBe(
      "535 of 1,101 counted, none missing",
    );
  });
  it("says whether any reading gives the stated figure", () => {
    expect(causeTeaser(diagnose(result({ variants: C2_VARIANTS }))!)).toBe("1 reading gives about 62%");
    expect(causeTeaser(diagnose(result({ params: { stated_value: 90 }, variants: C2_VARIANTS }))!)).toBe(
      "No reading we tried gives about 90%",
    );
  });
  it("counts several matching readings", () => {
    const d = diagnose(result({ params: { stated_value: 45, approximate: true }, fact: fact(421, 844), variants: C2_VARIANTS }))!;
    expect(d.matches.length).toBeGreaterThan(1);
    expect(causeTeaser(d)).toBe(`${d.matches.length} readings give about 45%`);
  });
  it("counts agreeing ways, or is null with none", () => {
    expect(robustnessTeaser(result({ variants: C2_VARIANTS }))).toBe("5 of 5 ways agree");
    expect(robustnessTeaser(result())).toBeNull();
  });
  it("mentions skeptic tests when they ran", () => {
    const r = result({ variants: C2_VARIANTS });
    r.skeptic = { shuffle_p: 0.01, n_sites: 3, site_flips: [] };
    expect(robustnessTeaser(r)).toBe("5 of 5 ways agree; skeptic tests apply");
  });
});

describe("diagnose: final review fixes", () => {
  it("does not call a reading a match when it barely moves the data's own value", () => {
    // 49.0% against "about 52%": the share outside the group (51.0%) is within "about" of 52 but explains nothing.
    const near = diagnose(result({ params: { stated_value: 52 }, fact: fact(490, 1000) }))!;
    expect(near.matches).toEqual([]);
    // 59.9% with 5 missing against "about 62%": counting the 5 inside gives 60.1%, a hair from the data.
    const tiny = diagnose(result({ fact: fact(599, 1000, 5) }))!;
    expect(tiny.matches).toEqual([]);
  });
  it("still finds a match that is far from the data's own value", () => {
    expect(diagnose(result({ variants: C2_VARIANTS }))!.matches.map((m) => m.value.toFixed(1))).toEqual(["61.6"]);
  });
  it("is null when there is nothing to try", () => {
    const r = result({ type: "COUNT", params: { unit: null, stated_value: 400 }, fact: { ...fact(421, 844), denominator: null } });
    expect(diagnose(r)).toBeNull();
  });
  it("is null for a claim checked through the AI helper's plan", () => {
    const r = result({ variants: C2_VARIANTS });
    r.ai_plan = {
      answerable: true,
      needed_data: null,
      plan: { op: "share", where: [], numerator: [] },
      stated: { kind: "percent", span: "about 62%", value: 62, high: null, total: null, approximate: true, relation: null },
      rationale: "",
    };
    expect(diagnose(r)).toBeNull();
  });
  it("reads an AI-plan share that states a count as a count", () => {
    const r = result({ params: { stated_value: null, unit: null } });
    r.ai_plan = {
      answerable: true,
      needed_data: null,
      plan: { op: "share", where: [], numerator: [] },
      stated: { kind: "count", span: "421", value: 421, high: null, total: null, approximate: false, relation: null },
      rationale: "",
    };
    expect(measureOf(r)).toBe("count");
  });
  it("gives every way of counting plain words for the story view", () => {
    const d = diagnose(result({ params: { stated_value: 44.3, approximate: false }, fact: fact(421, 844), variants: C2_VARIANTS }))!;
    expect(d.matches[0].plain).toBeTruthy();
    expect(d.matches[0].plain).not.toMatch(/RNA|2012|primary tumors/);
  });
});

describe("storyLines", () => {
  it("tells the story of a wrong figure in plain words", () => {
    const lines = storyLines(result({ variants: C2_VARIANTS }));
    expect(lines[0]).toBe("However we counted it, the data gave between 44.3% and 49.9%, never close to the report's about 62%.");
    expect(lines.join(" ")).toContain("count every record missing this detail as part of the group");
  });
  it("drops the wrong-figure lines once a reviewer has overridden the verdict", () => {
    const r = result({ variants: C2_VARIANTS });
    r.review = { decision: "override", final_verdict: "supported", reason: "rounding", reviewer_role: "Researcher" };
    const lines = storyLines(r);
    expect(lines[0]).toBe("However we counted it, the data gave between 44.3% and 49.9%.");
    expect(lines.join(" ")).not.toMatch(/never close|worked out|none gives/);
  });
});
