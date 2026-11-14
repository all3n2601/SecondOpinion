import { describe, expect, it } from "vitest";
import { describeParams } from "./claim-format";
import { notFullyRead, notFullyReadText } from "./coverage";
import { templateFor } from "./narrate";
import { keyNumber } from "./review";
import type { Claim, ClaimResult, RoleView } from "./types";

const GATED_REASON =
  'this sentence also states "N0" and "15", which the rules could not check; a person should check it';

function claim(overrides: Partial<Claim> = {}): Claim {
  return {
    id: "C1",
    text: "44 of 516 N0 patients died, against 15 of 77 N3 patients.",
    sentence_index: 0,
    type: "UNMAPPED",
    params: {
      stated_value: null, stated_high: null, stated_total: null, unit: null, decimals: null, approximate: false,
      subject: null, subtype: null, direction: null, measure: null, group_a: null, group_b: null,
    },
    needed_data: GATED_REASON,
    clinical_terms: [],
    coverage_gaps: ["N0", "15"],
    ...overrides,
  };
}

function insufficient(c: Claim): ClaimResult {
  return {
    claim: c, verdict: "insufficient_evidence", solidity: "not_applicable", fact: null, correct_value: null,
    missing_evidence: c.needed_data, variants: [], flips_on: [], skeptic: null, ladder: [], limitation: null,
    review: null,
  } as ClaimResult;
}

describe("a claim the rules did not read in full", () => {
  it("is told apart by its coverage gaps", () => {
    expect(notFullyRead(claim())).toBe(true);
    expect(notFullyRead(claim({ coverage_gaps: [] }))).toBe(false);
    expect(notFullyRead(claim({ coverage_gaps: undefined }))).toBe(false);
  });

  it("says it was not fully read, never that the data would need more", () => {
    const r = insufficient(claim());
    expect(notFullyReadText(r)).toBe(`The rules could not read every part of this sentence, so it was not checked: ${GATED_REASON}.`);
    expect(keyNumber(r)).toBe(`Not fully read: ${GATED_REASON}`);
    expect(describeParams(claim())).toBe('Not fully read: the rules could not check "N0", "15"; a person should check it');
    for (const view of ["story", "checklist", "evidence", "raw"] as RoleView[]) {
      const text = templateFor(view, [r]).claims.C1;
      expect(text).toMatch(/\bread\b/);
      expect(text).not.toMatch(/does not have|lacks|too little|Not enough data/);
    }
  });

  it("keeps the old wording for a claim without gaps", () => {
    const r = insufficient(claim({ coverage_gaps: [], needed_data: "treatment data" }));
    expect(keyNumber(r)).toBe("Would need treatment data");
    expect(describeParams(claim({ coverage_gaps: [] }))).toBe("No check exists yet for this kind of claim");
  });
});
