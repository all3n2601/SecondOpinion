# Split, check, join: no verdict on a sentence we only half read

Date: 2026-11-14 · Status: approach A chosen by the owner; builder check done (answers folded in); awaiting approval

## Intent

On the independent blind sets (`tcga-brca-blind-tests.zip`: blindset6–13 and 15 with `key.json`, plus blindtest3 and
blindtest5), the auditor gets 65% of verdicts right with the rules only and 70% with the AI helper on. The worst
failure is **a true claim called "contradicted": 92 of 495 claims with the rules, 94 with the AI**. Almost every
one is the same mistake: the sentence says more than the reading used, and the verdict is given anyway.

- A subgroup is dropped: "TP53 … 85% in basal-like vs 10% in Luminal A" is checked as TP53 in all tumors.
- A number is paired with the wrong quantity: "1,978 to 1,133" (frozen vs diagnostic slides) becomes two unrelated
  counts; "44 of 516 N0 patients died" becomes all deaths.
- A comparison or second figure is ignored: "18 tumors, the same number as SF3B1"; "432 tumors … about a third".
- A reference to the previous sentence is lost: "Their ages ranged from 44 to 84" (their = the 12 male patients).

The previous session fixed patterns one by one (`docs/HARD_CASES_BUGS.md`) and reached 129/129 on its own cases,
but new writers keep finding new shapes. The owner asked for a structural fix: **break a sentence into several
claims, check each, then join them again**, and never give a verdict on a reading that skipped part of the sentence.

## Goals

- **Coverage gate.** After any reading of a sentence (rules or AI), our code checks that every figure and every named
  group in the sentence was used by some part of the reading. A reading that skips something is not trusted.
- **Split with the AI.** A sentence that fails the gate (with the AI on) is split by the AI into self-contained
  statements, one figure each, with its group spelled out and references to the previous sentence resolved. Each
  statement is read by the rules first, then by an AI plan if the rules cannot read it; our code computes every number.
- **Join.** The sentence's verdict is its worst part, as today. A sentence whose parts still leave a figure or group
  unused is "can't check" (insufficient evidence), naming what was not checked; it is never supported or contradicted.
- **Safe without the AI.** With the AI off, a sentence that fails the gate is "can't check", with a reason naming the
  unused words. This alone should turn most of the 92 dangerous answers into safe ones.
- **Measured honestly.** Development uses five blind sets; the other sets are held out and scored once, at the end.

## Non-goals

- No change to verdict tolerances, the check functions' arithmetic, or what the release can answer.
- Headings that the rules read as counts ("Slide 1: The usual suspects") and topic sentences the AI reports as
  claims are separate problems (listed under "Later").
- The browser's manual "classify this sentence" path (`POST /classify`) gets the gate but not the AI split (it has no
  neighbouring sentence to resolve references with).
- No Decision Record / `audit.json` format change beyond fields the format already has.

## Anti-goals (a failure even if it works)

- A verdict on a sentence whose figures or groups were not all checked.
- The AI seeing data values. The split prompt sees only report text (the sentence and the one before it), as the
  claim finder already does.
- A number on screen that the AI produced: every figure a split part states must be copied from the sentence (the
  existing quote guard), and every computed value comes from our code.
- A large drop in what the rules alone get right: sentences the rules read completely today must still pass the gate.

## Constraints

- Python package `second_opinion` (rules in `extract.py`, checks in `checks/`, AI in `ai/`), FastAPI routes in
  `apps/api`, Next.js client in `apps/web`. Tests: pytest (1,165 passing on `main`), the hard-case harness
  `tests/ai_hard/compare.py`, vitest.
- `/audit` receives claims only, not the report. Anything that needs the previous sentence happens at `/extract`,
  which has the whole report.
- The AI client is optional (`make_client()` may be None). Every AI step must degrade to a safe answer.
- Existing pieces to reuse: `find_numbers` and `numwords` (figures, including number words), `find_entities`
  (named groups), `_unchecked_numbers` in `audit.py` (today's narrower version of the gate, AI plans only),
  `plan_claim` / `run_plan` (AI plans, quote guard), `_combine_parts` (worst part decides).

## Approaches considered

- **A. Coverage gate on every reading, AI split for sentences that fail it (chosen).** Safe first (the gate works with
  the AI off), smart second (the split recovers the right verdict), and simple sentences keep their deterministic
  rules reading.
- **B. AI splits every sentence with more than one figure.** Simpler routing, but with the AI off many multi-figure
  sentences the rules read correctly today (tables, "535 of 1,101 (48.6%)") would drop to "can't check".
- **C. A smarter rules splitter, no AI.** Predictable and offline, but it is the pattern-by-pattern approach that has
  stalled on new writing styles.

## Design

### 1. What a sentence states (`second_opinion/coverage.py`, new)

`sentence_demands(text) -> Demands`: the pieces a complete reading must use.

- **Figures**: every number `find_numbers` reports, number words included (via `numwords`), except numbers that are
  part of a name or a definition: gene and protein names (TP53, PAM50, ERBB2), stage labels (Stage IIA), GISTIC codes
  given as definitions ("GISTIC value 2", "-1 or -2") and the like. Ages and years used as cut-offs count as figures.
- **Groups**: every entity `find_entities` reports (subtype, receptor status, histology, stage, sex, gene, menopause,
  vital status, …), deduplicated by attribute and category.
- **Back references**: a sentence that opens with a word pointing at the previous sentence's group ("Their", "These",
  "This group", "Of these", "Among them", "A further", "The remaining", "Of those", "It", "They") demands that group;
  the rules alone can never satisfy it.
- **The counted thing**: the noun a figure counts (slides, samples, tumors, patients, deaths, genes, proteins). A
  reading that counts a different thing than the sentence does is incomplete ("1,978 to 1,133" frozen vs diagnostic
  *slides* read as counts of *tumors*).
- **Unrecognised qualifiers**: words that look like a group label but that `find_entities` does not know, by a short
  pattern list (TNM codes such as N0, N3, T2, M1; magnifications such as 40x; slide kinds "frozen", "diagnostic",
  "FFPE"; "equivocal"). The rules cannot have used them, so a sentence with one is incomplete for the rules; an AI
  split part may use them through a plan filter. This catches "44 of 516 N0 patients died" without widening
  `find_entities`, which every rule depends on.

### 2. What a reading used

`reading_uses(claim) -> Uses` from a claim and its parts: stated values, highs and totals; age, year and count
thresholds; and the groups in its params (`subtype`, `attribute`/`category`/`category_b`,
`within_attribute`/`within_category`, `group_a`/`group_b`, `subtype_source`). For an AI-planned claim, the plan's
filters, its quoted span and its stated figure.

`missing(demands, uses) -> list[str]`: the words of the sentence a reading left unused ("basal-like", "10%",
"twelve"). Empty means complete.

The words go in a new optional field, `Claim.coverage_gaps: list[str]` (default empty), mirrored in the API model and
the web `Claim` type, so `/audit` and the browser can name them. `audit.json` is built field by field in `export.py`,
so the field does not reach the organizers' format; the finding's summary already carries the "can't check" reason.

### 3. Where the gate runs

- **At `/extract`**, after the rules read each sentence: a rules claim with anything missing is replaced.
  - AI on: the sentence goes to the split step (section 4).
  - AI off: the claim becomes `UNMAPPED` with `needed_data` naming the unused words, so `/audit` reports it as
    "can't check": "This sentence also states …, which the rules could not check; a person should check it."
- **At `/audit`**, after an AI plan (replacing today's numbers-only `_unchecked_numbers`): a plan whose reading misses
  a figure or group of the text it was given gives "can't check", whatever its verdict, contradicted included. The
  text it was given is a split statement, already self-contained, so `/audit` needs no previous sentence: it trusts
  `/extract` to have resolved back references, and checks the statement itself.
- **At `/classify`**: the gate only (no split).

### 4. The split step (`second_opinion/ai/split.py`, new)

`split_sentence(sentence, previous, client) -> list[SplitPart]`, called from `/extract` for each sentence that fails
the gate (and for sentences the AI claim finder recovers).

- The model receives the sentence and the one before it, and returns
  `{"parts": [{"span": <exact words of the sentence>, "statement": <self-contained sentence>}]}` or
  `{"parts": []}` when the sentence makes no checkable statement.
- Validation in our code, with one correction retry (as the planner does), then failure:
  - every `span` occurs in the sentence word for word;
  - every figure in a `statement` is quoted from its `span` (the existing quote guard and `numwords`); no new numbers;
  - groups named in a `statement` may come from the sentence or the previous sentence only;
  - together the spans cover every figure in the sentence (section 1).
- Each valid part becomes a part claim: `text` = the statement, `part_label` = the span, `source = "ai"`,
  `original_text` = the sentence. The rules read each statement first (they handle simple single-figure sentences
  well); a statement the rules cannot read completely is left `UNMAPPED` for an AI plan at `/audit`.
- Split failure, or AI off: the sentence is `UNMAPPED` with the gate's reason (section 3).

### 5. Join (`audit.py` `_combine_parts`)

Unchanged rule: the worst part decides (contradicted, then insufficient, then supported). Each part has already
passed the gate against its own statement, so a contradicted part is a definite error, read completely: it keeps
the sentence contradicted even when another part of the sentence could not be checked. Added: if the parts' combined
spans still leave a figure or group of the original sentence unused, a sentence that would otherwise be supported
is "can't check", with the missing words named.

In short, "never a verdict on an incomplete reading" applies to each reading (a rules claim, an AI plan, a split
part). It does not stop a complete, contradicted part from deciding the sentence.

### 6. What the reviewer sees

- A split sentence shows its parts as today's multi-part claims ("Each part of the sentence").
- A gated sentence shows "can't check" with the unused words, so a person knows exactly what to verify.
- Split statements carry the existing AI marker, since the AI chose the wording; numbers stay ours.

### 7. Measurement

- `tests/blind/score.py` (in the repo): scores a folder of blind reports with `key.json` / `nonclaims.json`, rules
  only or AI on, and prints correct, true-called-wrong, wrong-called-true, can't-check and non-claims flagged.
- **Development sets** (copied into `tests/blind/dev/`): blindset6, blindset8, blindset10, blindset12, blindset15.
- **Held-out sets** (stay outside the repo until the end): blindset7, blindset9, blindset11, blindset13, blindtest3,
  blindtest5. blindtest3 and blindtest5 have Markdown answer keys and no non-claims list; they are scored by the
  existing parsers (exact quotes for blindtest3, best-overlap pairing for blindtest5, which is approximate by about
  three entries) and report verdicts only.
- Scoring rules (the same as the 65% / 70% baseline): a key entry with no matching finding counts as wrong ("not
  picked up"); the one entry marked `debatable` is counted like any other and listed separately.
- Baseline today on the dev sets is recorded before any change. Targets on the dev sets:
  - true called contradicted: down from about one claim in five to at most one in thirty, rules only and AI on;
  - wrong called supported: not up;
  - overall correct: up with the AI on; with the rules only it may dip slightly where a correct-but-incomplete
    reading now says "can't check", and every such case is listed for review.
- The full pytest suite and `tests/ai_hard/compare.py` keep passing, except where a test asserted a verdict on a
  sentence the gate now rightly refuses; each such change is listed with its reason.
- The held-out sets are scored once at the end and reported as they come out.

## Builder calls made during design (owner may revisit)

- The gate is sentence-level: a reading that misses anything is discarded whole, rather than keeping the parts that
  look complete. Simpler and safer; attribution of a group to one part is unreliable.
- The split happens at `/extract`, where the previous sentence is known; `/audit` only plans parts.
- The rules get the first try at each split statement; the AI plans only what the rules cannot read completely.
- A contradicted part keeps the sentence contradicted even when another part could not be checked (each part is
  gated on its own statement first).
- The gate also checks the counted thing and a short list of qualifier patterns `find_entities` does not know,
  rather than widening `find_entities` itself.
- One new optional field, `Claim.coverage_gaps`, carries the unused words; `audit.json` is unchanged.
- Sentences the rules mark "can't answer" (`NOT_ANSWERABLE`: treatment, causation, prediction) skip the gate and the
  split: they are already "can't check".

## Left to the builder

- The exact list of name-like numbers and back-reference words, tuned against the dev sets and the existing tests.
- Prompt wording for the split step.
- How `reading_uses` maps each `ClaimParams` field and each plan filter to groups and figures.
- Whether the gate reason is phrased per figure or per group.

## Later (not in this change)

- Headings and slide titles read as counts ("Slide 1: …").
- Topic sentences the AI claim finder reports as claims ("Losses are rarer than gains.").
- The AI split for `/classify`.
