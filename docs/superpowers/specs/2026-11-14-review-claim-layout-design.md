# Review page: one clear layout per claim

Date: 2026-11-14 · Status: approved in conversation ("Can we do it"), short design

## Intent

Each claim row on the Review page grew by accretion: the per-view body, then the 0–100 "report versus data" gauge,
then the new readings (every way of counting, what the number rests on, where the figure might come from) appended
at the end. On the practice audit the Data-use reviewer page is about 3,600px for 3 claims; C2 alone is about
1,200px before its Accept / Override form, says "49.9% (421 of 844)" up to four times, and draws two charts of the
same comparison. The owner wants the page to convey everything more clearly: answer first, then why, then decide.

## Goals

- Every claim row, in every view, follows the same order: **answer → one chart → folded detail → review form**.
- Each fact appears once per row. One chart per claim (or per part of a multi-part sentence).
- The role decides depth: which folds exist and which start open.
- Rows get much shorter by default (target: C2 in the checklist view about half its current height).

## Non-goals

- The overview panels, the review form's own behaviour, the gate, the AI narration and its cache are unchanged.
- No one-claim-at-a-time review flow (considered; it changes how the step works, not just how it looks).
- No new data, no Python change.

## Approaches

- **Three tiers in the existing list (chosen).** Same page and flow, each row restructured. Fixes repetition and
  length without changing how people move through the review.
- **One claim at a time** (list on the left, focused claim on the right, Next / Previous). Solves length outright but
  changes the Review step; can sit on top of this later.
- **Only collapse the new readings.** Cheapest, but leaves the duplicates and the two charts.

## Design

Row, top to bottom (the form's header with claim id and review status stays as it is):

1. **Answer.** Verdict badge (story: plain verdict words) with, outside the story view, a small solidity chip;
   the claim text; the narrated sentence (AI or template). The checklist "Key number" row and the "Solidity" row go:
   the sentence and the chip carry them.
2. **One chart.**
   - A share or count with at least two ways of counting: the dot strip (it already marks the report's figure and its
     "about" band). The strip labels the standard way's value directly under its dot, so the 0–100 gauge is no longer
     needed for that claim.
   - Otherwise the existing `ClaimVsData` figure (gauge, plain pair, or "what the data would need").
   - A multi-part sentence: one line per part (its words and verdict), each followed by that part's chart when it
     has one. This replaces both "Each part of the sentence" and the separate "About …" blocks.
   - Raw view: no chart; the per-way values table stands in for it inside the folds.
3. **Folds** (`<details>`, each summary carries a one-line teaser so a closed fold still informs):
   - *What the number rests on* — stacked bar and missing-data bounds. Teaser: "844 of 1,101 have a value".
   - *Where {stated} might come from* (contradicted only) — the clue sentence and every reading tried.
     Teaser: "1 reading gives it" / "No reading we tried gives it".
   - *Robustness and skeptic tests* — robustness line, skeptic line, corrected wording.
   - *Code and sample IDs* — the code and the sample IDs.
4. **Review form** (unchanged).

Per view:

| View | Answer | Chart | Folds (open by default in bold) |
|---|---|---|---|
| story | plain verdict words, claim, sentence | strip with a one-line plain caption | none; one "What else we found" box in plain sentences instead |
| checklist | badge + solidity chip, claim, sentence | strip or gauge | rests on, where from, robustness |
| evidence | badge + solidity chip, claim, sentence | strip or gauge | **rests on**, **where from**, **robustness**, code |
| raw | one-line verdict, claim, summary (mono) | none | **numbers** (rests on, ways table, readings), **sample IDs**, **code** |

## Builder calls

- The review form stays after the folds, not beside the verdict: deciding before reading the evidence is the wrong
  flow, and closed folds are one line each, so the form sits close to the answer.
- Fold teasers are computed from the same insight functions; no new numbers.
- Accessibility: each chart keeps a text equivalent; folds are native `<details>`.
