import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { narrate } from "./api";
import { claimSlots } from "./narrate";
import { clearNarrationCache, narrationClaims, readCachedNarration, writeCachedNarration } from "./use-narration";
import type { ClaimResult } from "./types";

const STORE_KEY = "secondopinion:narration:v1";

function stubStorage(): Map<string, string> {
  const data = new Map<string, string>();
  vi.stubGlobal("sessionStorage", {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  });
  return data;
}

const value = { headline: "{supported} of {total} held up.", caption: "{reviewed} reviewed.", claims: { C1: "{stated} was checked." } };

beforeEach(() => {
  clearNarrationCache();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("narration cache", () => {
  it("returns what was written", () => {
    stubStorage();
    writeCachedNarration("k1", value);
    expect(readCachedNarration("k1")).toEqual(value);
    expect(readCachedNarration("other")).toBeNull();
  });

  it("keeps other keys when one more is written", () => {
    stubStorage();
    writeCachedNarration("k1", value);
    writeCachedNarration("k2", { ...value, headline: "Other." });
    expect(readCachedNarration("k1")).toEqual(value);
    expect(readCachedNarration("k2")?.headline).toBe("Other.");
  });

  it("is emptied by clearNarrationCache", () => {
    const data = stubStorage();
    writeCachedNarration("k1", value);
    clearNarrationCache();
    expect(readCachedNarration("k1")).toBeNull();
    expect(data.has(STORE_KEY)).toBe(false);
  });

  it("reads null when the stored text is corrupt JSON", () => {
    const data = stubStorage();
    data.set(STORE_KEY, "{not json");
    expect(readCachedNarration("k1")).toBeNull();
  });

  it("reads null for a stored entry of the wrong shape", () => {
    const data = stubStorage();
    data.set(STORE_KEY, JSON.stringify({ k1: { headline: 5, caption: "x", claims: {} }, k2: { headline: "h", caption: "c", claims: { C1: 3 } } }));
    expect(readCachedNarration("k1")).toBeNull();
    expect(readCachedNarration("k2")).toBeNull();
  });

  it("never throws when storage is missing or throws", () => {
    vi.stubGlobal("sessionStorage", undefined);
    expect(() => writeCachedNarration("k1", value)).not.toThrow();
    expect(readCachedNarration("k1")).toBeNull();
    expect(() => clearNarrationCache()).not.toThrow();
    vi.stubGlobal("sessionStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("quota");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    });
    expect(() => writeCachedNarration("k1", value)).not.toThrow();
    expect(readCachedNarration("k1")).toBeNull();
    expect(() => clearNarrationCache()).not.toThrow();
  });

  it("keeps only the most recent entries", () => {
    stubStorage();
    for (let i = 0; i < 30; i++) writeCachedNarration(`k${i}`, value);
    expect(readCachedNarration("k0")).toBeNull();
    expect(readCachedNarration("k29")).toEqual(value);
  });
});

describe("narrate request", () => {
  it("sends only id, final verdict, solidity, overridden, text and slot names per claim", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ source: "template", headline: null, caption: null, claims: null, reason: "x" })));
    vi.stubGlobal("fetch", fetchMock);
    const claim = {
      claim: {
        id: "Cx",
        text: "About 62% were female.",
        sentence_index: 0,
        type: "SHARE",
        params: { stated_value: 62, stated_high: null, stated_total: null, unit: "percent", decimals: null, approximate: true },
      },
      verdict: "contradicted",
      solidity: "holds_under_some_variants",
      fact: { label: "share", value: 48, numerator: 48, denominator: 100, sample_ids: ["S1"], files: [], code: "", unknown_count: 0, extra: {} },
      correct_value: "48.0% (48 of 100)",
      variants: [
        { variant_id: "v1", fact: null, verdict: "contradicted" },
        { variant_id: "v2", fact: null, verdict: "supported" },
      ],
      ladder: [],
      review: { decision: "override", final_verdict: "supported", reason: "no", reviewer_role: "Researcher" },
    } as unknown as ClaimResult;
    await narrate("story", [claim]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, { body: string }];
    expect(url).toBe("/api/ai/narrate");
    expect(JSON.parse(init.body)).toEqual({
      view: "story",
      claims: [
        {
          id: "Cx",
          verdict: "supported",
          solidity: "holds_under_some_variants",
          overridden: true,
          text: "About 62% were female.",
          slots: ["stated", "data_shows", "direction", "agree", "ways"],
        },
      ],
    });
    // Names only: none of the slot values (counts, figures, direction) or sample ids appear outside the report sentence.
    const rest = init.body.replace("About 62% were female.", "");
    expect(Object.values(claimSlots(claim))).toEqual(["about 62%", "48.0% (48 of 100)", "lower than", "1", "2"]);
    expect(rest).not.toMatch(/[0-9]|lower than|S1/);
  });

  it("sends an empty slot list for a claim with nothing to fill", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ source: "template", headline: null, caption: null, claims: null, reason: "x" })));
    vi.stubGlobal("fetch", fetchMock);
    const claim = {
      claim: { id: "C2", text: "Treatment worked.", sentence_index: 1, type: "RANK", params: { stated_value: null, stated_high: null, stated_total: null, unit: null } },
      verdict: "insufficient_evidence",
      solidity: "not_applicable",
      fact: null,
      correct_value: null,
      variants: [],
      ladder: [],
      review: null,
    } as unknown as ClaimResult;
    await narrate("checklist", [claim]);
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, { body: string }];
    expect(JSON.parse(init.body).claims[0].slots).toEqual([]);
  });
});

describe("narrationClaims", () => {
  const claims = [] as ClaimResult[];
  it("asks for nothing until saved state has loaded and the role's view is settled", () => {
    expect(narrationClaims(false, false, claims)).toBeNull();
    expect(narrationClaims(true, false, claims)).toBeNull(); // roles still loading: the "checklist" placeholder
    expect(narrationClaims(false, true, claims)).toBeNull();
    expect(narrationClaims(true, true, claims)).toBe(claims);
  });
  it("stays null with no audit", () => {
    expect(narrationClaims(true, true, null)).toBeNull();
  });
});
