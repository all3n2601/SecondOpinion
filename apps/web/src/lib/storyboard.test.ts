import { describe, expect, it } from "vitest";
import { agreedReason, beatAt, buildScenes, indexOfScene, sceneDuration, shouldAdvance } from "./storyboard";

describe("buildScenes", () => {
  it("has no claim scenes before the report is read", () => {
    expect(buildScenes(null).map((s) => s.id)).toEqual(["cover", "report", "data", "findings", "review", "decision", "result"]);
  });

  it("puts one scene per claim between the data and the findings", () => {
    const ids = buildScenes(["C1", "C2", "C3"]).map((s) => s.id);
    expect(ids).toEqual([
      "cover",
      "report",
      "data",
      "claim-C1",
      "claim-C2",
      "claim-C3",
      "findings",
      "review",
      "decision",
      "result",
    ]);
  });

  it("lights up each claim in the report scene", () => {
    expect(buildScenes(["C1", "C2"]).find((s) => s.id === "report")!.beats).toBe(3);
  });

  it("makes the review and the decision gates: a person acts there", () => {
    const gates = buildScenes(["C1"]).filter((s) => s.gate).map((s) => s.id);
    expect(gates).toEqual(["cover", "review", "decision", "result"]);
  });
});

describe("beatAt", () => {
  const claim = buildScenes(["C1"]).find((s) => s.kind === "claim")!;

  it("starts at the first beat and steps with time", () => {
    expect(beatAt(claim, 0)).toBe(0);
    expect(beatAt(claim, claim.beatMs - 1)).toBe(0);
    expect(beatAt(claim, claim.beatMs)).toBe(1);
  });

  it("never runs past the last beat", () => {
    expect(beatAt(claim, 10 * sceneDuration(claim))).toBe(claim.beats - 1);
  });

  it("shows a one-beat scene whole", () => {
    expect(beatAt(buildScenes(null)[0], 0)).toBe(0);
  });
});

describe("shouldAdvance", () => {
  const [, report] = buildScenes(["C1"]);
  const review = buildScenes(["C1"]).find((s) => s.kind === "review")!;

  it("moves on once the scene's time is up", () => {
    expect(shouldAdvance(report, sceneDuration(report) - 1, true, false)).toBe(false);
    expect(shouldAdvance(report, sceneDuration(report), true, false)).toBe(true);
  });

  it("waits for the data the scene shows", () => {
    expect(shouldAdvance(report, 1e9, false, false)).toBe(false);
  });

  it("never passes a gate on time alone", () => {
    expect(shouldAdvance(review, 1e9, true, false)).toBe(false);
  });

  it("goes on from a passed gate after a short hold", () => {
    expect(shouldAdvance(review, 0, true, true)).toBe(false);
    expect(shouldAdvance(review, review.holdMs, true, true)).toBe(true);
  });
});

describe("indexOfScene", () => {
  it("finds a scene after the list is rebuilt with claims", () => {
    expect(indexOfScene(buildScenes(["C1", "C2"]), "data")).toBe(2);
    expect(indexOfScene(buildScenes(null), "claim-C2")).toBe(0);
  });
});

describe("agreedReason", () => {
  it("names the rule the suggestion came from", () => {
    expect(agreedReason("Rule 2: at least one claim is contradicted.")).toBe(
      "Agreed with the tool's suggestion (Rule 2: at least one claim is contradicted) after reviewing every verdict.",
    );
  });
});
