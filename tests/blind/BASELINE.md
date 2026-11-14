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
