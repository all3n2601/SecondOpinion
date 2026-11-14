# Blind-set baseline

Measured 2026-11-14 on branch `feat/claim-split-join`, before the coverage gate and AI split, with the five dev sets
in `tests/blind/dev/` (blindset6, 8, 10, 12, 15: 275 key entries, 172 non-claims). The other blind sets are held out and
are never scored while developing.

Re-run:

```
SO_RELEASE_DIR=<release A raw> .venv/bin/python tests/blind/score.py tests/blind/dev [--ai] [--json OUT]
```

Columns: correct = verdict matches the key; true->contradicted = key says supported, we say contradicted;
wrong->supported = key says contradicted, we say supported; can't check = we say insufficient evidence where the key
has a verdict; other wrong = any remaining mismatch (the key says it cannot be checked and we gave a verdict);
not picked up = no finding contained the key sentence; non-claims flagged = findings raised on sentences that are not
claims.

## Rules only (SO_AI=off)

| set | correct | true->contradicted | wrong->supported | can't check | other wrong | not picked up | non-claims flagged |
|---|---|---|---|---|---|---|---|
| blindset10 | 43/55 | 5 | 2 | 5 | 0 | 0 | 1/41 |
| blindset12 | 25/55 | 10 | 1 | 13 | 0 | 6 | 15/53 |
| blindset15 | 32/55 | 12 | 1 | 10 | 0 | 0 | 2/29 |
| blindset6 | 34/55 | 15 | 0 | 4 | 0 | 2 | 2/14 |
| blindset8 | 44/55 | 4 | 1 | 4 | 1 | 1 | 3/35 |
| **Total** | 178/275 | 46 | 5 | 36 | 1 | 9 | 23/172 |

## With AI (the app's normal path: add missed claims, then audit with the AI executor)

| set | correct | true->contradicted | wrong->supported | can't check | other wrong | not picked up | non-claims flagged |
|---|---|---|---|---|---|---|---|
| blindset10 | 46/55 | 6 | 2 | 1 | 0 | 0 | 4/41 |
| blindset12 | 29/55 | 11 | 1 | 13 | 0 | 1 | 15/53 |
| blindset15 | 36/55 | 12 | 2 | 5 | 0 | 0 | 5/29 |
| blindset6 | 37/55 | 15 | 0 | 3 | 0 | 0 | 2/14 |
| blindset8 | 46/55 | 4 | 1 | 3 | 1 | 0 | 4/35 |
| **Total** | 194/275 | 48 | 6 | 25 | 1 | 1 | 30/172 |

## After Task 3: the coverage gate at extraction, rules only (SO_AI=off)

A rules reading that leaves a figure, group, counted thing, qualifier or back reference of its sentence unused is now
UNMAPPED with `coverage_gaps`, and the audit says "can't check".

| set | correct | true->contradicted | wrong->supported | can't check | other wrong | not picked up | non-claims flagged |
|---|---|---|---|---|---|---|---|
| blindset10 | 36/55 | 2 | 0 | 17 | 0 | 0 | 1/41 |
| blindset12 | 22/55 | 5 | 0 | 22 | 0 | 6 | 15/53 |
| blindset15 | 22/55 | 7 | 0 | 26 | 0 | 0 | 2/29 |
| blindset6 | 31/55 | 9 | 0 | 13 | 0 | 2 | 2/14 |
| blindset8 | 36/55 | 2 | 1 | 14 | 1 | 1 | 3/35 |
| **Total** | 147/275 | 25 | 1 | 92 | 1 | 9 | 23/172 |

Against the rules-only baseline, per key entry: 21 of 46 true->contradicted and 4 of 5 wrong->supported became can't
check; no entry moved into either dangerous column. 31 entries went from correct to can't check. Every one is a
reading that did not use part of its sentence; the words named are the gate's:

| set | report | key | sentence | left unused |
|---|---|---|---|---|
| blindset10 | r1 | contradicted | The slide manifest lists 3,111 pathology slides, of which 1,133 are frozen sections. | slides, 1,133, sections |
| blindset10 | r3 | supported | PIK3CA is the most frequently mutated gene, altered in 273 of 791 tumors. | 791 |
| blindset10 | r3 | supported | CDH1 mutations were found in 12.9% of tumors, slightly more often than GATA3 mutations. | 12.9% |
| blindset10 | r4 | supported | Median age at diagnosis was 58 years, and 12 patients were men. | 58 |
| blindset10 | r5 | supported | E-cadherin protein was markedly reduced in lobular carcinomas (mean -1.89 across 101 tumors) relative to ductal carcinomas. | 1.89, 101 |
| blindset10 | r6 | supported | (A) Subtype shares among 844 subtyped primary tumors: Luminal A 49.9%, Luminal B 22.7%, ... | 844 |
| blindset10 | r6 | contradicted | Basal-like tumors had the highest death rate of any subtype, 19 of 140. | 19, 140 |
| blindset12 | r2 | supported | TTN is the third most frequently mutated gene, behind PIK3CA and TP53. | PIK3CA, TP53 |
| blindset12 | r2 | contradicted | TTN shows up in 137 tumors, so roughly one in four. | one in four |
| blindset12 | r6 | contradicted | Of the slides with a recorded objective, 640 were scanned at 20x. | 20x |
| blindset15 | r1 | supported | Nearly all Luminal A tumors with a recorded ER result were ER-positive, 393 of 402. | 393, 402 |
| blindset15 | r1 | supported | Most ER-positive tumors were also PR-positive, 682 in all. | 682 |
| blindset15 | r1 | contradicted | Of the 164 HER2-positive tumors, the largest share came from the HER2-enriched subtype. | 164 |
| blindset15 | r2 | supported | KMT2C mutations were nearly twice as frequent in ER-positive as in ER-negative tumors (11.1% versus 6.2%). | 11.1%, 6.2% |
| blindset15 | r2 | supported | PTEN mutation frequency was almost identical in ER-positive and ER-negative tumors, at about 6.5% and 6.2%. | ER-positive, ER-negative, 6.2% |
| blindset15 | r2 | contradicted | EGFR amplification (23 tumors) was twice as common as KRAS amplification. | 23 |
| blindset15 | r4 | supported | 2 \| PIK3CA was amplified at a high level in 54 tumors, 5.0% of the copy-number cohort. | 54 (the row number 2 was read as the count) |
| blindset15 | r4 | contradicted | 3 \| TP53 deep deletion was seen in 51 tumors. | 51 (the row number 3 was read as the count) |
| blindset15 | r5 | supported | Diagnostic slides exist for nearly all primary tumors, 1,061 of 1,101. | slides, 1,061, 1,101 |
| blindset15 | r6 | contradicted | Frozen top sections are the most common slide kind, with 1,814 slides. | sections, slides |
| blindset6 | r1 | contradicted | Basal-like tumors formed the second-largest group, ahead of Luminal B. | Luminal B |
| blindset6 | r4 | supported | The median age at diagnosis was 58 years, with patients ranging from 26 to 90. | 26, 90 |
| blindset6 | r4 | contradicted | Frozen top sections are the single most common slide kind, with 1,418 slides, and every primary tumor has at least one slide. | sections, slides |
| blindset8 | r1 | contradicted | Of these, 1,101 are primary tumors, 139 are normal tissue samples and 9 are metastases. | Of these |
| blindset8 | r1 | supported | Twelve primary tumors come from male patients, a little over 1% of all primary tumors. | 1% |
| blindset8 | r1 | contradicted | Frozen sections therefore make up about 68% of all slides, and only three primary tumors have no slide at all. | 68%, three, tumors |
| blindset8 | r2 | supported | Protein data covers 742 primary tumors, about 67% of all primaries. | 742 |
| blindset8 | r3 | contradicted | Luminal B is second with 192 tumors, followed by HER2-enriched. | Luminal B, HER2-enriched |
| blindset8 | r4 | supported | Most triple-negative tumors are Basal-like, 77 of the 116. | 77, 116 |
| blindset8 | r5 | contradicted | CDH1 ranks third among all genes, mutated in about 13% of tumors. | 13% |
| blindset8 | r7 | supported | The median age at diagnosis among primary tumors is 58 years, with patients ranging from 26 to 90. | 26, 90 |

The 25 true->contradicted left are readings the gate counts as complete because every figure is recorded, but under
the wrong quantity: means read as counts ("means of 1.33 and 0.38" as "7 of 1.33" tumors, "median age (54)" as 54
tumors), a second layer or sample type folded into one count ("RNA for seven and protein for five samples"), and
check-level disagreements ("844 received a PAM50 call").
