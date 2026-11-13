# SecondOpinion

**Research Claim Auditor** for the OncoSys Cancer AI Lab hackathon, **Track 2: Evidence Navigator**.

> Research prototype. Not a clinical decision system. Verdicts need human review.
> No diagnosis, treatment advice or risk scores.

**Demo video:** _link to be added_ (3 minutes; script in [docs/DEMO.md](docs/DEMO.md))

## What it does

Research reports about cancer data often say things the data can't fully back up: a percentage
that is slightly wrong, a claim about treatment when the data has no treatment records, or a result
that only holds if you count one particular way. A reviewer asked "can we trust this report?" would
have to dig through files and code to find out.

SecondOpinion does that work. Give it a report and the TCGA-BRCA data release the report is about:

1. **It reads the report** and pulls out every sentence that makes a checkable factual claim.
2. **It checks each claim against the real data** with ordinary pandas code, never an AI guess, and
   gives one of three verdicts: `supported`, `contradicted` or `insufficient_evidence`.
3. **It tests how solid each verdict is** by recounting eight reasonable ways. The verdict is
   *robust* if it never changes and *fragile* if it flips, and the tool names the choice that flips it.
4. **It rewrites the claim honestly (the Claim Ladder):** over-strong wording is struck out and the
   supported version written beneath.
5. **A person reviews every verdict** (accept or override, with a reason) and records one decision:
   Proceed, Fix a problem, Narrow the question or Stop. The tool exports an `audit.json` in the
   organizers' shared findings format, plus a Decision Record.

Example, from the organizers' practice report:

> Luminal A is the largest RNA subtype, accounting for ~~about 62%~~ **49.9% (421 of 844)** of
> primary tumors with an RNA subtype call.

The report said 62%. The data shows 421 of 844 = 49.9%, and it is never 62% however you count it
(44.3% with the 2012 subtype label, 45.4% counting all samples), so the verdict is *contradicted,
robust*.

| Practice claim | Verdict | Why |
| --- | --- | --- |
| 535 of 1,101 primary tumors have all the data layers | `supported` | Recounted from the release files: 535 of 1,101 |
| Luminal A is about 62% of primary tumors with an RNA subtype call | `contradicted`, robust (8 of 8) | 49.9% (421 of 844) |
| Patients with the highest ER-alpha protein responded best to hormone therapy | `insufficient_evidence` | The data has no treatment or response records. It would need treatment and treatment-response data |

### Who it is for

**User:** a reviewer handed a report and asked, "Can we trust this?"

**The one workflow they finish:** load the report and a release folder → keep the sentences that
are claims → read the Claim Ladder for each claim → accept or override every verdict → choose one
decision → download `audit.json` and the Decision Record.

### How a verdict is decided

All verdicts come from code. There is no AI in the verdict path and no API key anywhere.

- A stated number is **supported** if it equals the computed value after rounding to the report's own
  precision. For "about / roughly / nearly" it is supported within **2 percentage points** (shares)
  or **2% of the count** (counts). Ranges ("55-65%") must contain the value.
- Otherwise it is **contradicted**, and the tool gives the correct value with its denominator.
- A direction claim ("higher in ER-positive") is supported when the sign of the difference matches.
- Claims about treatment, response, cause or prediction, or about data the release does not contain,
  are `insufficient_evidence`, with what data would be needed.
- The primary number always follows the organizers' reference definitions. The other ways of
  counting only decide the robust/fragile tag; they never change the verdict.

Claim types checked: counts, shares of a subtype, coverage ("every tumor has protein data"), group
comparisons (ER-alpha protein by ER status), and "the data can't answer this".

## Quick start

Needs **Node.js 22+**, **Python 3.11-3.14** (3.13 recommended) and **git**. From the repository root:

```bash
python3.13 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
npm ci
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git ../oncosys-hackathon-challenge && .venv/bin/python ../oncosys-hackathon-challenge/data/tcga-brca/fetch.py
```

The third command downloads the frozen TCGA-BRCA release A (about 70 MB) into
`../oncosys-hackathon-challenge/data/tcga-brca/raw/` and verifies its checksums. If `fetch.py`
prints `CHANGED` for a file, do not use that file and tell the organizers. No TCGA data is
committed to this repository.

Then start the app:

```bash
npm run dev
```

Open <http://localhost:3000>. The page says **API connected** when the backend is up.

### Try it in one click

1. On the home page, enter the **absolute path** of the release folder (for example
   `/Users/you/.../oncosys-hackathon-challenge/data/tcga-brca/raw`). To pre-fill it, copy
   `apps/web/.env.example` to `apps/web/.env.local`, set `NEXT_PUBLIC_DEFAULT_RELEASE_DIR`, and
   restart.
2. Click **Run the practice audit**. It loads the practice report, finds the three claims, audits
   them and opens the audit board.

### Audit your own report

1. **Start:** upload a `.md` or `.txt` report (or paste the text), enter the release folder, click
   **Check the files** (it lists the files and checksums, or what is missing), then **Find claims**.
2. **Claims:** untick sentences that are not claims, or tick ones the tool skipped. **Run audit**.
3. **Audit board:** one entry per claim with the verdict, how solid it is and the Claim Ladder.
   **Open evidence** shows the calculation, the "report vs data" gauge, the files and checksums, the
   code that reproduces the number, the sample IDs (CSV download), the eight ways of counting and the
   skeptic tests.
4. **Review:** accept or override each verdict (an override needs a reason and your role).
   **Continue to decision** unlocks when every claim is reviewed.
5. **Decision:** read the suggested decision and who must sign off, choose one, give a reason,
   **Export**, then download `audit.json` and `decision_record.md`.

The app keeps your work if you refresh the page. It is stored only in that browser tab
(`sessionStorage`); closing the tab clears it, and **Start over** clears it on demand.

## Run on a sealed envelope (judging)

At the Q&A, judges give an envelope number and a four-word code. From the challenge repository
(unsealing needs its own requirements, which include `cryptography`):

```bash
cd ../oncosys-hackathon-challenge
../SecondOpinion/.venv/bin/python -m pip install -r requirements.txt
../SecondOpinion/.venv/bin/python envelopes/unseal.py <number> <four words>
```

The new release is in `envelopes/opened/E<number>/release/`. It has no RNA file and no manifest, and
the tool says so instead of failing. Rehearse with the public practice envelope:

```bash
../SecondOpinion/.venv/bin/python envelopes/unseal.py practice orange meadow pilot lantern
```

Then either use the web app with `envelopes/opened/practice/release/` as the release folder, or the
command line, from this repository:

```bash
.venv/bin/second-opinion --release ../oncosys-hackathon-challenge/envelopes/opened/practice/release \
  --report docs/challenge/products/research-claim-auditor/practice_brief.md --out audit.json
.venv/bin/python docs/challenge/format/validate.py audit.json
```

On the day, the judges' report is `envelopes/opened/E<number>/claim_auditor_report.md`; use it as
`--report` (or upload it in the app). `--claims-json claims.json` skips sentence extraction and audits a given list of claims (then
`--report` is not needed). The validator must print `valid`. A full run takes well under a minute.

## Configuration

| Setting | Where | What it does |
| --- | --- | --- |
| `API_ORIGIN` | environment (default `http://127.0.0.1:8000`) | Where the Next.js server proxies `/api/*`. Restart after changing |
| `NEXT_PUBLIC_DEFAULT_RELEASE_DIR` | `apps/web/.env.local` | Release folder pre-filled in the app. Restart after changing |
| `PORT`, `UVICORN_PORT` | environment | Web and API ports for `npm run dev` |
| `SO_RELEASE_DIR` | environment | Folder of the real release; turns on the real-data tests |
| `SO_ENVELOPE_DIR` | environment | An unsealed envelope's `release/` folder; turns on the envelope rehearsal tests |
| `SO_RELEASES_ROOT` | environment, for any shared or deployed instance | If set, `/audit` only accepts release folders inside this directory. Leave it unset for local use |

If ports 3000 or 8000 are busy:

```bash
PORT=3001 UVICORN_PORT=8001 API_ORIGIN=http://127.0.0.1:8001 npm run dev
```

## Tests and checks

```bash
npm test            # Python: engine, API, export, extraction (real-data tests are skipped by default)
npm run lint
npm run typecheck
npm run build
```

To include the real-data and envelope tests (about 500 tests in total):

```bash
export SO_RELEASE_DIR="$PWD/../oncosys-hackathon-challenge/data/tcga-brca/raw"
export SO_ENVELOPE_DIR="$PWD/../oncosys-hackathon-challenge/envelopes/opened/practice/release"
npm test
```

The real-data tests reproduce the organizers' numbers: 535 of 1,101, Luminal A 421 of 844, ER-alpha
529 vs 169 samples with a difference of 3.051, and the other ways of counting.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "API unavailable" or a failed audit | The backend isn't running. Use `npm run dev`, or check `API_ORIGIN` matches the API port |
| "Release folder not found" | Use an absolute path to the folder that directly contains the five files |
| "…is missing release files: …" | The folder is not a complete release. Re-run `fetch.py` or unseal the envelope again |
| `fetch.py` prints `CHANGED` | The source changed. Don't use that file; tell the organizers |
| Port already in use | Use the `PORT` / `UVICORN_PORT` / `API_ORIGIN` command above |
| Fonts missing offline | The web fonts are downloaded the first time you run `npm run dev` or `npm run build` and cached after that. Connect once |
| `/board` shows "No audit yet" | State is per browser tab. Run an audit first, or you opened a new tab |

## Limitations

These are shown in the product next to the claims they affect, not only here.

- **Subtype calls are incomplete:** only 844 of 1,101 primary tumors have an RNA-seq subtype call
  (522 have the 2012 study label). Shares are computed over samples with a call; the rest are
  reported as unknown, never dropped silently.
- **No treatment or response data:** claims about treatment, response, cause or prediction get
  `insufficient_evidence` with the data that would be needed. The tool does not guess.
- **Envelope releases have no RNA file and no manifest:** claims about RNA are `insufficient_evidence`,
  and "all five data layers" is counted over the four layers present, with a note saying so.
- **Sex and sample type:** 13 male samples (12 of them primary tumors), 4 primary tumors with no
  recorded sex, and 139 normal-tissue and 7 metastasis samples are mixed in. "Women only" excludes
  unknown-sex rows and reports how many.
- **Claim types covered:** counts, shares, coverage and group comparisons. Any other kind of claim
  gets `insufficient_evidence` ("No check exists yet for this kind of claim") for a person to check.
- **The suggested decision is advice.** Every verdict needs a human review before export, and the
  Decision Record names who must sign off.

## How it is built

```text
apps/web/          Next.js App Router, TypeScript, Tailwind CSS: the screens above (design notes in apps/web/DESIGN.md)
apps/api/app/      FastAPI transport and request/response models (stateless)
second_opinion/    Python audit engine and CLI, shared by the API and the CLI
tests/             Engine, API and web-flow tests; tests/reports holds our own reports with known answers
docs/              Plan, challenge snapshot, demo script, stack references
```

Browser → Next.js (proxies `/api/*`) → FastAPI → `second_opinion` (pandas) → evidence, `audit.json`
and Decision Record. No database. The API keeps no session: the browser sends back what it needs.

| Engine module | Role |
| --- | --- |
| `extract.py`, `unanswerable.py` | Split the report into sentences, type each claim, parse numbers, detect "the data can't answer this" |
| `release.py` | Load a release folder (any envelope), checksums, which samples are in which data layer |
| `checks/` | One check per claim type: count, coverage, share, comparison |
| `verdict.py`, `robustness.py`, `skeptic.py` | Tolerance rules, the eight ways of counting, label-shuffle and leave-one-site-out tests |
| `ladder.py` | The Claim Ladder wording rules (fixed rules, same output every time) |
| `audit.py` | Runs a list of claims through all of the above and returns the audit result |
| `decision.py`, `export.py`, `roles.py` | Suggested decision, `audit.json` and Decision Record, role views |

| API route | Purpose |
| --- | --- |
| `POST /extract`, `POST /classify` | Report text → sentences and claims; type one ticked sentence |
| `POST /audit` | Claims + release folder → audit result |
| `POST /decision`, `POST /export` | Suggested decision; `audit.json` and Decision Record (refused until every claim is reviewed) |
| `GET /roles`, `POST /roles` | Role views |
| `GET /health`, `GET /variants` | Status; the eight ways of counting |

Interactive API docs while running: <http://localhost:3000/api/docs>. See [docs/PLAN.md](docs/PLAN.md)
and the [implementation plan](docs/superpowers/plans/2026-11-12-secondopinion-claim-auditor.md).

Production: `npm run build`, then `npm run start:web` and `npm run start:api` as separate services,
with `API_ORIGIN` set for the frontend and `SO_RELEASES_ROOT` set on the API.

## Team

| Name | Built |
| --- | --- |
| Allen | Audit engine: release loader, checks, verdict rules, robustness, `/audit`, CLI, integration |
| Benoy | Reading the report: sentence splitting, claim typing, "data can't answer" detection, skeptic tests, Claim Ladder wording |
| Akshaya | Web app: start screen, claims list, audit board with the Claim Ladder, evidence panel, accessibility |
| Meghana | Decisions and outputs: decision rules, `audit.json` export, Decision Record, roles, review queue, decision screen, docs |

## Data credits and third-party code

The results shown here are in whole or part based upon data generated by the TCGA Research Network:
https://www.cancer.gov/tcga. Data via [UCSC Xena](https://xenabrowser.net/) (Goldman et al., *Nat
Biotechnol* 2020) and the TCGA Pan-Cancer Clinical Data Resource (Liu et al., *Cell* 2018); slide
metadata via NCI Imaging Data Commons. Details in
[docs/challenge/DATA_LICENSES.md](docs/challenge/DATA_LICENSES.md).

Libraries and their licenses: [THIRD_PARTY.md](THIRD_PARTY.md). The web fonts are IBM Plex Sans,
IBM Plex Mono and Newsreader (SIL Open Font License).
