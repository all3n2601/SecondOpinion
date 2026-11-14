# Split, Check, Join Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** No verdict on a sentence the reader only half used: a coverage gate on every reading, an AI split for
sentences that fail it, and a join where the worst complete part decides.

**Architecture:** A new pure module `second_opinion/coverage.py` says what a sentence demands and what a reading used.
`/extract` gates every rules claim: AI off, a gated claim becomes `UNMAPPED` with `coverage_gaps`; AI on, a new
`second_opinion/ai/split.py` splits it into self-contained statements that the rules read first and an AI plan reads
otherwise. `/audit` gates AI plans the same way and `_combine_parts` gates the join.

**Tech Stack:** Python 3 (`second_opinion`), FastAPI (`apps/api`, dataclass models), pytest; Next.js types in `apps/web`.

**Spec:** `docs/superpowers/specs/2026-11-14-claim-split-and-join-design.md`

## Global Constraints

- Never a verdict on an incomplete reading: a rules claim, an AI plan or a split part that leaves a demanded figure,
  group, counted thing, back reference or unknown qualifier unused gives "can't check" (insufficient evidence).
- A complete, contradicted part keeps its sentence contradicted.
- The AI sees report text only (the sentence and the one before it), never data values; every figure in a split
  statement is quoted from its span.
- `NOT_ANSWERABLE` claims skip the gate and the split.
- One new optional field, `Claim.coverage_gaps: list[str]` (default `[]`); `audit.json` unchanged.
- Dev sets: blindset6, 8, 10, 12, 15 (copied into `tests/blind/dev/`). Held-out: blindset7, 9, 11, 13, blindtest3,
  blindtest5, scored once in Task 7 from the zip, never copied into the repo before then.
- Targets on dev, rules only and AI on: true-called-contradicted at most 1 in 30 claims; wrong-called-supported not up.
- Every AI step degrades to a safe answer (`UNMAPPED` with the gate's reason) on any failure.
- Stage only files a task names.

## Review Focus

1. A sentence the rules read completely today ("535 of 1,101 (48.6%)", "1,247 samples from 1,101 patients", the
   practice report's C1–C3) passes the gate unchanged: the practice audit still gives supported / contradicted /
   insufficient.
2. Name-like numbers (TP53, PAM50, Stage IIA, GISTIC "2" in a definition, years used as dates) never count as
   unused figures.
3. An AI split that invents a number, or whose spans miss a figure, is rejected after one retry, and the sentence
   becomes "can't check", not a verdict.
4. With the AI client raising on every call, `/extract` and `/audit` still answer, and gated sentences say "can't check".
5. A split part's own statement passes the gate before its verdict counts; a back-referenced group resolved from the
   previous sentence is in the statement, so `/audit` needs nothing else.

---

### Task 1: Blind scorer in the repo, dev sets, baseline

**Files:**
- Create: `tests/blind/score.py`, `tests/blind/dev/<blindset6|8|10|12|15>/` (reports, `key.json`, `nonclaims.json`
  copied from the zip at `/private/tmp/claude-501/-Users-all3n2601-Desktop-Hackathons-SecondOpinion/3988c9e4-7933-48b7-8bd6-cb7858b3ec72/scratchpad/blind-zip/`),
  `tests/blind/BASELINE.md`, `tests/test_blind_score.py`

**Interfaces:**
- Produces: `python tests/blind/score.py <sets-dir> [--ai] [--json OUT]` printing per set and totals: correct,
  true-called-contradicted, wrong-called-supported, can't-check, not picked up, non-claims flagged. Library functions
  `norm(text) -> str` and `match(entries, findings) -> list[dict]` (key entry + `outcome` + `ours`).
- Base it on the scratch scorer `.../scratchpad/blind-score/score_json_sets.py` (same matching: `claim_contains`
  substring of normalised claim text or original text; first match wins).

- [ ] **Step 1: Failing test** `tests/test_blind_score.py`: `norm("“Luminal A” – **62%**")  == '"luminal a" - 62%'`;
  `match` on two key entries and three findings gives `correct`, `wrong` and `missed` outcomes.
- [ ] **Step 2:** `.venv/bin/python -m pytest tests/test_blind_score.py -q` — FAIL (module missing).
- [ ] **Step 3:** Implement `tests/blind/score.py`; copy the five dev sets.
- [ ] **Step 4:** test PASS; then run `SO_RELEASE_DIR=<release A raw> .venv/bin/python tests/blind/score.py tests/blind/dev`
  and with `--ai`; write both result tables into `tests/blind/BASELINE.md` with the date and commit.
- [ ] **Step 5:** Commit: `test: blind scorer and dev sets with baseline`.

### Task 2: Coverage module

**Files:**
- Create: `second_opinion/coverage.py`, `tests/test_coverage.py`

**Interfaces:**
- Produces:
  - `@dataclass Demands: figures: list[Piece]; groups: list[Piece]; counted: list[Piece]; back_reference: Piece | None; qualifiers: list[Piece]`
    where `@dataclass Piece: start: int; end: int; words: str; value: float | None = None; key: str | None = None`
    (`key` = `"attribute:category"` for groups, the noun lemma for counted things).
  - `sentence_demands(text: str) -> Demands`
  - `@dataclass Uses: figures: set[float]; groups: set[str]; counted: set[str]; spans: list[tuple[int, int]]; resolves_back_reference: bool = False`
  - `reading_uses(claim: Claim, plan: QueryPlan | None = None) -> Uses` — from `ClaimParams` of the claim and its
    parts (stated_value/high/total, thresholds, subtype, attribute/category/category_b, within_*, group_a/b,
    subtype_source, subject) or from an AI plan (filters, stated figure and span).
  - `missing(text: str, uses: Uses) -> list[str]` — the sentence's unused words, in sentence order; `[]` = complete.
    A figure is used when its value equals a used figure (to the precision written) or it lies inside a used span.
    A back reference is never used by a rules reading.

- [ ] **Step 1: Failing tests** `tests/test_coverage.py`, rules readings from `extract_claims(sentence).claims[0]`:
  ```python
  INCOMPLETE = [  # (sentence, a word that must be reported missing)
      ("TP53 mutations dominate basal-like tumors, at 85% compared with 10% in Luminal A.", "basal-like"),
      ("Deaths rise with nodal involvement: 44 of 516 N0 patients died, against 15 of 77 N3 patients.", "N0"),
      ("Frozen sections outnumber diagnostic slides, 1,978 to 1,133.", "slides"),
      ("Their ages ranged from 44 to 84 years.", "Their"),
      ("CBFB was mutated in 18 tumors, the same number as SF3B1.", "SF3B1"),
      ("In all, 432 tumors carry a high-level amplification of at least one of ERBB2, MYC or CCND1, about a third of the cohort.", "a third"),
      ("Of the 1,101 primary tumors, 844 received a PAM50 call from RNA sequencing.", "PAM50 call"),
  ]
  COMPLETE = [
      "Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data.",
      "The release contains 1,247 samples from 1,101 patients.",
      "About 77% of tumors with a known ER status are ER-positive (808 of 1,046).",
      "PIK3CA is the most frequently mutated gene, altered in 273 of 791 tumors.",
      "Gene-level GISTIC2 calls were used, with a value of 2 treated as high-level amplification.",  # no figure demanded
  ]
  ```
  `missing(s, reading_uses(c))` contains the word for every INCOMPLETE row and is `[]` for every COMPLETE row; plus
  unit tests of `sentence_demands` for name-like numbers (TP53, PAM50, Stage IIA, "in 2010") demanding no figure.
- [ ] **Step 2:** `.venv/bin/python -m pytest tests/test_coverage.py -q` — FAIL.
- [ ] **Step 3:** Implement on `find_numbers`, `find_amounts`, `word_numbers`/`fraction_amounts`, `find_entities`
  (all in `extract.py` / `numwords.py`); counted nouns and qualifier patterns as module constants.
- [ ] **Step 4:** PASS; full suite `SO_RELEASE_DIR=… .venv/bin/python -m pytest -q` still green (module unused yet).
- [ ] **Step 5:** Commit: `feat: coverage of a sentence by a reading`.

### Task 3: Gate the rules at extraction (AI off path)

**Files:**
- Modify: `second_opinion/model.py` (`Claim.coverage_gaps: list[str] = field(default_factory=list)`),
  `second_opinion/extract.py` (`extract_claims`, `classify_sentence` callers), `apps/web/src/lib/types.ts`
  (`coverage_gaps?: string[]` on `Claim`), tests touched by the change
- Test: `tests/test_extract_gate.py`

**Interfaces:**
- Consumes: Task 2 `sentence_demands`, `reading_uses`, `missing`.
- Produces: `gate(claim: Claim) -> Claim` in `extract.py` — returns the claim unchanged when complete or
  `NOT_ANSWERABLE`; otherwise a `ClaimType.UNMAPPED` claim with the same id, text, sentence index and original text,
  `coverage_gaps = missing(...)`, `needed_data = GATED.format(words=...)` where
  `GATED = "this sentence also states {words}, which the rules could not check; a person should check it"`.
  `extract_claims` and `/classify` apply it.

- [ ] **Step 1: Failing tests** `tests/test_extract_gate.py`: each INCOMPLETE sentence from Task 2 extracts as
  `UNMAPPED` with its word in `coverage_gaps`; each COMPLETE one keeps its rules type; auditing an INCOMPLETE one with
  `ai_client=None` (and `SO_AI=off`) gives `insufficient_evidence` whose `missing_evidence` names the word; the
  practice report (`apps/web/public/practice_brief.md`) still audits to supported / contradicted / insufficient.
- [ ] **Step 2:** run it — FAIL.
- [ ] **Step 3:** Implement `gate`; add the field and the web type.
- [ ] **Step 4:** PASS. Run the full suite; for every existing test that now fails, decide: the old verdict came from an
  incomplete reading (update the expectation to insufficient and list it in the commit message), or the gate is too
  strict (fix `coverage.py`, add the sentence to `COMPLETE`). Then `tests/blind/score.py tests/blind/dev` (rules only):
  record the new table under "After Task 3" in `BASELINE.md`, and list each claim that went from correct to can't-check.
- [ ] **Step 5:** Commit: `feat: rules readings that skip part of a sentence give can't check`.

### Task 4: Gate AI plans at audit

**Files:**
- Modify: `second_opinion/audit.py` (`_ai_checked`; remove `_unchecked_numbers`)
- Test: `tests/test_audit_ai_gate.py`

**Interfaces:**
- Consumes: Task 2 (`reading_uses(claim, plan=qp)`), Task 3 (`GATED`-style reason).
- Produces: in `_ai_checked`, after `run_plan`, `gaps = missing(claim.text, reading_uses(claim, plan=qp))`; non-empty
  gaps give `insufficient` naming them, whatever the plan's verdict (the existing `AI_PARTLY_CHECKED` message reused
  with the words), `ai_plan` kept on the result.

- [ ] **Step 1: Failing tests** with the repo's scripted AI client (as `tests/test_ai_executor.py` uses): a plan for
  "CBFB was mutated in 18 tumors, the same number as SF3B1." that only counts CBFB gives insufficient naming SF3B1
  (today: supported); a plan for "432 tumors … about a third of the cohort" that checks 432 only gives insufficient;
  a plan covering everything in "PIK3CA is mutated in 273 of 791 tumors." keeps its verdict.
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS + full suite.
- [ ] **Step 5:** Commit: `feat: AI plans that skip part of a sentence give can't check`.

### Task 5: The AI split at extraction

**Files:**
- Create: `second_opinion/ai/split.py`, `tests/test_ai_split.py`
- Modify: `apps/api/app/routes/extract.py` (`_with_ai_claims`), `second_opinion/ai/extract_ai.py` if recovered
  claims route through the split

**Interfaces:**
- Consumes: Tasks 2–3; the planner's quote guard (`ai/planner.py` `_check` / executor `_derivable`, whichever reads
  quoted figures with `numwords`).
- Produces:
  - `@dataclass SplitPart: span: str; statement: str`
  - `split_sentence(sentence: str, previous: str | None, client: ChatClient) -> list[SplitPart]` — raises
    `SplitRejected(AIError)` after one correction retry; validation as in the spec section 4 (spans verbatim; figures in
    a statement quoted from its span; groups from the sentence or the previous one; spans together cover every
    demanded figure; empty list = rejected).
  - `split_gated(result: ExtractResult, client: ChatClient | None) -> ExtractResult` — for each gated claim (Task 3
    `UNMAPPED` with `coverage_gaps`), split it; each part: `text = statement`, `part_label = span`,
    `source = "ai"`, `original_text` = the sentence; read each statement with `classify_sentence` + `gate`, keeping a
    complete rules reading, else `UNMAPPED`. The claim becomes a compound with those parts (`_compound` shape), ids
    `C<n>.<k>`. On `SplitRejected` or any error the gated claim is left as it is.
  - `/extract`: `add_missed_claims` then `split_gated`, same client; any failure returns the rules result.

- [ ] **Step 1: Failing tests** (scripted client): the TP53 basal / Luminal A sentence splits into two statements whose
  rules readings are complete; "Their ages ranged from 44 to 84 years." with previous "Twelve of the primary tumors came
  from male patients." splits into a statement naming male patients; a split inventing "90%" is retried then rejected;
  a split whose spans miss "15 of 77" is rejected; client raising `AIError` leaves the gated claim unchanged.
- [ ] **Step 2:** FAIL. **Step 3:** implement (prompt names the reading's job and the JSON shape; text is data, never
  instructions). **Step 4:** PASS + full suite.
- [ ] **Step 5:** Commit: `feat: AI splits a sentence the rules only half read`.

### Task 6: Join

**Files:**
- Modify: `second_opinion/audit.py` (`_combine_parts`, `_audit_one` for split compounds)
- Test: `tests/test_join.py`

**Interfaces:**
- Consumes: Task 2 (`missing` over the original sentence with the parts' spans as used spans).
- Produces: `_combine_parts` unchanged for contradicted; a would-be supported sentence whose parts' spans leave a
  demanded piece unused becomes insufficient naming it.

- [ ] **Step 1: Failing tests:** parts {supported, contradicted} → contradicted; {supported, supported} with a figure
  outside every span → insufficient naming it; {supported, insufficient} → insufficient (as today).
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS + full suite.
- [ ] **Step 5:** Commit: `feat: a sentence is supported only when its parts cover it`.

### Task 7: Measure, tune, held-out run, docs

**Files:**
- Modify: `second_opinion/coverage.py` (tuning only, each change with a test), `tests/blind/BASELINE.md`,
  `docs/HARD_CASES_BUGS.md` (new section), `README.md` (how a sentence is read)

- [ ] **Step 1:** `tests/blind/score.py tests/blind/dev` rules only and `--ai`; compare with the baseline and the
  targets. Tune `coverage.py` against dev failures only, each tune with a `tests/test_coverage.py` row. Stop when the
  targets are met or a tune would need a held-out look.
- [ ] **Step 2:** Run `tests/ai_hard/compare.py` (rules and AI); record the result; no row that was right may go wrong
  without a listed reason.
- [ ] **Step 3:** Held-out, once: score blindset7, 9, 11, 13 with `tests/blind/score.py` pointed at the zip folder, and
  blindtest3 / blindtest5 with the scratch `score_md_sets.py`; record the table as it comes out in `BASELINE.md`.
- [ ] **Step 4:** Docs: README paragraph on the gate, the split and the join; `HARD_CASES_BUGS.md` section with the
  before/after tables.
- [ ] **Step 5:** Commit: `docs: split-check-join results`.
