import { describe, expect, it } from "vitest";
import { entryFromHash, hashFor, isOwnHash, nextToReview, OVERVIEW, previousEntry, reviewStatus } from "./review-nav";
import type { ClaimResult, Review, Verdict } from "./types";

function claim(id: string, review: Review | null = null, verdict: Verdict = "contradicted"): ClaimResult {
  return {
    claim: {
      id,
      text: `Claim ${id}.`,
      sentence_index: 0,
      type: "SHARE",
      params: {
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
      },
      needed_data: null,
      clinical_terms: [],
    },
    verdict,
    solidity: "not_applicable",
    fact: null,
    correct_value: null,
    missing_evidence: null,
    variants: [],
    flips_on: [],
    skeptic: null,
    ladder: [],
    limitation: null,
    review,
  };
}

const accept: Review = { decision: "accept", final_verdict: "contradicted", reason: "", reviewer_role: "Researcher" };
const override: Review = { decision: "override", final_verdict: "supported", reason: "rounding", reviewer_role: "Researcher" };

// C1 reviewed, C2 and C3 not.
const claims = [claim("C1", accept), claim("C2"), claim("C3")];
const allReviewed = [claim("C1", accept), claim("C2", accept), claim("C3", override)];

describe("review navigation", () => {
  it("reads the selected claim from the hash, Overview otherwise", () => {
    expect(entryFromHash("#review-C2", ["C1", "C2"])).toBe("C2");
    expect(entryFromHash("", ["C1"])).toBe(OVERVIEW);
    expect(entryFromHash("#review-C9", ["C1", "C2"])).toBe(OVERVIEW);
    expect(entryFromHash("#elsewhere", ["C1"])).toBe(OVERVIEW);
  });

  it("opens Overview for a garbled hash instead of throwing", () => {
    expect(entryFromHash("#review-%", ["C1"])).toBe(OVERVIEW);
    expect(entryFromHash("#review-%E0", ["C1"])).toBe(OVERVIEW);
  });

  it("tells its own hashes from other fragments, such as the skip link's", () => {
    expect(isOwnHash("")).toBe(true);
    expect(isOwnHash("#review-C2")).toBe(true);
    expect(isOwnHash("#review-C9")).toBe(true);
    expect(isOwnHash("#content")).toBe(false);
  });

  it("writes the hash back", () => {
    expect(hashFor(OVERVIEW)).toBe("");
    expect(hashFor("C2")).toBe("#review-C2");
  });

  it("goes to the next claim still to review, wrapping", () => {
    expect(nextToReview(claims, OVERVIEW)).toBe("C2");
    expect(nextToReview(claims, "C2")).toBe("C3");
    expect(nextToReview(claims, "C3")).toBe("C2");
    expect(nextToReview(claims, "C1")).toBe("C2");
  });

  it("never returns the claim just saved, even before its review shows", () => {
    const onlyC3Unreviewed = [claim("C1", accept), claim("C2", accept), claim("C3")];
    expect(nextToReview(onlyC3Unreviewed, "C3")).toBe(OVERVIEW);
  });

  it("opens Overview when every claim is reviewed", () => {
    expect(nextToReview(allReviewed, "C3")).toBe(OVERVIEW);
    expect(nextToReview([], OVERVIEW)).toBe(OVERVIEW);
  });

  it("steps back to the previous claim, then Overview", () => {
    expect(previousEntry(["C1", "C2"], "C2")).toBe("C1");
    expect(previousEntry(["C1", "C2"], "C1")).toBe(OVERVIEW);
  });

  it("words a claim's review status", () => {
    expect(reviewStatus(claim("C2"))).toBe("to review");
    expect(reviewStatus(claim("C1", accept))).toBe("accepted");
    expect(reviewStatus(claim("C3", override))).toBe("overridden to Supported");
  });
});
