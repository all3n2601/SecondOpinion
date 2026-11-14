// Slotted prose for the Review page. Text has named {blanks}; our code fills them from the audit, so a
// number on screen always comes from the data, never from the wording. The built-in templates below are
// the fallback and the baseline; the optional AI endpoint (POST /ai/narrate) writes the same slotted
// shape, already checked by second_opinion/ai/narrate.py. These templates obey the same rules as that
// checker (no digits, no number or comparison words, no percent sign outside a slot) so a reviewer
// hears one voice whichever wrote it. Pure functions: no React, no fetch.

import { describeStated } from "./ai-plan";
import { formatResultFact } from "./claim-format";
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
  if (result.verdict === "contradicted") dataShows = result.correct_value ?? formatResultFact(result);
  else if (result.verdict === "supported") dataShows = formatResultFact(result);
  if (dataShows) slots.data_shows = dataShows;

  const said = result.claim.params.stated_value;
  const found = result.fact?.value;
  if ((result.claim.type === "SHARE" || result.claim.type === "COUNT") && !result.parts?.length) {
    if (typeof said === "number" && typeof found === "number") {
      const [a, b] = [round1(found), round1(said)];
      slots.direction = a > b ? "higher than" : a < b ? "lower than" : "the same as";
    }
  }

  if (result.variants.length > 0) {
    slots.agree = formatCount(result.variants.filter((v) => v.verdict === result.verdict).length);
    slots.ways = formatCount(result.variants.length);
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

function claimSentence(view: RoleView, result: ClaimResult): string {
  const final = finalVerdict(result);
  const kind: Kind = final === result.verdict ? final : "overridden";
  const values = { ...auditSlots([result]), ...claimSlots(result) };
  const ways = "{agree} of {ways} ways of counting";

  switch (view) {
    case "story": {
      if (kind === "overridden") {
        return compose(
          values, " ",
          `A reviewer changed the verdict to ${FINAL_WORDS[final]}.`,
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
      return "This release does not have the data to check this claim.";
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
          `${ways} agree.`,
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
          `${ways} agree.`,
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
          `${ways} give the same verdict.`,
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
          `${ways} give the same verdict.`,
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
        "agree {agree}/{ways}",
      );
    }
  }
}

const HEADLINE: Record<RoleView, string> = {
  story:
    "{supported} of {total} claims held up against the data, {contradicted} did not, and {insufficient} could not be checked.",
  checklist: "{total} claims to review: {supported} supported, {contradicted} contradicted, {insufficient} with too little data.",
  evidence:
    "{supported} supported, {contradicted} contradicted and {insufficient} with insufficient evidence, out of {total} claims.",
  raw: "total {total} | supported {supported} | contradicted {contradicted} | insufficient {insufficient}",
};

const CAPTION: Record<RoleView, string> = {
  story: "{reviewed} reviewed by a person so far. {fragile} could change if counted another way.",
  checklist: "{reviewed} of {total} reviewed. Accept or override each claim, then finish.",
  evidence: "{fragile} verdicts hold in only some ways of counting; {reviewed} reviewed so far.",
  raw: "reviewed {reviewed} | fragile {fragile}",
};

const EMPTY: Record<RoleView, { headline: string; caption: string }> = {
  story: { headline: "There are no claims to look at yet.", caption: "Add a report and run the audit to see what held up." },
  checklist: { headline: "No claims to review.", caption: "Run an audit first." },
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

/** Changes whenever the view or any final verdict changes: the cue to ask the AI for new wording. */
export function narrationKey(view: RoleView, claims: ClaimResult[]): string {
  return `${view}|${claims.map((c) => `${c.claim.id}:${finalVerdict(c)}`).join(",")}`;
}
