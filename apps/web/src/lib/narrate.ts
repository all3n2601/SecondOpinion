// Slotted prose for the Review page. Text has named {blanks}; our code fills them from the audit, so a
// number on screen always comes from the data, never from the wording. The built-in templates below are
// the fallback and the baseline; the optional AI endpoint (POST /ai/narrate) writes the same slotted
// shape, already checked by second_opinion/ai/narrate.py. These templates obey the same rules as that
// checker (no digits, no number or comparison words, no percent sign outside a slot; no jargon in the story
// view) so a reviewer hears one voice whichever wrote it. A slot can hold 1, so no template puts a plural noun
// after a count slot ("Claims to review: {total}", never "{total} claims"). Pure functions: no React, no fetch.

import { describeStated } from "./ai-plan";
import { agreement, agreementFraction, formatResultFact } from "./claim-format";
import { finalVerdict, formatCount } from "./review";
import type { ClaimParams, ClaimResult, RoleView, Verdict } from "./types";

export type Slotted = { headline: string; caption: string; claims: Record<string, string> };

export type Rendered = { text: string; ai: boolean };

export type Narration = {
  headline: string;
  caption: string;
  claims: Record<string, Rendered>;
  /** True when at least one piece of text came from the AI. */
  ai: boolean;
};

const SLOT = /\{(\w+)\}/g;

/** Fill each `{name}` from `values`; null if any name has no value. */
export function fillSlots(text: string, values: Record<string, string>): string | null {
  let missing = false;
  const out = text.replace(SLOT, (_, name: string) => {
    if (!Object.prototype.hasOwnProperty.call(values, name)) {
      missing = true;
      return "";
    }
    return values[name];
  });
  return missing ? null : out;
}

/** Audit-wide counts, by final verdict (after any override). */
export function auditSlots(claims: ClaimResult[]): Record<string, string> {
  const count = (v: Verdict) => claims.filter((c) => finalVerdict(c) === v).length;
  return {
    supported: formatCount(count("supported")),
    contradicted: formatCount(count("contradicted")),
    insufficient: formatCount(count("insufficient_evidence")),
    total: formatCount(claims.length),
    reviewed: formatCount(claims.filter((c) => c.review !== null).length),
    fragile: formatCount(claims.filter((c) => c.solidity === "holds_under_some_variants").length),
  };
}

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

function isPercent(type: string, params: ClaimParams): boolean {
  // Same reading as ladder.py: a share with no unit is a percentage.
  return params.unit === "percent" || (params.unit === null && type === "SHARE");
}

/** What the report states, in a few words: "about 62%", "7 of 12", "30 to 40%". Null when there is no figure. */
function statedWords(result: ClaimResult): string | null {
  if (result.parts?.length) return null;
  const aiStated = result.ai_plan?.stated;
  if (aiStated) {
    const words = describeStated(aiStated);
    if (words) return words;
  }
  const { claim } = result;
  const p = claim.params;
  if (p.unit === "all") return "every one";
  if (p.stated_value === null) return null;
  const pct = isPercent(claim.type, p) ? "%" : "";
  if (p.stated_high !== null) return `${number.format(p.stated_value)} to ${number.format(p.stated_high)}${pct}`;
  const value = `${p.approximate ? "about " : ""}${number.format(p.stated_value)}${pct}`;
  return p.stated_total !== null ? `${value} of ${number.format(p.stated_total)}` : value;
}

const round1 = (n: number) => Math.round(n * 10) / 10;

/** Values for the blanks that belong to one claim. A key is present only when there is a value for it. */
export function claimSlots(result: ClaimResult): Record<string, string> {
  const slots: Record<string, string> = {};
  const stated = statedWords(result);
  if (stated) slots.stated = stated;

  // The data is what the tool computed, whatever a reviewer later decided about it.
  let dataShows = "";
  const multiPart = (result.parts?.length ?? 0) > 1;
  if (result.verdict === "contradicted") dataShows = result.correct_value ?? formatResultFact(result);
  // One figure cannot stand for a sentence with several parts; each part's figure is listed under it.
  else if (result.verdict === "supported" && !multiPart) dataShows = formatResultFact(result);
  if (dataShows) slots.data_shows = dataShows;

  // A single-value comparison misleads for a range or a figure out of a stated total, and "the same as" next to
  // a contradicted verdict (the gap is in the total or the rounding) reads as a contradiction of itself.
  const p = result.claim.params;
  const single = p.stated_high === null && p.stated_total === null && !result.ai_plan?.stated?.high && !result.ai_plan?.stated?.total;
  if ((result.claim.type === "SHARE" || result.claim.type === "COUNT") && !result.parts?.length && single) {
    const said = p.stated_value;
    const found = result.fact?.value;
    if (typeof said === "number" && typeof found === "number") {
      const [a, b] = [round1(found), round1(said)];
      const direction = a > b ? "higher than" : a < b ? "lower than" : "the same as";
      if (!(direction === "the same as" && result.verdict === "contradicted")) slots.direction = direction;
    }
  }

  const whole = agreement(result);
  if (whole?.kind === "ways") {
    slots.agree = formatCount(whole.agree);
    slots.ways = formatCount(whole.ways);
  } else if (whole?.kind === "parts") {
    slots.parts_hold = agreementFraction(whole);  // "3 of 4": parts that hold under every way of counting
  }
  return slots;
}

// ---- Built-in templates ----

/** First alternative whose blanks all have values; "" when none does. */
function firstFilled(values: Record<string, string>, ...alternatives: string[]): string {
  for (const text of alternatives) if (fillSlots(text, values) !== null) return text;
  return "";
}

/** Join the pieces that can be filled, in order, with `sep`. A piece is a string or a list of alternatives. */
function compose(values: Record<string, string>, sep: string, ...pieces: (string | string[])[]): string {
  return pieces
    .map((p) => firstFilled(values, ...(Array.isArray(p) ? p : [p])))
    .filter(Boolean)
    .join(sep);
}

const FINAL_WORDS: Record<Verdict, string> = {
  supported: "supported",
  contradicted: "contradicted",
  insufficient_evidence: "not checkable with this data",
};

type Kind = Verdict | "overridden";

/** Story-view words for a final verdict. The same family as STORY_WORDS in components/review/ClaimBody.tsx. */
export const STORY_VERDICT_WORDS: Record<Verdict, string> = {
  supported: "Held up",
  contradicted: "Wrong",
  insufficient_evidence: "Couldn't be checked",
};

function claimSentence(view: RoleView, result: ClaimResult): string {
  const final = finalVerdict(result);
  const kind: Kind = final === result.verdict ? final : "overridden";
  const values = { ...auditSlots([result]), ...claimSlots(result) };

  switch (view) {
    case "story": {
      if (kind === "overridden") {
        return compose(
          values, " ",
          `A reviewer changed this to "${STORY_VERDICT_WORDS[final]}".`,
          ["The report says {stated}, and the data shows {data_shows}.", "The data shows {data_shows}."],
        );
      }
      if (kind === "supported") {
        return compose(
          values, " ",
          [
            "The report says {stated} and the data agrees: {data_shows}.",
            "The data backs this up: {data_shows}.",
            "The data backs this up.",
          ],
        );
      }
      if (kind === "contradicted") {
        return compose(
          values, " ",
          [
            "The report says {stated}, but the data shows {data_shows}, which is {direction} the report.",
            "The report says {stated}, but the data shows {data_shows}.",
            "The data shows {data_shows}, not what the report says.",
            "The data does not back this up.",
          ],
        );
      }
      return "This claim couldn't be checked: the release does not have the data it needs.";
    }

    case "checklist": {
      if (kind === "overridden") {
        return compose(
          values, " ",
          `Verdict changed by a reviewer to ${FINAL_WORDS[final]}.`,
          ["Report says {stated}; data shows {data_shows}.", "Data shows {data_shows}."],
        );
      }
      if (kind === "supported") {
        return compose(
          values, " ",
          [
            "Supported: report says {stated}; data shows {data_shows}.",
            "Supported: data shows {data_shows}.",
            "Supported.",
          ],
          ["Ways of counting that agree: {agree} of {ways}.", "Parts that hold under every way of counting: {parts_hold}."],
          "Check it, then accept.",
        );
      }
      if (kind === "contradicted") {
        return compose(
          values, " ",
          [
            "Contradicted: report says {stated}; data shows {data_shows} ({direction} the report).",
            "Contradicted: report says {stated}; data shows {data_shows}.",
            "Contradicted: data shows {data_shows}.",
            "Contradicted.",
          ],
          ["Ways of counting that agree: {agree} of {ways}.", "Parts that hold under every way of counting: {parts_hold}."],
          "Accept, or override with a reason.",
        );
      }
      return "Not enough data to check this. Accept, or override with a reason.";
    }

    case "evidence": {
      if (kind === "overridden") {
        return compose(
          values, " ",
          `A reviewer set the verdict to ${FINAL_WORDS[final]}, differing from the tool's.`,
          [
            "The report states {stated}; the recomputed figure is {data_shows}.",
            "The recomputed figure is {data_shows}.",
          ],
        );
      }
      if (kind === "supported") {
        return compose(
          values, " ",
          [
            "The report states {stated}; the recomputed figure is {data_shows}.",
            "The recomputed figure is {data_shows}.",
            "The recomputed figure supports the claim.",
          ],
          [
            "Ways of counting that give the same verdict: {agree} of {ways}.",
            "Parts that keep their verdict under every way of counting: {parts_hold}.",
          ],
        );
      }
      if (kind === "contradicted") {
        return compose(
          values, " ",
          [
            "The report states {stated}; the recomputed figure is {data_shows}, {direction} the report.",
            "The report states {stated}; the recomputed figure is {data_shows}.",
            "The recomputed figure is {data_shows}.",
            "The recomputed figure contradicts the claim.",
          ],
          [
            "Ways of counting that give the same verdict: {agree} of {ways}.",
            "Parts that keep their verdict under every way of counting: {parts_hold}.",
          ],
        );
      }
      return "The release lacks the data this claim needs, so no verdict on the figure is possible.";
    }

    case "raw": {
      const head = kind === "overridden" ? `overridden to ${FINAL_WORDS[final]}` : kind === "insufficient_evidence" ? "insufficient" : kind;
      return compose(
        values, " | ",
        head,
        "stated {stated}",
        "data {data_shows}",
        "{direction}",
        ["agree {agree}/{ways}", "parts robust {parts_hold}"],
      );
    }
  }
}

const HEADLINE: Record<RoleView, string> = {
  story: "Claims checked against the data: {total}. Held up: {supported}. Wrong: {contradicted}. Couldn't be checked: {insufficient}.",
  checklist: "Claims to review: {total} (supported {supported}, contradicted {contradicted}, too little data {insufficient}).",
  evidence: "Claims audited: {total}. Supported: {supported}; contradicted: {contradicted}; insufficient evidence: {insufficient}.",
  raw: "total {total} | supported {supported} | contradicted {contradicted} | insufficient {insufficient}",
};

const CAPTION: Record<RoleView, string> = {
  story: "Reviewed by a person so far: {reviewed}. Could change if counted another way: {fragile}.",
  checklist: "Reviewed so far: {reviewed} of {total}. Accept or override each claim, then finish.",
  evidence: "Verdicts that hold in only some ways of counting: {fragile}. Reviewed so far: {reviewed}.",
  raw: "reviewed {reviewed} | fragile {fragile}",
};

// An audit that ran and found nothing to check in the report (the page shows no overview without an audit).
const EMPTY: Record<RoleView, { headline: string; caption: string }> = {
  story: { headline: "The report had no claims to check.", caption: "There is nothing here to review." },
  checklist: { headline: "No claims to review.", caption: "The audit found no claims in the report." },
  evidence: { headline: "The audit has no claims.", caption: "Nothing to recompute." },
  raw: { headline: "no claims", caption: "audit empty" },
};

/** The built-in wording for a view. Every piece fills completely from `auditSlots` and the claim's own `claimSlots`. */
export function templateFor(view: RoleView, claims: ClaimResult[]): Slotted {
  const claimTexts = Object.fromEntries(claims.map((r) => [r.claim.id, claimSentence(view, r)]));
  if (claims.length === 0) return { ...EMPTY[view], claims: claimTexts };
  return { headline: HEADLINE[view], caption: CAPTION[view], claims: claimTexts };
}

/** AI text where it fills from the audit, else the template's text for that piece. */
export function renderNarration(view: RoleView, claims: ClaimResult[], ai: Slotted | null): Narration {
  const template = templateFor(view, claims);
  const audit = auditSlots(claims);

  const piece = (aiText: string | undefined, fallback: string, values: Record<string, string>): Rendered => {
    const filled = aiText === undefined ? null : fillSlots(aiText, values);
    if (filled !== null && filled.trim() !== "") return { text: filled, ai: true };
    return { text: fillSlots(fallback, values) ?? fallback, ai: false };
  };

  const headline = piece(ai?.headline, template.headline, audit);
  const caption = piece(ai?.caption, template.caption, audit);
  const out: Record<string, Rendered> = {};
  for (const r of claims) {
    const id = r.claim.id;
    out[id] = piece(ai?.claims[id], template.claims[id], { ...audit, ...claimSlots(r) });
  }
  return {
    headline: headline.text,
    caption: caption.text,
    claims: out,
    ai: headline.ai || caption.ai || Object.values(out).some((c) => c.ai),
  };
}

/** FNV-1a (32-bit) of a string, in hex. Deterministic and dependency-free; a cache key, not a security measure. */
function hash(text: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

/** Changes whenever the view, any final verdict or any claim text changes: the cue to ask the AI for new wording. */
export function narrationKey(view: RoleView, claims: ClaimResult[]): string {
  const texts = hash(claims.map((c) => c.claim.text).join("\u0001"));
  return `${view}|${texts}|${claims.map((c) => `${c.claim.id}:${finalVerdict(c)}`).join(",")}`;
}
