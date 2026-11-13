# SecondOpinion

**Research Claim Auditor** for the OncoSys Cancer AI Lab hackathon, **Track 2: Evidence Navigator**.

SecondOpinion checks a research report against a TCGA-BRCA data release. For every factual
sentence it says whether the data supports it, how solid that answer is, and the strongest honest
way to word it. A person then reviews each verdict and records one decision, and the tool exports an
`audit.json` in the organizers' shared findings format, plus a Decision Record.

**Demo video:** _link to be added_ (3 minutes; script in [docs/DEMO.md](docs/DEMO.md))

> Research prototype. Not a clinical decision system. Verdicts need human review.
> No diagnosis, treatment advice or risk scores.

## Who it is for

**User:** a reviewer handed a report and asked, "Can we trust this?"

**The one workflow they finish:** load the report and a release folder → keep the sentences that
are claims → read the Claim Ladder for each claim → accept or override every verdict → choose one
decision → download `audit.json` and the Decision Record.

For each claim the tool shows:

1. **Verdict:** `supported`, `contradicted` or `insufficient_evidence`. Verdicts come only from code.
2. **Solidity:** whether the verdict holds under all 8 reasonable ways of counting (RNA-seq subtype
   call vs 2012 study label × everyone vs women only × primary tumors vs all samples), or only some.
3. **Strongest honest sentence (Claim Ladder):** the claim with the over-strong part crossed out,
   e.g. ~~about 62%~~ **49.9% (421 of 844)** of primary tumors with an RNA subtype call were Luminal A.
4. **Proof:** the number with its denominator, the sample IDs, the release files and a pandas
   snippet that reproduces it.
5. **One report decision:** Proceed / Fix a problem / Narrow the question / Stop, the rule that
   suggested it, who must sign off, and what would change it. The reviewer makes the final call.

## Team

| Name | Built |
| --- | --- |
| Allen | Audit engine: release loader, checks, verdict rules, robustness, `/audit`, CLI, integration |
| Benoy | Reading the report: sentence splitting, claim typing, "data can't answer" detection, skeptic tests, Claim Ladder wording |
| Akshaya | Web app: start screen, claims list, audit board with the Claim Ladder, evidence panel, accessibility |
| Meghana | Decisions and outputs: decision rules, `audit.json` export, Decision Record, roles, review queue, decision screen, docs |

## Setup

Needs Node.js 22+, Python 3.11–3.14 (3.13 recommended) and git. From the repository root:

```bash
python3.13 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
npm ci
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git ../oncosys-hackathon-challenge && .venv/bin/python ../oncosys-hackathon-challenge/data/tcga-brca/fetch.py
```

The third command downloads the frozen TCGA-BRCA release A into
`../oncosys-hackathon-challenge/data/tcga-brca/raw/` and checks its checksums. If `fetch.py` prints
`CHANGED` for a file, do not use that file. No TCGA data is committed to this repository.

## Run the web app

```bash
npm run dev
```

Open http://localhost:3000. The Start screen says **API connected** when the backend is up.

1. **Start:** upload a `.md` or `.txt` report (or click **Use the practice report**), enter the
   release folder (for example the absolute path to `../oncosys-hackathon-challenge/data/tcga-brca/raw`),
   click **Check the files**, then **Find claims**. Pick who you are in **Viewing as**.
2. **Claims:** untick sentences that are not claims, or tick ones the tool skipped.
3. **Audit board:** one Claim Ladder card per claim; open a card for the evidence panel.
4. **Review:** accept or override every verdict (an override needs a reason). **Continue to
   decision** unlocks when every claim is reviewed.
5. **Decision:** read the suggested decision, choose one, give a reason, **Export**, then download
   `audit.json` and `decision_record.md`.

To pre-fill the release folder, copy `apps/web/.env.example` to `apps/web/.env.local` and set
`NEXT_PUBLIC_DEFAULT_RELEASE_DIR`. If port 3000 or 8000 is busy:

```bash
PORT=3001 UVICORN_PORT=8001 API_ORIGIN=http://127.0.0.1:8001 npm run dev
```

## Run on a sealed envelope (judging)

At the Q&A, judges give an envelope number and a four-word code. From the challenge repository
(unsealing needs its own requirements, which include `cryptography`):

```bash
cd ../oncosys-hackathon-challenge
../SecondOpinion/.venv/bin/python -m pip install -r requirements.txt
../SecondOpinion/.venv/bin/python envelopes/unseal.py <number> <four words>
```

The new release is in `envelopes/opened/E<number>/release/`. Rehearse with the public practice
envelope: `envelopes/unseal.py practice orange meadow pilot lantern` →
`envelopes/opened/practice/release/`.

Then either use the web app with that folder as the release folder, or the CLI, from this repository:

```bash
.venv/bin/second-opinion --release ../oncosys-hackathon-challenge/envelopes/opened/practice/release \
  --report report.md --out audit.json
.venv/bin/python docs/challenge/format/validate.py audit.json
```

`--claims-json claims.json` skips sentence extraction and audits a given list of claims. The
validator must print `valid`.

## Limitations

These are shown in the product next to the claims they affect, not only here.

- **Subtype calls are incomplete:** only 844 of 1,101 primary tumors have an RNA-seq subtype call
  (522 have the 2012 study label). Shares are computed over samples with a call; the rest are
  reported as unknown, never dropped silently.
- **No treatment or response data:** claims about treatment, response, cause or prediction get
  `insufficient_evidence` with the data that would be needed. The tool does not guess.
- **Envelope releases have no RNA file and no manifest:** claims about RNA or "all five layers" say
  so in the audit notes instead of failing.
- **Sex and sample type:** 12 male samples, 4 with no recorded sex, and 139 normal-tissue and 7
  metastasis samples are mixed in. "Women only" excludes unknown-sex rows and reports how many.
- **Claim types covered:** counts, shares, coverage, group comparisons and agreement between labels.
  Any other kind of claim gets `insufficient_evidence` ("No check exists yet for this kind of
  claim") for a person to check.
- **The suggested decision is advice.** Every verdict needs a human review before export, and the
  Decision Record names who must sign off.

## Status (Saturday code freeze)

Working end to end through the API and CLI: release loading, checks, verdicts, robustness across
the 8 ways of counting, review, decision, `audit.json` export (passes the organizers' validator) and
the Decision Record. Report sentence extraction (`/extract`) is still being finished. Until it
lands, the CLI can take `--claims-json`.

## How it is built

```text
apps/web/          Next.js App Router, TypeScript, Tailwind CSS: the screens above
apps/api/app/      FastAPI transport and request/response models (stateless)
second_opinion/    Python audit engine and CLI, shared by the API and the CLI
tests/             Engine and API tests
docs/             Plan, challenge snapshot, demo script
```

Browser → Next.js (proxies `/api/*`) → FastAPI → `second_opinion` (pandas) → evidence, `audit.json`
and Decision Record. No database. Verdicts are deterministic code; there is no AI in the verdict
path and no API keys. See [docs/PLAN.md](docs/PLAN.md) and the
[implementation plan](docs/superpowers/plans/2026-11-12-secondopinion-claim-auditor.md).

## Checks

```bash
npm test            # Python tests; real-data tests run when SO_RELEASE_DIR is set
npm run lint
npm run typecheck
npm run build
```

Production: `npm run build`, then `npm run start:web` and `npm run start:api` as separate services,
with `API_ORIGIN` set for the frontend.

## Data credits and third-party code

The results shown here are in whole or part based upon data generated by the TCGA Research Network:
https://www.cancer.gov/tcga. Data via [UCSC Xena](https://xenabrowser.net/) (Goldman et al., *Nat
Biotechnol* 2020) and the TCGA Pan-Cancer Clinical Data Resource (Liu et al., *Cell* 2018); slide
metadata via NCI Imaging Data Commons. Details in
[docs/challenge/DATA_LICENSES.md](docs/challenge/DATA_LICENSES.md).

Libraries and their licenses: [THIRD_PARTY.md](THIRD_PARTY.md).
