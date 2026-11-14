# Review Claim Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every claim row on the Review page reads answer → one chart → folded detail → review form, with each fact once.

**Architecture:** Pure teaser functions join `lib/insights.ts`. `components/review/Insights.tsx` stops being a
dispatcher appended after the body and instead exports its pieces; a new `components/review/ClaimChart.tsx` picks
the single chart; `ClaimBody.tsx` composes answer, chart and folds per view. `ReviewForm` and the overviews are untouched.

**Tech Stack:** Next.js 16 / React 19 / Tailwind 4 in `apps/web`, vitest 3.

**Spec:** `docs/superpowers/specs/2026-11-14-review-claim-layout-design.md`

## Global Constraints

- Order in every view: answer → one chart → folds → review form (form unchanged, stays last).
- One chart per claim, or per part of a multi-part sentence. No 0–100 gauge when the dot strip is shown.
- Checklist loses the "Key number" and "Solidity" rows; outside story, solidity shows as a chip beside the badge.
- Folds are native `<details>`; each summary carries a teaser computed from the insight functions. No new numbers.
- Story view: no folds; the plain "What else we found" box stays.
- Colours only from tokens (`apps/web/DESIGN.md`); every chart keeps a text equivalent.
- Branch `feat/review-insights`. Stage only the files a task names: other sessions have uncommitted files here.

## Review Focus

1. A claim with fewer than two ways of counting (practice C1, a count) gets the existing gauge, and its "rests on" fold says 535 of 1,101 with nothing missing.
2. An insufficient-evidence claim (C3) shows only "what the data would need": no folds, no empty fold.
3. A multi-part sentence where no part has a strip shows one line per part and nothing else in the chart tier.
4. A claim checked through the AI helper's plan (no variants) still gets `ClaimVsData`'s plan-aware figure.
5. A fold with nothing inside is not rendered (e.g. no code and no sample IDs).

---

### Task 1: Fold teasers

**Files:**
- Modify: `apps/web/src/lib/insights.ts`
- Test: `apps/web/src/lib/insights.test.ts`

**Interfaces:**
- Produces: `restsTeaser(r: RestsOn): string`, `causeTeaser(d: Diagnosis): string`, `robustnessTeaser(result: ClaimResult): string | null`

- [ ] **Step 1: Write the failing tests** (reuse the file's `result`, `fact`, `C2_VARIANTS` fixtures)

```ts
describe("teasers", () => {
  it("says how many have a value, and none missing when none are", () => {
    expect(restsTeaser(restsOn(result())!)).toBe("844 of 1,101 have a value");
    expect(restsTeaser(restsOn(result({ type: "COUNT", params: { unit: null }, fact: fact(535, 1101) }))!)).toBe("535 of 1,101 counted, none missing");
  });
  it("says whether any reading gives the stated figure", () => {
    expect(causeTeaser(diagnose(result({ variants: C2_VARIANTS }))!)).toBe("1 reading gives about 62%");
    expect(causeTeaser(diagnose(result({ params: { stated_value: 90 }, variants: C2_VARIANTS }))!)).toBe("No reading we tried gives about 90%");
  });
  it("counts agreeing ways, or is null with none", () => {
    expect(robustnessTeaser(result({ variants: C2_VARIANTS }))).toBe("5 of 5 ways agree");
    expect(robustnessTeaser(result())).toBeNull();
  });
});
```

(Several matching readings: "2 readings give about 62%".)

- [ ] **Step 2:** `cd apps/web && npx vitest run src/lib/insights.test.ts` — FAIL, functions not exported.
- [ ] **Step 3:** Implement the three functions in `lib/insights.ts` (`formatCount` for numbers, `statedWords` for the figure; robustness counts variants whose verdict equals `result.verdict`, and appends `; skeptic tests apply` only when `result.skeptic` is set).
- [ ] **Step 4:** Same command — PASS.
- [ ] **Step 5:** Commit `apps/web/src/lib/insights.ts apps/web/src/lib/insights.test.ts`: `feat(web): fold teasers for claim readings`.

### Task 2: One chart and three tiers per view

**Files:**
- Create: `apps/web/src/components/review/ClaimChart.tsx`
- Modify: `apps/web/src/components/review/Insights.tsx`, `apps/web/src/components/review/ClaimBody.tsx`

**Interfaces:**
- Consumes: Task 1 teasers; `countingRange`, `restsOn`, `diagnose`, `statedFigure` from `lib/insights.ts`; `ClaimVsData` default export.
- Produces:
  - `Insights.tsx` named exports (default export removed): `CountingStrip({ range, stated, verdict, plain? })`, `RestsOnBar({ rests })`, `CauseNote({ diagnosis })`, `TriedList({ diagnosis, mono? })`, `StoryFindings({ result })`, `RawNumbers({ result })`.
  - `ClaimChart({ result, plain }: { result: ClaimResult; plain: boolean })`: strip when `countingRange(result)` is non-null, else `<ClaimVsData result={result} />`; for `result.parts?.length > 1`, one line per part (part words in `<q>`, verdict label, data shown) followed by that part's strip when it has one.
  - `Fold({ title, teaser, open, children })` in `ClaimBody.tsx`: a `<details>` whose `<summary>` shows the title and, after it, the teaser in `text-ink-soft`.

- [ ] **Step 1:** In `CountingStrip`, label the standard way's value directly under its ringed dot ("Data 49.9%", placed like `ClaimVsData`'s `place()` so it stays inside the track); shorten the non-plain caption to the range sentence plus "Ringed dot: the standard way."
- [ ] **Step 2:** Move per-part handling out of the old default export into `ClaimChart`; `StoryFindings` and `RawNumbers` take a `result` and walk parts themselves (one paragraph / one block per part that has readings, each headed by the part's words).
- [ ] **Step 3:** Rewrite `ClaimBody.tsx` bodies to the spec's table:
  - story: plain verdict line, quoted claim, narrated sentence, `ClaimChart plain`, `StoryFindings`.
  - checklist: `VerdictBadge` + `SolidityExplained` side by side, claim, sentence, `ClaimChart`, folds closed: *What the number rests on*, *Where {stated} might come from* (contradicted only), *Robustness and skeptic tests*.
  - evidence: badge + chip, claim, sentence, `ClaimChart`, folds open: rests on, where from (with `TriedList`), robustness (`RobustnessLine full`, `SkepticLine`, corrected wording when the ladder changed anything); *Code and sample IDs* closed.
  - raw: current mono facts (verdict, count, summary), then open folds: *Numbers* (`RawNumbers`), *Sample IDs*, *Code*.
  - A fold whose content is empty is not rendered. For a multi-part sentence the rests-on and where-from folds use the first part that has them, and their titles name that part's words.
- [ ] **Step 4:** `cd apps/web && npx tsc --noEmit -p . && npm run lint && npx vitest run` — all clean.
- [ ] **Step 5:** Commit the three component files: `feat(web): answer, one chart, folds on each review row`.

### Task 3: Check it in the app, then docs

**Files:**
- Modify: `README.md` (the readings paragraph under **Role views**)

- [ ] **Step 1:** Run the practice audit at http://localhost:3000/start, open `/review`, and for each of the four roles record the page height and the y of each review form (`document.body.scrollHeight`, `form.getBoundingClientRect().top + scrollY`). Expected: C2's row in the checklist view about half of its previous ~1,200px; no "49.9% (421 of 844)" more than twice in a row; C1 shows the gauge; C3 shows no folds.
- [ ] **Step 2:** Screenshot C2 in all four views into `.playwright-mcp/layout-<view>.png` and look at each.
- [ ] **Step 3:** README: say each row reads answer, one chart, folded detail, then the review form, and which folds each view opens.
- [ ] **Step 4:** Commit `README.md` and the spec/plan docs: `docs: review row layout`.
