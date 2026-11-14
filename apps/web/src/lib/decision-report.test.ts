import { describe, expect, it } from "vitest";
import { actionLabel, actionSummary, claimAction } from "./decision-report";
import type { ClaimResult, LadderSegment, Verdict } from "./types";

const REWRITE: LadderSegment[] = [
  { text: "about 62%", struck: true, inserted: false },
  { text: "49.9%", struck: false, inserted: true },
];
const UNCHANGED: LadderSegment[] = [{ text: "535 of 1,101", struck: false, inserted: false }];

function result(verdict: Verdict, ladder: LadderSegment[], overriddenTo?: Verdict): ClaimResult {
  return {
    claim: { id: "C1", text: "x", sentence_index: 0, type: "SHARE", params: {}, needed_data: null, clinical_terms: [] },
    verdict,
    ladder,
    review: overriddenTo
      ? { decision: "override", final_verdict: overriddenTo, reason: "r", reviewer_role: "Researcher" }
      : null,
  } as unknown as ClaimResult;
}

describe("what a decision means for each claim", () => {
  it("keeps a supported claim whatever the decision", () => {
    for (const d of ["Proceed", "Fix a problem", "Narrow the question", "Stop"] as const) {
      expect(claimAction(result("supported", UNCHANGED), d)).toBe("keep");
    }
  });

  it("rewrites with the ladder under Fix and Narrow, by hand when it has no wording", () => {
    expect(claimAction(result("contradicted", REWRITE), "Fix a problem")).toBe("rewritten");
    expect(claimAction(result("insufficient_evidence", REWRITE), "Narrow the question")).toBe("rewritten");
    expect(claimAction(result("contradicted", UNCHANGED), "Fix a problem")).toBe("by-hand");
  });

  it("holds under Stop and keeps under Proceed", () => {
    expect(claimAction(result("contradicted", REWRITE), "Stop")).toBe("hold");
    expect(claimAction(result("contradicted", REWRITE), "Proceed")).toBe("kept-anyway");
  });

  it("follows the reviewer's final verdict, not the tool's", () => {
    expect(claimAction(result("contradicted", REWRITE, "supported"), "Fix a problem")).toBe("keep");
    expect(claimAction(result("supported", UNCHANGED, "contradicted"), "Fix a problem")).toBe("by-hand");
  });

  it("says narrow where the decision narrows", () => {
    expect(actionLabel("rewritten", "Fix a problem")).toBe("Reworded");
    expect(actionLabel("rewritten", "Narrow the question")).toBe("Narrowed");
    expect(actionLabel("by-hand", "Narrow the question")).toBe("Narrow or take out");
  });

  it("sums up the report in a fixed order", () => {
    const results = [result("supported", UNCHANGED), result("contradicted", REWRITE), result("contradicted", UNCHANGED)];
    expect(actionSummary(results, "Fix a problem")).toBe("3 claims: 1 kept, 1 reworded, 1 to reword by hand");
    expect(actionSummary(results, "Stop")).toBe("3 claims: 1 kept, 2 on hold");
  });
});
