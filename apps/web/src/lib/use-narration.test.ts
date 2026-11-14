import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { narrate } from "./api";
import { clearNarrationCache, readCachedNarration, writeCachedNarration } from "./use-narration";
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
  it("sends only id, final verdict, solidity, overridden and text per claim", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ source: "template", headline: null, caption: null, claims: null, reason: "x" })));
    vi.stubGlobal("fetch", fetchMock);
    const claim = {
      claim: { id: "C1", text: "About 62% were female.", sentence_index: 0, type: "SHARE", params: { stated_value: 62 } },
      verdict: "supported",
      solidity: "holds_under_some_variants",
      fact: { value: 62, numerator: 62, denominator: 100, sample_ids: ["S1"] },
      correct_value: 61,
      review: { decision: "override", final_verdict: "contradicted", reason: "no", reviewer_role: "Researcher" },
    } as unknown as ClaimResult;
    await narrate("story", [claim]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, { body: string }];
    expect(url).toBe("/api/ai/narrate");
    expect(JSON.parse(init.body)).toEqual({
      view: "story",
      claims: [{ id: "C1", verdict: "contradicted", solidity: "holds_under_some_variants", overridden: true, text: "About 62% were female." }],
    });
  });
});
