import { describe, expect, it } from "vitest";
import {
  auditSlots,
  claimSlots,
  fillSlots,
  narrationKey,
  renderNarration,
  STORY_VERDICT_WORDS,
  templateFor,
} from "./narrate";
import type { ClaimResult, ClaimType, RoleView, Verdict } from "./types";

const VIEWS: RoleView[] = ["story", "checklist", "evidence", "raw"];

let seq = 0;

function result(overrides: Partial<ClaimResult> & { type?: ClaimType; id?: string } = {}): ClaimResult {
  const { type, id, ...rest } = overrides;
  seq += 1;
  const claimId = id ?? `c${seq}`;
  return {
    claim: {
      id: claimId,
      text: `Claim ${claimId}.`,
      sentence_index: seq,
      type: type ?? "SHARE",
      params: {
        stated_value: 62,
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
      },
      needed_data: null,
      clinical_terms: [],
    },
    verdict: "supported",
    solidity: "holds_under_every_variant",
    fact: {
      label: "share",
      value: 62,
      numerator: 62,
      denominator: 100,
      sample_ids: [],
      files: [],
      code: "",
      unknown_count: 0,
      extra: {},
    },
    correct_value: null,
    missing_evidence: null,
    variants: [],
    flips_on: [],
    skeptic: null,
    ladder: [],
    limitation: null,
    review: null,
    ...rest,
  };
}

function review(final: Verdict): ClaimResult["review"] {
  return { decision: final === "supported" ? "accept" : "override", final_verdict: final, reason: "", reviewer_role: "Researcher" };
}

function mixed(): ClaimResult[] {
  return [
    result({ id: "a" }),
    result({
      id: "b",
      verdict: "contradicted",
      correct_value: "48.0% (48 of 100)",
      solidity: "holds_under_some_variants",
      fact: { ...result().fact!, value: 48, numerator: 48 },
      variants: [
        { variant_id: "v1", fact: null, verdict: "contradicted" },
        { variant_id: "v2", fact: null, verdict: "supported" },
        { variant_id: "v3", fact: null, verdict: "contradicted" },
      ],
    }),
    result({ id: "c", verdict: "insufficient_evidence", fact: null, solidity: "not_applicable", type: "RANK" }),
    result({ id: "d", verdict: "contradicted", correct_value: "7 of 12", type: "COUNT", review: review("supported") }),
  ];
}

describe("fillSlots", () => {
  it("fills named blanks", () => {
    expect(fillSlots("{a} of {b}", { a: "2", b: "7" })).toBe("2 of 7");
  });
  it("returns null when a slot has no value", () => {
    expect(fillSlots("{a}", {})).toBeNull();
    expect(fillSlots("{constructor}", {})).toBeNull();
  });
  it("leaves text without slots alone", () => {
    expect(fillSlots("plain words.", {})).toBe("plain words.");
  });
});

describe("auditSlots", () => {
  it("counts by the final verdict, after overrides", () => {
    const slots = auditSlots(mixed());
    expect(slots).toMatchObject({ supported: "2", contradicted: "1", insufficient: "1", total: "4", reviewed: "1", fragile: "1" });
  });
  it("formats large counts with separators", () => {
    const many = Array.from({ length: 1200 }, () => result());
    expect(auditSlots(many).total).toBe("1,200");
  });
});

describe("claimSlots", () => {
  it("has no stated for a claim with parts", () => {
    const part = result();
    expect(claimSlots(result({ parts: [part] }))).not.toHaveProperty("stated");
  });
  it("words the stated figure with a percent sign and an about hedge", () => {
    const r = result();
    r.claim.params.approximate = true;
    expect(claimSlots(r).stated).toBe("about 62%");
  });
  it("prefers the AI plan's reading of the claim", () => {
    const r = result({
      ai_plan: {
        answerable: true,
        needed_data: null,
        plan: null,
        stated: { kind: "count", span: "7", value: 7, high: null, total: 12, approximate: false, relation: null },
        rationale: "",
      },
    });
    expect(claimSlots(r).stated).toBe("7 of 12");
  });
  it("gives data_shows from correct_value when contradicted, from the fact when supported, none when insufficient", () => {
    const [a, b, c] = mixed();
    expect(claimSlots(b).data_shows).toBe("48.0% (48 of 100)");
    expect(claimSlots(a).data_shows).toBe("62.0% (62 of 100)");
    expect(claimSlots(c)).not.toHaveProperty("data_shows");
  });
  it("direction is lower than for a SHARE claim stated 62 with data 48", () => {
    const [, b] = mixed();
    expect(claimSlots(b).direction).toBe("lower than");
  });
  it("direction covers higher and the same, and only SHARE or COUNT claims", () => {
    const higher = result({ fact: { ...result().fact!, value: 70 } });
    const same = result();
    const rank = result({ type: "RANK" });
    expect(claimSlots(higher).direction).toBe("higher than");
    expect(claimSlots(same).direction).toBe("the same as");
    expect(claimSlots(rank)).not.toHaveProperty("direction");
  });
  it("omits direction when a contradicted claim would read as the same as the report", () => {
    const sameCount = result({ type: "COUNT", verdict: "contradicted", correct_value: "7 of 15", fact: { ...result().fact!, value: 7 } });
    sameCount.claim.params.stated_value = 7;
    sameCount.claim.params.stated_total = 12;
    sameCount.claim.params.unit = "count";
    expect(claimSlots(sameCount)).not.toHaveProperty("direction");
    const rounded = result({ verdict: "contradicted", correct_value: "62.0% (62 of 100)" });
    expect(claimSlots(rounded)).not.toHaveProperty("direction");
    for (const view of VIEWS) {
      const text = templateFor(view, [sameCount]).claims[sameCount.claim.id];
      expect(fillSlots(text, { ...auditSlots([sameCount]), ...claimSlots(sameCount) }), view).not.toMatch(/same as/);
    }
  });
  it("omits direction for a range or a stated total, but keeps it for a supported same-as", () => {
    const range = result({ fact: { ...result().fact!, value: 48 } });
    range.claim.params.stated_value = 60;
    range.claim.params.stated_high = 70;
    expect(claimSlots(range)).not.toHaveProperty("direction");
    const total = result({ type: "COUNT", fact: { ...result().fact!, value: 5 } });
    total.claim.params.stated_value = 7;
    total.claim.params.stated_total = 12;
    expect(claimSlots(total)).not.toHaveProperty("direction");
    expect(claimSlots(result()).direction).toBe("the same as");
  });
  it("agree and ways come from the variants, only when there are variants", () => {
    const [a, b] = mixed();
    expect(claimSlots(a)).not.toHaveProperty("agree");
    expect(claimSlots(a)).not.toHaveProperty("ways");
    expect(claimSlots(b)).toMatchObject({ agree: "2", ways: "3" });
  });
});

describe("templateFor", () => {
  const audit = mixed();
  for (const view of VIEWS) {
    it(`fills completely for the ${view} view`, () => {
      const t = templateFor(view, audit);
      expect(fillSlots(t.headline, auditSlots(audit))).not.toBeNull();
      expect(fillSlots(t.caption, auditSlots(audit))).not.toBeNull();
      for (const r of audit) {
        const text = t.claims[r.claim.id];
        expect(text, r.claim.id).toBeTruthy();
        expect(fillSlots(text, { ...auditSlots(audit), ...claimSlots(r) }), `${view}/${r.claim.id}: ${text}`).not.toBeNull();
      }
    });
    it(`has a clean headline for the ${view} view with no claims`, () => {
      const t = templateFor(view, []);
      for (const text of [t.headline, t.caption]) {
        expect(text).not.toMatch(/NaN|undefined|\{/);
        expect(text.length).toBeGreaterThan(0);
      }
      expect(t.claims).toEqual({});
    });
  }
  it("avoids every word and character the server's checker rejects in AI text", () => {
    // Keep in step with BANNED_WORDS in second_opinion/ai/narrate.py.
    const banned = new Set(
      `one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen
      seventeen eighteen nineteen twenty half dozen none all every most majority few several many higher lower
      more fewer less above below over under exceeds zero thirty forty fifty sixty seventy eighty ninety hundred
      thousand million percent twice double triple quarter third thirds both neither couple pair exceed exceeded
      exceeding greater larger smaller least highest lowest minority cent`.split(/\s+/),
    );
    for (const view of VIEWS) {
      const t = templateFor(view, audit);
      for (const text of [t.headline, t.caption, ...Object.values(t.claims), templateFor(view, []).headline]) {
        const bare = text.replace(/\{\w+\}/g, " ");
        expect(bare, text).not.toMatch(/[0-9%]|[^\x20-\x7e]/);
        for (const word of bare.toLowerCase().match(/[a-z]+/g) ?? []) expect(banned.has(word), `${view}: "${word}" in "${text}"`).toBe(false);
      }
    }
  });
  it("uses plain words only in the story view", () => {
    // Keep in step with STORY_JARGON in second_opinion/ai/narrate.py (whole words, plurals too).
    const jargon = /\b(?:fragile|robust|robustness|variants?|solidity|skeptic|verdict|p-value|PAM50)s?\b/i;
    const overridden = (["supported", "contradicted", "insufficient_evidence"] as Verdict[]).map((v) =>
      result({ verdict: v === "supported" ? "contradicted" : "supported", review: review(v) }),
    );
    for (const claims of [audit, overridden, []]) {
      const t = templateFor("story", claims);
      // Slot names are not words the reader sees ({fragile} becomes a number), as in the server's checker.
      for (const text of [t.headline, t.caption, ...Object.values(t.claims)]) expect(text.replace(/\{\w+\}/g, " ")).not.toMatch(jargon);
    }
  });
  it("uses one phrase family for a claim that could not be checked in the story view", () => {
    const [, , c] = audit;
    const t = templateFor("story", audit);
    expect(STORY_VERDICT_WORDS.insufficient_evidence).toBe("Couldn't be checked");
    expect(t.headline).toContain("Couldn't be checked: {insufficient}");
    expect(t.claims[c.claim.id]).toMatch(/^This claim couldn't be checked/);
    const changed = result({ review: review("insufficient_evidence") });
    expect(templateFor("story", [changed]).claims[changed.claim.id]).toContain(`"Couldn't be checked"`);
    const all = [t.headline, t.caption, ...Object.values(t.claims)].join(" ");
    expect(all).not.toMatch(/can't tell|could not be checked|not checkable/i);
  });
  it("reads correctly when every count is 1", () => {
    const one = result({
      verdict: "contradicted",
      correct_value: "48.0% (48 of 100)",
      solidity: "holds_under_some_variants",
      fact: { ...result().fact!, value: 48, numerator: 48 },
      variants: [{ variant_id: "v1", fact: null, verdict: "contradicted" }],
      review: review("contradicted"),
    });
    for (const view of VIEWS) {
      const out = renderNarration(view, [one], null);
      for (const text of [out.headline, out.caption, out.claims[one.claim.id].text]) {
        expect(text, `${view}: ${text}`).not.toMatch(/\b1 (?:of 1 )?(?:claims|ways|verdicts|were|are)\b/);
      }
    }
  });
  it("words the empty overview for an audit that ran and found no claims", () => {
    for (const view of VIEWS) {
      const t = templateFor(view, []);
      expect(`${t.headline} ${t.caption}`, view).not.toMatch(/run (?:the|an) audit|add a report|yet/i);
    }
    expect(templateFor("story", []).headline).toBe("The report had no claims to check.");
  });
  it("says so when a reviewer's verdict differs from the data, instead of claiming the data agrees", () => {
    const overridden = result({ verdict: "contradicted", correct_value: "7 of 12", review: review("supported") });
    for (const view of VIEWS) {
      const text = templateFor(view, [overridden]).claims[overridden.claim.id];
      expect(text, view).toMatch(/reviewer|overridden/);
      expect(text, view).not.toMatch(/agrees|backs this up/);
    }
  });
  it("picks the sentence by the final verdict when the reviewer accepted the tool's", () => {
    const accepted = result({ verdict: "contradicted", correct_value: "7 of 12", review: review("contradicted") });
    const plain = { ...accepted, review: null };
    expect(templateFor("story", [accepted]).claims[accepted.claim.id]).toBe(templateFor("story", [plain]).claims[accepted.claim.id]);
  });
});

describe("renderNarration", () => {
  const audit = mixed();
  const aiClaims = Object.fromEntries(audit.map((r) => [r.claim.id, "The data shows {data_shows}."]));

  it("keeps AI text where it fills and falls back to the template where it does not", () => {
    const out = renderNarration("story", audit, { headline: "{supported} held.", caption: "{reviewed} reviewed.", claims: aiClaims });
    const template = templateFor("story", audit);
    expect(out.claims.c.ai).toBe(false);
    expect(out.claims.c.text).toBe(template.claims.c);
    expect(out.claims.a).toEqual({ text: "The data shows 62.0% (62 of 100).", ai: true });
    expect(out.headline).toBe("2 held.");
    expect(out.ai).toBe(true);
  });
  it("rejects claim slots in the headline", () => {
    const out = renderNarration("story", audit, { headline: "Shows {data_shows}", caption: "ok {total}", claims: aiClaims });
    expect(out.headline).toBe(templateFor("story", audit).headline.replace(/\{(\w+)\}/g, (_, k) => auditSlots(audit)[k]));
    expect(out.caption).toBe("ok 4");
  });
  it("is all template with no AI text", () => {
    const out = renderNarration("checklist", audit, null);
    expect(out.ai).toBe(false);
    expect(Object.values(out.claims).every((c) => !c.ai)).toBe(true);
    expect(out.headline).not.toMatch(/\{/);
  });
  it("falls back for a claim the AI left out", () => {
    const out = renderNarration("raw", audit, { headline: "h", caption: "c", claims: { a: "ok" } });
    expect(out.claims.a).toEqual({ text: "ok", ai: true });
    expect(out.claims.b.ai).toBe(false);
  });
});

describe("narrationKey", () => {
  it("changes when an override changes the final verdict", () => {
    const base = [result({ id: "a" }), result({ id: "b" })];
    const changed = [base[0], { ...base[1], review: review("contradicted") }];
    expect(narrationKey("story", changed)).not.toBe(narrationKey("story", base));
  });
  it("is the same when an override keeps the verdict", () => {
    const base = [result({ id: "a" })];
    const kept = [{ ...base[0], review: review("supported") }];
    expect(narrationKey("story", kept)).toBe(narrationKey("story", base));
  });
  it("differs when the same ids and verdicts carry different claim text", () => {
    const a = [result({ id: "a" })];
    const b = [result({ id: "a" })];
    b[0].claim.text = "A different report sentence.";
    expect(narrationKey("story", b)).not.toBe(narrationKey("story", a));
    const c = [result({ id: "a" })];
    c[0].claim.text = a[0].claim.text;
    expect(narrationKey("story", c)).toBe(narrationKey("story", a));
  });
  it("differs by view", () => {
    const base = [result({ id: "a" })];
    expect(narrationKey("story", base)).not.toBe(narrationKey("raw", base));
  });
});
