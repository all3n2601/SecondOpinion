# Hard cases: bugs to fix

Found by `tests/ai_hard/compare.py`: 77 sentences in five reports (`tests/ai_hard/*_report.md`), each with a verdict
worked out from the raw release A files by hand (pandas, not our code). Every sentence was audited twice: rules only,
and rules plus the AI helper.

**Baseline (2026-11-14): rules only 41/77, with AI 45/77.** A row only counts as right when the verdict is right
*and* it came from the number the sentence states; a right verdict from a misread number is "luck" and counts as wrong.

Run it again: `SO_RELEASE_DIR=../oncosys-hackathon-challenge/data/tcga-brca/raw .venv/bin/python tests/ai_hard/compare.py`

Each fix goes in with a failing test first, and the rules and the AI path get the same fix in the same style
(one shared helper where both need it), so neither path can disagree with the other.

## A. Wrong verdicts (the worst kind: a confident wrong answer)

| # | Sentence | We say | Truth | Cause |
|---|---|---|---|---|
| A1 | "Under one in fifteen primary tumours come from patients diagnosed before forty." | supported (AI) | contradicted: 6.9% is not under 6.7% | `judge_plan` (`ai/executor.py`) drops `stated.relation`, so "under", "over", "fewer than", "more than" never reach `bound` for share and count plans |
| A2 | "Fewer than 300 primary tumours come from patients diagnosed before fifty." | contradicted (AI) | supported: 297 | same as A1 |
| A3 | "Nearly eleven hundred primary tumours…" / "one thousand two hundred and forty-seven samples" / "A hundred and thirty-nine samples…" / "GATA3 is mutated in ninety-seven tumours" / "…nine hundred and ninety-nine…" | contradicted (read 11, 7, 9, 7, 9) | supported 1,100 / 1,247 / 139 / 97; 999 is wrong for a different reason | the rules' number reader takes one word of a compound number ("ninety-seven" -> 7, "eleven hundred" -> 11) |
| A4 | "Deep PTEN deletions appear in five dozen tumours." | contradicted, but read 5 | contradicted: 56, not 60 | "dozen" is not a number word |
| A5 | "ERBB2 is amplified in one tumour in eight with copy number data." | contradicted, a count of 1 | supported: 12.3% is about one in eight | "one *noun* in eight" is not read as a fraction |
| A6 | "Between 20% and 25% of staged tumours are stage III or IV." / "Over a quarter of staged tumours are stage III or higher." | supported / contradicted (stage III only, 23.3%) | contradicted / supported: III or IV is 25.1% | the rules keep the first category of "III or IV" and drop "or higher" |
| A7 | "Postmenopausal women outnumber premenopausal women about three to one." / "Basal-like tumours outnumber HER2-enriched tumours by more than two to one." | supported, but only checked "more than 1 to 1" | supported 3.08 / 2.10, which should be the checked numbers | "outnumber" sets ratio > 1 and the stated "three to one" is dropped; "outnumber ten to one" would also pass |
| A8 | "Mean ERALPHA protein is higher in ER-positive than in ER-negative tumours by about 3 units." | supported, direction only | supported: difference 3.05 | the size of the difference is never read or checked; "by about 30 units" would also pass |
| A9 | "Protein data cover 742 primary tumours measured across 131 proteins." | contradicted (131 checked as a tumour count, data 1,101) | supported: 742 tumours, 131 proteins | the second number becomes its own claim about tumours |
| A10 | "PIK3CA mutations are rarest in Basal-like tumours." | contradicted (ranks genes inside Basal-like: UBE2Q2 is rarest) | supported: Basal-like has the lowest PIK3CA rate (6.6%) | "rarest in <group>" is read as "the rarest gene in the group" |
| A11 | "Diagnoses span the years 1988 to 2013." | insufficient: "never makes diagnostic statements" | supported: years run 1988 to 2013 | the word "Diagnoses" trips the guard against diagnostic advice |

## B. Left unchecked although the release can answer it

| # | Sentence | We say | Truth | Cause |
|---|---|---|---|---|
| B1 | "Men contribute barely a dozen of the primary tumours." / "The typical patient was diagnosed at fifty-eight, going by the median." | insufficient (AI plan rejected) | supported 12 / 58 | the AI quote guard (`_derivable`) has no "dozen" and no compound words, so honest plans are refused |
| B2 | "None of the male patients had a Basal-like tumour." | insufficient | supported: 0 of 12 | "none" means 0, but 0 is not "in the sentence" for the guard; the rules have no zero-count form |
| B3 | "Not a single primary tumour lacks an age at diagnosis." | insufficient | contradicted: 4 lack one | double negative over missing values; no rule, and the AI plan has no number |
| B4 | "Basal-like patients were diagnosed younger than Luminal A patients." / "…the youngest at diagnosis of any RNA subtype." / "Luminal A patients were the oldest…" | not read | supported / contradicted (Normal-like 53 < Basal-like 54) / supported | no group-median comparison without the numbers written; no AI plan op for it |
| B5 | "Luminal B patients share the cohort's median age at diagnosis of 58 years." | insufficient (rules) | supported | rules only (the AI gets it) |
| B6 | "TTN ranks third among mutated genes." | insufficient | supported | gene ranks other than first are not read; no AI op for gene ranks |
| B7 | "HER2-positive tumours by immunohistochemistry are fewer than ERBB2-amplified tumours." | insufficient | contradicted: 164 vs 133 | comparing counts of two different attributes is not supported |
| B8 | "TP53 mutations are roughly eight times as common in Basal-like as in Luminal A tumours." | insufficient | supported: 84.9% / 10.3% = 8.2 | ratio of two rates not supported |
| B9 | "Nine in every hundred tumours with mutation data have a KMT2C mutation." | insufficient | supported: 9.7% | "N in every hundred" is not read |
| B10 | "Less than 1% of primary tumours were diagnosed before 1990." / "Diagnoses span the years 1988 to 2013." | insufficient | supported | no year-of-diagnosis attribute (`year_of_initial_pathologic_diagnosis`) in the rules or the AI fields |
| B11 | "The mutation file lists more than 40,000 genes." | insufficient | supported: 40,543 | claims about the files themselves (genes, proteins) are not supported |
| B12 | "The median number of positive lymph nodes was one." | not read | supported | no lymph-node attribute (`number_of_lymphnodes_positive_by_he`) |
| B13 | "Luminal B comes in second…", "The oldest patient at diagnosis was ninety.", "Patients aged seventy or more account for over a third…" | not read by rules | supported / supported / contradicted | rules only (the AI gets them); worth teaching the rules too |

## C. Root cause behind most of B: the AI plan is narrower than the rules

The rules read 20 attributes through one resolver (`checks/attributes.py`: ER, PR, HER2, hormone receptor,
triple-negative, stage, histology, menopause, subtype, vital status, mutation, amplification, deletion, gain, loss,
DSS, PFI, slides, age group). An AI plan may only filter on 8 fields (`ai/plan.py`: sample type, sex, two subtype
columns, ER, HER2, layer, age). So any sentence the rules miss about PR, stage, histology, a gene or survival has no
way through the AI either.

Fix: let a plan filter on any attribute the rules know, read through the same `attribute_values()`, and add the
missing plan operations (group statistic comparison, ratio of two counts or rates, gene rank, file facts). The AI
then reaches everything the rules can, with the rules' own definitions (equivocal HER2 is unknown, GISTIC 2 is an
amplification, and so on).

## Fix order

1. A1–A2 (AI bound), A3–A5 + B1 + B9 (one shared number-word reader for rules and AI), A6 (category unions),
   A7–A8 (stated ratio and difference sizes), A9–A11.
2. C (AI plan reaches every rules attribute), then B4, B6–B8, B10–B12 as plan operations and rules.
3. B2–B3, B5, B13.

## Fixed

**After the fixes (2026-11-14): rules only 62/77, with AI 77/77.** Full suite: 1,085 passed, 3 skipped.
The rules give no wrong verdict on the 77 cases; every row they miss is one they leave to the AI.

| Bug | Fix | Rules | AI |
|---|---|---|---|
| A1–A2 | the bound ("under", "fewer than", "at least") comes from the sentence's own words via the rules' `bound_op`, for share, count and statistic plans (`ai/executor.py` `_sentence_bound`) | already right | fixed |
| A3–A5, B1, B9 | one number-word reader for both paths, `second_opinion/numwords.py`: compound words, "hundred", "thousand", "dozen", fractions with any number word ("one in fifteen", "nine in every hundred", "one tumour in eight"); the AI quote check now reads whole phrases, so "ninety-seven" can no longer be quoted as 7 or 90 | fixed | fixed |
| A6 | "stage III or IV", "stage III or higher", "stages I to III" are one group (`STAGE_UNION`; `attribute_values` relabels the union, like "Luminal") | fixed | via `in` filters |
| A7 | "outnumber … about three to one" keeps the stated ratio and its bound; "3:1" is no longer read as a count of 3 | fixed | n/a |
| A8 | "higher … by about 3 units" checks the size of the difference (`unit = "difference"`) | fixed | already right |
| A9, B11 | genes and proteins a file measures are their own count (`features:<layer>`), also as a part of a coverage sentence | fixed | n/a |
| A10 | "rarest in", "commonest in" rank the groups by rate | fixed | `rank_groups` |
| A11 | "Diagnoses span the years …" is not diagnostic advice (`unanswerable.py`) | fixed | `summary_stat` range |
| B2–B3 | a stated zero is quoted from "none", "not a single", "no men"; `is_unknown` filter for "lacks a value" | not yet | fixed |
| B4, B8, B7 | `compare_groups` (two groups by count, share or statistic; difference or ratio) and `rank_groups` (a subtype's place by rate or statistic, highest or lowest first) | not yet | fixed |
| B6 | gene ranks (`rank` with `category_field: mutated_gene`) | not yet | fixed |
| B10, B12 | numeric fields `diagnosis_year` and `positive_lymph_nodes` (filters and statistics, plus a `range` statistic) | not yet | fixed |
| B13 | ages written as words and "diagnosed before forty" name an age group | fixed | already right |
| C | AI plans filter on every attribute the rules read (`"field": "attribute"`), through the rules' own `attribute_values()`; the planner lists each attribute's legal values (labels only, no counts) | n/a | fixed |

## Round 2: a blind set, and the rules gaps closed

An independent agent wrote four more reports (`tests/ai_hard/blind*_report.md`, 52 claims) from the product brief
and the raw data alone, without seeing this code. First run: **rules only 37/52, with AI 39/52**. It found bugs
the hand-written cases had not, including two the committed code already had:

| # | Sentence | We said | Truth | Fix |
|---|---|---|---|---|
| D1 | "There are 421 Luminal A tumours." (any count of one subtype) | contradicted: checked as 421 of all 1,101 tumours | supported | a lone subtype with a count is the subtype's count (`_rule_attribute`); was in the committed code |
| D2 | "TP53 mutations are 8 times more common in Basal-like than in Luminal A tumours." | contradicted: ratio of the two subtypes' sizes | supported: 84.9% / 10.3% = 8.2 | ratio of two rates (`_rate_ratio`); was in the committed code |
| D3 | "The oldest patient was 90 at diagnosis." | contradicted: a count of 90 tumours | supported | "90 at diagnosis", "diagnosed at 26" are ages, read as statistics |
| D4 | "Under the 2012 consortium labels, Normal-like is the rarest group, at under 2%" | contradicted: read the RNA calls (2.7%) | supported: 1.5% by the 2012 labels | a claim can name its subtype source (`ClaimParams.subtype_source`) |
| D5 | "Mean ER-alpha protein is 2.18 in ER-positive tumors against -0.87 in ER-negative tumors" | contradicted: two counts, signs lost | supported | two means may have words between them ("in ER-positive tumors against") |
| D6 | "Where both the RNA-seq call and the 2012 label exist, the two agree for 90% of tumors." | contradicted: RNA coverage 99.6% | supported: 456 of 508 | AGREEMENT now has a rule and a check (`checks/agreement.py`) |
| D7 | "The median overall-survival time on record was 843 days" | contradicted (843 days compared in years at 1 decimal) | supported | converted times keep the precision written in their own unit |
| D8 | "TP53 … in basal-like tumors, where 85% carry one, against roughly one in ten Luminal A tumors." | contradicted: 85% of all tumours | supported | one value in two groups, a figure for each (`_rule_group_shares`) |
| D9 | "Just over half of the tumors scored HER2-positive by IHC carry an ERBB2 amplification." | contradicted: HER2-positive share | supported: 87 of 162 | "of the tumors scored X" names the subgroup |
| D10 | "The 257 primary tumors without an RNA subtype call were left out because their RNA quality was too low." | contradicted | insufficient: no quality records | sample-quality reasons are unanswerable |
| D11 | "GATA3 protein in ER-positive tumors exceeds that in ER-negative tumors by more than two units." | insufficient ("no GATA3 measurement") | contradicted: 1.62 | any RPPA protein compares between receptor groups |
| D12 | "HER2-enriched tumors had a lower death rate than Luminal A tumors." | insufficient (survival analysis) | contradicted: 20.9% vs 13.1% | a death *rate* is a share; "mortality", "risk of death" and survival still need a survival analysis |
| D13 | "includes 698 primary tumors with both RPPA data and a definitive ER result" | contradicted: 742 | supported | coverage among tumours with a known status |
| D14 | "Most tumors in the release were diagnosed in 2010 or later." | insufficient | contradicted: 44.2% | year-of-diagnosis groups (`diagnosis_year`), year spans, lymph-node statistics |
| D15 | "diagnosed before age 50", "diagnosed at 65 or older", "diagnosed about six years later on average than" | not read | supported / contradicted / contradicted | wider age cut-offs; mean or median age gaps, within a year when hedged |
| D16 | AI: "patients" planned over all 1,242 samples; stage value "IV" rejected; "Most" refused | wrong / insufficient | — | planner: patients mean primary tumours; stage names normalised; vague amounts quotable with their bound |

The rules also learned the rest of round 1's open list: zero inside a group ("None of the male patients had a
Basal-like tumour"), "lacks an age", median-age comparisons and ranks without numbers, ages written as words,
placement words ("TTN ranks third", "comes in second"), and counts of two different attributes against each other.

**After round 2 (all 129 claims): rules only 128/129, with AI 129/129, the same on three runs.** Full suite 1,152
passed. Every report's `audit.json` passes the organizers' `format/validate.py`; the practice brief still gives
supported / contradicted / insufficient.

## Round 3: a second blind set in other formats

A second independent agent wrote three reports in formats the first sets lacked: a results section with markdown
tables, a dense abstract, and bullet points (`tests/ai_hard/blindB*_report.md`, 45 claims). First run: **35/45 for
both** the rules and the AI.

| # | Sentence | We said | Truth | Fix |
|---|---|---|---|---|
| E1 | table row "\| Basal-like \| 141 \| 12.8 \|" under a "%" column | supported (141 only) | contradicted: 141 of 844 is 16.7% | a table header's "%" column gives its bare numbers their unit |
| E2 | caption "... with an RNA-seq subtype call (n = 844)" | contradicted: RNA coverage 1,097 | supported | "RNA-seq subtype call" is a subtype-call count |
| E3 | "the 1,101 primary breast tumors ..., of which 535 (48.6%) carry all five data layers" | contradicted: count of 1,101 | supported | "of which N" is the count and the number before it its total; the bracketed percent is checked too |
| E4 | "HER2 overexpression by immunohistochemistry was uncommon (22.5%; ...)" | HER2-enriched subtype | HER2-positive status | "HER2 overexpression" names the status |
| E5 | "with a mean RPPA difference of 2.0–2.5 units" | supported (direction only) | contradicted: 3.05 | a difference may be a range, or "a gap of" |
| E6 | "2.18 in the 529 ER+ tumors with protein data against -0.87 in the 169 ER- tumors" | contradicted: protein coverage | supported | two means may have up to nine words between them |
| E7 | "Every one of the 742 primary tumors with protein data also has RNA-seq data." | contradicted (read "one" as 1) | supported | "every one of" is not a count; the 742 is checked as a second figure |
| E8 | "Basal-like tumors are almost all ER-negative: 124 of 136 with a known ER status (91.2%)." | contradicted: 141 Basal-like | supported | a count and its bracketed percent are one statement about one group |
| E9 | "Mean cyclin B1 protein (RPPA CYCLINB1) is lower in ..." | insufficient ("no B1") | contradicted | the protein's name in "(RPPA NAME)" or two words ("cyclin B1") |
| E10 | "Diagnosis years span 1988–2013, and 2010 is the busiest single year with 225 diagnoses." | insufficient (diagnostic guard) | supported | "225 diagnoses" is a count; the most common year and its count are checked |
| E11 | "a group of 31 tumors that the 2012 study placed in LumB and that RNA-seq calls LumA" ("the largest single disagreement") | contradicted: subtype rank | supported | one cell of the 2012-versus-RNA table, and its rank among the disagreements |

**After round 3 (all 174 claims): rules only 173/174, with AI 174/174.** Full suite 1,163 passed; every report's
`audit.json` is valid; the practice brief is unchanged.

### Still open

"Luminal B patients share the cohort's median age at diagnosis of 58 years" (two medians in one phrase) is left to
the AI; with the AI off it is insufficient evidence, not a wrong verdict.
