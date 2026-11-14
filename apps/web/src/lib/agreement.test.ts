import { describe, expect, it } from "vitest";
import { agreement, agreementText, solidityText } from "./claim-format";
import { claimSlots } from "./narrate";
import type { ClaimParams, ClaimResult, Fact, Solidity, VariantResult, Verdict } from "./types";

const PARAMS: ClaimParams = {
  stated_value: 59,
  stated_high: null,
  stated_total: null,
  unit: "percent",
  decimals: null,
  approximate: false,
  subject: null,
  subtype: null,
  direction: null,
  measure: null,
  group_a: null,
  group_b: null,
};

function fact(numerator: number, denominator: number): Fact {
  return {
    label: "", value: (100 * numerator) / denominator, numerator, denominator,
    sample_ids: [], files: [], code: "", unknown_count: 0, extra: {},
  };
}

/** Eight ways of counting; the first `same` give `verdict`, the rest the other verdict. */
function ways(same: number, verdict: Verdict = "supported"): VariantResult[] {
  return Array.from({ length: 8 }, (_, i) => ({
    variant_id: `way${i}`,
    fact: null,
    verdict: i < same ? verdict : verdict === "supported" ? "contradicted" : "supported",
  }));
}

function result(o: {
  id?: string;
  label?: string;
  solidity?: Solidity;
  variants?: VariantResult[];
  flips?: string[];
  parts?: ClaimResult[];
} = {}): ClaimResult {
  return {
    claim: {
      id: o.id ?? "C1", text: "CDH1 was mutated in 59% of lobular carcinomas.", sentence_index: 0, type: "SHARE",
      params: PARAMS, needed_data: null, clinical_terms: [], part_label: o.label ?? "",
    },
    verdict: "supported",
    solidity: o.solidity ?? "holds_under_every_variant",
    fact: fact(85, 144),
    correct_value: null,
    missing_evidence: null,
    variants: o.variants ?? ways(8),
    flips_on: o.flips ?? [],
    skeptic: null,
    ladder: [],
    limitation: null,
    review: null,
    parts: o.parts,
  };
}

// The four-part CDH1 / PIK3CA sentence: the first part holds every way, the PIK3CA parts change.
const FRAGILE_PIK3CA = ["subtype_source=study_2012_label"];
const C1 = result({
  solidity: "holds_under_some_variants",
  variants: ways(8), // the backend copies one part's ways of counting here: the first part's 8 of 8
  flips: ["sex_filter=women_only", ...FRAGILE_PIK3CA],
  parts: [
    result({ id: "C1.1", label: "59% of lobular" }),
    result({ id: "C1.2", label: "1.6% of ductal" }),
    result({ id: "C1.3", label: "48.5% of Luminal A", solidity: "holds_under_some_variants", variants: ways(6), flips: FRAGILE_PIK3CA }),
    result({ id: "C1.4", label: "6.6% of Basal-like", solidity: "holds_under_some_variants", variants: ways(5), flips: ["sex_filter=women_only"] }),
  ],
});

describe("agreement", () => {
  it("counts ways of counting for a claim with one part", () => {
    expect(agreement(result({ variants: ways(7) }))).toEqual({ kind: "ways", agree: 7, ways: 8 });
    expect(agreementText(agreement(result({ variants: ways(7) }))!)).toBe("7 of 8 ways of counting agree");
  });

  it("counts parts for a sentence with several parts, not the first part's ways of counting", () => {
    const a = agreement(C1)!;
    expect(a.kind).toBe("parts");
    expect(agreementText(a)).toBe(
      "2 of 4 parts hold under every way of counting; “48.5% of Luminal A” and “6.6% of Basal-like” change when " +
        "using the 2012 study subtype label or counting women only",
    );
    expect(agreementText(a, false)).toBe("2 of 4 parts hold under every way of counting");
  });

  it("leaves out parts that were not recounted, and gives nothing when none were", () => {
    const untested = result({ solidity: "not_applicable", variants: [] });
    const mixed = result({ parts: [result({ label: "a" }), untested] });
    expect(agreementText(agreement(mixed)!)).toBe("1 of 1 part holds under every way of counting");
    expect(agreement(result({ parts: [untested, untested] }))).toBeNull();
    expect(agreement(result({ variants: [] }))).toBeNull();
  });
});

describe("a Fragile tag and the line under it agree", () => {
  it("never says 8 of 8 for a fragile sentence with several parts", () => {
    const text = solidityText(C1);
    expect(text.short).toBe("Fragile: flips when counting women only or using the 2012 study subtype label");
    expect(text.long).not.toMatch(/8 of 8/);
    expect(text.long).toMatch(/^2 of 4 parts hold under every way of counting/);
  });

  it("narration gets parts_hold instead of agree/ways, and no single figure for the whole sentence", () => {
    const slots = claimSlots(C1);
    expect(slots.parts_hold).toBe("2 of 4");
    expect(slots.agree).toBeUndefined();
    expect(slots.ways).toBeUndefined();
    expect(slots.data_shows).toBeUndefined();
  });

  it("keeps agree/ways for a claim with one part", () => {
    const slots = claimSlots(result({ variants: ways(8) }));
    expect([slots.agree, slots.ways, slots.parts_hold]).toEqual(["8", "8", undefined]);
  });
});
