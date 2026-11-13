# SecondOpinion

OncoSys Cancer AI Lab hackathon · **Track 2: Evidence Navigator** · Research Claim Auditor + robustness checks. The main screen is the "Claim Ladder".

**User:** a reviewer handed a report and asked "can we trust this?"

**Workflow:** give the tool a report and a data release folder. For each claim it shows:

1. **Verdict:** `supported`, `contradicted` or `insufficient_evidence`.
2. **Solidity:** does the verdict hold under every reasonable way of counting, or only one?
3. **Strongest honest sentence:** the claim rewritten with the over-strong parts crossed out
   (~~about 62% of~~ **49.9% (421 of 844)** of primary tumors with an RNA subtype call were Luminal A).
4. **One report decision:** Proceed / Fix / Narrow / Stop, who must sign off, and an `audit.json`
   in the [shared findings format](https://github.com/disleveK/oncosys-hackathon-challenge/tree/main/format).

Every number links to the samples, file and code behind it. The AI (optional) only helps pull
sentences out of the report. It never sets a verdict.

> Research prototype. No diagnosis, treatment advice or risk scores.

## Status

Scaffold only. See [docs/PLAN.md](docs/PLAN.md) for scope and build order, and
[docs/Idea_Analysis_Report.pdf](docs/Idea_Analysis_Report.pdf) for why this idea was chosen.

## Setup

```bash
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git ../oncosys-hackathon-challenge
python ../oncosys-hackathon-challenge/data/tcga-brca/fetch.py
pip install -r requirements.txt
```

## Run

```bash
python -m second_opinion.cli --release <release-folder> --report <report.md> --out audit.json
python ../oncosys-hackathon-challenge/format/validate.py audit.json
```

The release folder is any folder with the five TCGA-BRCA files, so the same command works on
release A, the practice envelope, or a sealed envelope's `release/`.

## Tests

```bash
pytest
```

## Third-party

TCGA data: UCSC Xena and NCI Imaging Data Commons, see the challenge repo's `DATA_LICENSES.md`.
No raw TCGA files are committed here.
