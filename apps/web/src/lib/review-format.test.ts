import { describe, expect, it } from "vitest";
import { countText, samplesText } from "./review";
import type { Fact } from "./types";

function fact(o: Partial<Fact>): Fact {
  return {
    label: "", value: null, numerator: null, denominator: null, sample_ids: [], files: [], code: "",
    unknown_count: 0, extra: {}, ...o,
  };
}

describe("countText", () => {
  it("writes a lone whole number with commas", () => {
    expect(countText(fact({ value: 1101 }))).toBe("1,101");
  });
  it("keeps up to three decimals for a mean or a ratio", () => {
    expect(countText(fact({ value: 3.3949579 }))).toBe("3.395");
  });
  it("gives the figure with its total and what was left out", () => {
    expect(countText(fact({ value: 59, numerator: 85, denominator: 144, unknown_count: 59 }))).toBe("85 of 144; 59 unknown, left out");
  });
});

describe("samplesText", () => {
  it("counts the listed samples", () => {
    expect(samplesText(fact({ numerator: 2, sample_ids: ["a", "b"] }))).toBe("2");
  });
  it("says 0 only when the check counted none", () => {
    expect(samplesText(fact({ numerator: 0, denominator: 178 }))).toBe("0");
  });
  it("says not listed when a check (a rank, a rate) does not list samples", () => {
    expect(samplesText(fact({ value: 1, numerator: 15, denominator: 20 }))).toBe("not listed");
  });
});
