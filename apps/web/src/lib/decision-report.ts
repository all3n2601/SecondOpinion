// What a recorded decision means for each claim, for the report shown again after the decision. Pure: no React.
// The verdict that counts is the final one, after review. Fix a problem and Narrow the question rewrite the
// claims that do not hold with the Claim Ladder's wording, where it has one; Stop holds them; Proceed keeps them.

import { finalVerdict, plural } from "./review";
import type { ClaimResult, Decision, LadderSegment } from "./types";

/**
 * - `keep`: the claim holds, so it stays as written.
 * - `kept-anyway`: it does not hold, but the decision was Proceed, so it stays as written.
 * - `rewritten`: it does not hold and the decision rewrites it with the Claim Ladder's wording.
 * - `by-hand`: it does not hold and the decision rewrites it, but the ladder has no wording, so a person must.
 * - `hold`: it does not hold and the decision was Stop.
 */
export type ClaimAction = "keep" | "kept-anyway" | "rewritten" | "by-hand" | "hold";

const ACTION_ORDER: ClaimAction[] = ["keep", "rewritten", "by-hand", "kept-anyway", "hold"];

/** True when the ladder actually changes the sentence. */
export function ladderRewrites(segments: LadderSegment[]): boolean {
  return segments.some((s) => s.struck || s.inserted);
}

export function claimAction(result: ClaimResult, decision: Decision): ClaimAction {
  if (finalVerdict(result) === "supported") return "keep";
  if (decision === "Proceed") return "kept-anyway";
  if (decision === "Stop") return "hold";
  // A reviewer who overrode a supported verdict leaves the ladder with nothing to change: that one is by hand.
  return ladderRewrites(result.ladder) ? "rewritten" : "by-hand";
}

/** The action as a short label in the claim's stamp; Narrow the question narrows where Fix a problem rewords. */
export function actionLabel(action: ClaimAction, decision: Decision): string {
  const narrow = decision === "Narrow the question";
  switch (action) {
    case "keep":
      return "Keep";
    case "kept-anyway":
      return "Kept as written";
    case "rewritten":
      return narrow ? "Narrowed" : "Reworded";
    case "by-hand":
      return narrow ? "Narrow or take out" : "Reword by hand";
    case "hold":
      return "Hold";
  }
}

/** One line on what the report becomes under this decision. */
export const DECISION_HEADLINE: Record<Decision, string> = {
  Proceed: "The report goes ahead as written.",
  "Fix a problem": "The report with each claim that does not match the data reworded to what the data shows.",
  "Narrow the question": "The report limited to what the data can answer.",
  Stop: "The report is on hold. The marked claims are why.",
};

/** "3 claims: 1 kept, 1 reworded, 1 to reword by hand", in a fixed order. */
export function actionSummary(results: ClaimResult[], decision: Decision): string {
  const counts = new Map<ClaimAction, number>();
  for (const r of results) {
    const action = claimAction(r, decision);
    counts.set(action, (counts.get(action) ?? 0) + 1);
  }
  const parts = ACTION_ORDER.filter((a) => counts.has(a)).map((a) => `${counts.get(a)} ${SUMMARY_WORDS[a](decision)}`);
  return `${plural(results.length, "claim", "claims")}: ${parts.join(", ")}`;
}

const SUMMARY_WORDS: Record<ClaimAction, (decision: Decision) => string> = {
  keep: () => "kept",
  "kept-anyway": () => "kept although not supported",
  rewritten: (d) => (d === "Narrow the question" ? "narrowed" : "reworded"),
  "by-hand": (d) => (d === "Narrow the question" ? "to narrow or take out by hand" : "to reword by hand"),
  hold: () => "on hold",
};
