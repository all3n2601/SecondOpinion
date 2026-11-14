import { describe, expect, it } from "vitest";
import { evidenceHref, markAnchor, markIdFromHash, reportHref, returnHref, returnView } from "./report-nav";

describe("report navigation", () => {
  it("names a claim's mark", () => {
    expect(markAnchor("C2")).toBe("mark-C2");
  });

  it("reads the claim id from the hash, nothing otherwise", () => {
    expect(markIdFromHash("#mark-C2")).toBe("C2");
    expect(markIdFromHash("#mark-C2.1")).toBe("C2.1");
    expect(markIdFromHash("")).toBeNull();
    expect(markIdFromHash("#mark-")).toBeNull();
    expect(markIdFromHash("#content")).toBeNull();
    expect(markIdFromHash("#review-C2")).toBeNull();
  });

  it("ignores a garbled hash instead of throwing", () => {
    expect(markIdFromHash("#mark-%")).toBeNull();
    expect(markIdFromHash("#mark-%E0")).toBeNull();
  });

  it("builds the way back to the report, and round-trips odd ids", () => {
    expect(reportHref()).toBe("/board/report");
    expect(reportHref("C2")).toBe("/board/report#mark-C2");
    const odd = reportHref("C 2/x");
    expect(markIdFromHash(odd.slice(odd.indexOf("#")))).toBe("C 2/x");
  });

  it("builds evidence links that remember they came from the report", () => {
    expect(evidenceHref("C2")).toBe("/board/C2");
    expect(evidenceHref("C2", "report")).toBe("/board/C2?from=report");
    expect(evidenceHref("C2", "decision")).toBe("/board/C2?from=decision");
  });

  it("builds the way back to the decision", () => {
    expect(returnHref("decision")).toBe("/decision");
    expect(returnHref("decision", "C2")).toBe("/decision#mark-C2");
    expect(returnHref("report", "C2")).toBe(reportHref("C2"));
  });

  it("reads the from search param", () => {
    expect(returnView("report")).toBe("report");
    expect(returnView("decision")).toBe("decision");
    expect(returnView(["decision", "x"])).toBe("decision");
    expect(returnView(undefined)).toBeNull();
    expect(returnView("board")).toBeNull();
  });
});
