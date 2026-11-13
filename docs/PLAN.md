# Plan

Summarised from [Idea_Analysis_Report.pdf](Idea_Analysis_Report.pdf).

## Why this combination

Research Claim Auditor has a hidden test file and an organizer answer key. Claim Ladder is the
screen a judge understands in seconds. Together: objective score plus a memorable demo.

## Scope (cut to finish by Saturday 2:15 PM ET)

Keep:
- 3 "count it differently" choices, 8 variants total: subtype label (RNA-seq call vs 2012 study label),
  women only vs everyone, primary tumors only vs all samples.
- 2 skeptic tests: shuffle the labels, leave one hospital out.
- Check types: sample counts, percentages, group comparisons, "data can't answer" (treatment, cause, prediction).
- Optional LLM for claim extraction only. Fallback: sentence splitter, user ticks which are claims.

Cut: survival models, live AI agents, slide images.

## Practice report expectations

| Claim | Expected verdict |
|---|---|
| 535 of 1,101 primary tumors have all five layers | supported |
| ~62% of subtyped primary tumors are Luminal A | contradicted (49.9%, 421/844 with RNA call; 44.3% of 522 with 2012 label) |
| Highest ER-alpha patients responded best to hormone therapy | insufficient_evidence (no treatment-response data) |

Trap: the two subtype columns spell names differently (`LumA` vs `Luminal A`). Normalise before counting.

## Build order

| When | Goal |
|---|---|
| Thu Nov 12 | Checks for the 3 practice claims on real data. Post as Checkpoint 1. |
| Fri Nov 13 | Claim Ladder screen, click-to-proof, solidity tags, `audit.json` export. Repo swap with paired team. |
| Sat Nov 14 AM | Role views, overall decision and sign-off, accessibility pass, README, demo video. Rehearse with the practice envelope. |

## Risks

- Unseen claim types: build ready-made checks for common types.
- Unknown exact `audit.json` expectations: run `format/validate.py` early and often.
- Claim extraction unreliable: AI optional, manual tick fallback.
- Setup breaks elsewhere: use Friday repo swap, pin versions.
