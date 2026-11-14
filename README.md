# SecondOpinion

**Research Claim Auditor** for the OncoSys Cancer AI Lab hackathon, **Track 2: Evidence Navigator**.

> Research prototype. Not a clinical decision system. Verdicts need human review.
> No diagnosis, treatment advice or risk scores.

**Demo video:** _link to be added_ (about 3 minutes, silent screen recording; shot list in [docs/DEMO.md](docs/DEMO.md))

## How to run it, step by step

These steps are for macOS or Linux, in a terminal. They take about 10 minutes the first time, most of
it downloading.

### Step 1. Check you have the tools

Run each command and check the version it prints:

```bash
node --version      # needs v22 or newer
python3 --version   # needs 3.11, 3.12, 3.13 or 3.14
git --version       # any version
```

If Node is missing or older than 22, install it from <https://nodejs.org> (or `nvm install 22`). If
Python is missing or too old, install it from <https://www.python.org/downloads/>.

### Step 2. Get the code

```bash
git clone https://github.com/all3n2601/SecondOpinion.git
cd SecondOpinion
```

Run every remaining command from inside this `SecondOpinion` folder unless the step says otherwise.

### Step 3. Install the Python part

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

This creates a `.venv` folder inside `SecondOpinion`. The app expects it there, so don't put it anywhere
else. If `python3` is older than 3.11, use the full name of a newer one instead, for example
`python3.13 -m venv .venv`.

### Step 4. Install the web part

```bash
npm ci
```

### Step 5. Download the data

The data is not stored in this repository. Get it from the organizers' repository, which goes in the
folder **next to** `SecondOpinion`, not inside it:

```bash
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git ../oncosys-hackathon-challenge
.venv/bin/python ../oncosys-hackathon-challenge/data/tcga-brca/fetch.py
```

This downloads the TCGA-BRCA release (about 70 MB) and checks every file. If it prints `CHANGED` for a
file, stop and tell the organizers.

### Step 6. Note the full path to the data folder

The app asks for this path. Print it:

```bash
(cd ../oncosys-hackathon-challenge/data/tcga-brca/raw && pwd)
```

Copy the line it prints, for example `/Users/you/oncosys-hackathon-challenge/data/tcga-brca/raw`.

To skip pasting it every time, save it once. This is optional:

```bash
cp apps/web/.env.example apps/web/.env.local
```

Then open `apps/web/.env.local` and paste the path after `NEXT_PUBLIC_DEFAULT_RELEASE_DIR=`.

### Step 7. Start the app

```bash
npm run dev
```

This starts the website and the API together. Leave this terminal open; the app stops when you close
it. When you see `Ready` from the website, go to the next step.

### Step 8. Open it in your browser

Go to **<http://localhost:3000>**. Use `localhost`, not `127.0.0.1`; on `127.0.0.1` the page will not
load properly.

Click **Start an audit**. The Start page should say **API connected**. If it says the API is unavailable,
check the terminal from step 7 for an error.

### Step 9. Run the practice audit

1. You can leave the data folder box empty: the practice run fills it in with release A (the copy
   from step 6, or a temporary download of about 70 MB if there is none).
2. Click **Run the practice audit**. It reads the organizers' practice report and checks its three
   claims.
3. Click **Open the audit board** to see each claim's verdict. Click **Open evidence** on a claim to see
   how it was checked.
4. To finish: on **Review**, accept or override each verdict. Then on **Decision**, choose a decision,
   give a reason and click **Export** to download `audit.json` and the Decision Record.

To audit your own report instead, upload it or paste its text on the Start page in step 9.

### Step 10. Stop the app

Go back to the terminal from step 7 and press **Ctrl+C**.

### Running it again later

You only need steps 7 to 9:

```bash
cd SecondOpinion
npm run dev
```

### Without the browser (optional)

To check a report from the terminal instead:

```bash
.venv/bin/second-opinion --release ../oncosys-hackathon-challenge/data/tcga-brca/raw \
  --report path/to/report.md --out audit.json
```

It prints one line per claim and writes `audit.json`.

If something goes wrong, see [Troubleshooting](#troubleshooting).

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
- One-sided bounds are checked as bounds: "more than 150", "at least 1,000", "fewer than 1%".
- Amount words become numbers: "a third", "half", "one in ten" (within 2 points); "most" / "the
  majority" is more than 50%; "nearly all" at least 90%; "a minority" under 50%.
- Rankings ("the most frequently mutated gene", "the second most common subtype", "the two most
  frequently mutated genes") must hold exactly; ties count as holding. Ratios ("about two to one",
  "twice as many") are supported within 15% ("about") or 10% of the stated ratio.
- A sentence that makes several checks ("7 metastatic and 139 normal-tissue samples", "about 77% are
  ER-positive and 66% PR-positive", "Luminal A is the largest subtype, at about 62%") is checked part by
  part and takes the verdict of its worst part; every part is listed in the finding.
- Otherwise it is **contradicted**, and the tool gives the correct value with its denominator.
- A direction claim ("higher in ER-positive") is supported when the sign of the difference matches.
- Claims about treatment, response, cause or prediction, survival differences between groups,
  measures the release does not hold (Ki-67, grade, tumor size, race, BMI, ...), or "large enough"
  judgments are `insufficient_evidence`, with what data would be needed.
- The primary number always follows the organizers' reference definitions: primary tumors by barcode,
  PAM50 from `PAM50Call_RNAseq`, receptor status from the clinical IHC columns (Positive among
  Positive + Negative), deaths from `survival.tsv` OS. The other ways of counting (including the 2012
  study's columns) only decide the robust/fragile tag; they never change the verdict.
- Close calls are flagged for the reviewer: a ranking won by under 2 points, a share near the edge of
  its tolerance, a count right at its bound.

Claim types checked: counts (samples, patients, sample types, sexes, deaths, slides), shares (PAM50
subtype, ER / PR / HER2 / hormone-receptor / triple-negative status, stage, histology, menopause, sex,
gene mutation, ERBB2-style amplification and deep deletion, deaths), data-layer coverage, also within a
subgroup ("protein data covers most triple-negative tumors"), rankings, ratios, comparisons of a share
between groups ("TP53 mutations are more common in Basal-like than Luminal A tumors"), protein
comparisons (ER-alpha by ER status), median / mean age, and "the data can't answer this".

## Quick start

Needs **Node.js 22+**, **Python 3.11-3.14** and **git**. From the repository root (if `python3 --version`
is older than 3.11, use the name of a newer one, such as `python3.13`):

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
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

Open <http://localhost:3000> and choose **Start an audit**. The Start page (`/start`) says
**API connected** when the backend is up.

### Try it in one click

1. On the Start page, leave the release folder empty or enter one. If it is empty, the practice run
   fills it in with release A: `SO_RELEASE_DIR`, else `../oncosys-hackathon-challenge/data/tcga-brca/raw`,
   else a temporary download (about 70 MB, checked against the frozen checksums, reused afterwards).
   To pre-fill the box, copy `apps/web/.env.example` to `apps/web/.env.local`, set
   `NEXT_PUBLIC_DEFAULT_RELEASE_DIR`, and restart.
2. Click **Run the practice audit**. It loads the practice report, finds the three claims and
   audits them. Each step on the right fills in with what it found (claims, verdicts, how many hold
   under every way of counting, how many sentences were rewritten). Then **Open the audit board**.

### Audit your own report

1. **Start:** upload a `.md` or `.txt` report (or paste the text), enter the release folder, click
   **Check the files** (it lists the files and checksums, or what is missing), then **Run the audit**
   to go straight through, or **Find claims only** to adjust the list first.
2. **Claims:** untick sentences that are not claims, or tick ones the tool skipped. **Run audit**.
3. **Audit board:** one entry per claim with the verdict, how solid it is and the Claim Ladder.
   **Open evidence** shows the calculation, the "report vs data" gauge, the files and checksums, the
   code that reproduces the number, the sample IDs (CSV download), the eight ways of counting and the
   skeptic tests.
4. **Review:** accept or override each verdict (an override needs a reason and your role). The page is a list
   of claims beside one open entry: it opens on the role's **Overview**, **Start reviewing** opens the first
   claim not yet reviewed, and **Save and next** moves on until every claim is done. The open claim is in the
   address (`#review-C2`), so reload and the back button keep your place.
   **Continue to decision** unlocks when every claim is reviewed. The page layout follows the role
   (see below).
5. **Decision:** read the suggested decision and who must sign off, choose one, give a reason,
   **Export**, then download `audit.json` and `decision_record.md`.

**Role views.** Each role in `second_opinion/roles.yaml` has a `view` that sets how the Review page
looks. Every view keeps Accept / Override and the "all reviewed" gate, and every number comes from
code:

| `view` | Shipped for | What it shows |
| --- | --- | --- |
| `story` | Program leader | A short written summary of what held up and what did not |
| `checklist` | Data-use reviewer | Counts by verdict, then every claim as a tick box that jumps to its row |
| `evidence` | Researcher | Each claim next to the numbers and checks behind it |
| `raw` | Data engineer | Plain tables and files, with only a terse one-line headline, caption and per-claim summary |

If a role has no `view`, it comes from `detail`: `summary` is `story`, `standard` is `checklist`,
`full` is `evidence`. The **Add a role** form has a "How it looks" choice for it. The wording in all
four views (headline, caption and one line per claim) is template text by default. If the optional AI
helper is configured (`SO_AI_API_KEY` and `SO_AI_MODEL` in `.env`, see `.env.example`; `SO_AI=off`
switches it off), `POST /ai/narrate` can reword it with named blanks that the browser fills from the
audit, so the numbers still come from code. The model sees only the view, and per claim its id, final
verdict, how solid it is (in plain words), whether a person overrode it, the report sentence and the
names of the blanks that claim has a value for. Anything that fails the checker
(`second_opinion/ai/narrate.py`) falls back to the template wording.

Every claim row reads the same way in every view: the answer (verdict, how solid it is, the claim and one
sentence), one chart, folded detail, then the Accept / Override form. Each closed fold still shows a
one-line summary. The Program leader gets no folds, only a plain "What else we found" box; the Data-use
reviewer's folds start closed; the Researcher's open on what the number rests on and where the figure
might come from; the Data engineer's open on the numbers, sample IDs and code.

Each checked share or count also gets three readings, worked out in the browser from numbers the audit
already returns (`apps/web/src/lib/insights.ts`), at each view's level of detail:

- **Every way of counting:** one dot per way the claim was recounted, on a number line beside the
  report's figure and what "about" allows.
- **What the number rests on:** counted, checked but not counted, and left out for a missing value.
  For a share with values missing, the range the true share must lie in whatever the missing values are.
- **Where the report's figure might come from** (contradicted claims): which other way of counting, or
  common slip (missing values counted one way or the other, the share outside the group, everyone
  checked instead of the group), gives the stated figure, or the nearest one when none does. A match is
  a clue, not proof.

The app keeps your work if you refresh the page. It is stored only in that browser tab
(`sessionStorage`); closing the tab clears it, and **Start over** clears it on demand.

## Run on a sealed envelope (judging)

At the Q&A, judges give an envelope number and a four-word code.

**In the app:** on the Start page, type them into **Open a sealed envelope** and press **Unseal envelope**.
It runs the organizers' own `envelopes/unseal.py`, lists the fingerprint checks it passed, loads
`claim_auditor_report.md` into the report box and sets the data folder to release A (or the envelope's
own release, if you pick it). Then press **Run the audit now**. **Rehearse with the practice envelope**
does the same with the public practice code. The challenge repository must sit next to this one (or set
`SO_CHALLENGE_DIR`), with release A fetched and its requirements installed in `.venv`.

**From the terminal**, in the challenge repository (unsealing needs its own requirements, which include
`cryptography`):

```bash
cd ../oncosys-hackathon-challenge
../SecondOpinion/.venv/bin/python -m pip install -r requirements.txt
../SecondOpinion/.venv/bin/python envelopes/unseal.py <number> <four words>
```

On Windows, set `PYTHONUTF8=1` first (`$env:PYTHONUTF8=1` in PowerShell): `unseal.py` prints check
marks and can otherwise stop with a `UnicodeEncodeError`. Rehearse with the public practice envelope:

```bash
../SecondOpinion/.venv/bin/python envelopes/unseal.py practice orange meadow pilot lantern
```

**Which release to audit against.** Our product's input in the envelope is
`envelopes/opened/E<number>/claim_auditor_report.md`. The envelope's `release/` folder is the input for
Cohort Control Tower (see the table in `envelopes/README.md`); it is a changed release with no RNA file
and no manifests. The practice brief says it describes "release A from `fetch.py`", and the product brief
lists "the TCGA-BRCA files from `fetch.py` and the manifests" as our data, so **check the judges' report
against release A**, `../oncosys-hackathon-challenge/data/tcga-brca/raw` (its manifests sit one folder
up and are read for slide counts). The tool works on an envelope's `release/` folder too, if the judges
ask for it.

From this repository (`.venv\Scripts\second-opinion.exe` and backslashes on Windows):

```bash
.venv/bin/second-opinion --release ../oncosys-hackathon-challenge/data/tcga-brca/raw \
  --report ../oncosys-hackathon-challenge/envelopes/opened/E<number>/claim_auditor_report.md --out audit.json
.venv/bin/python ../oncosys-hackathon-challenge/format/validate.py audit.json
```

It prints one line per claim (verdict, the data's value or what is missing, fragile and close-call
warnings), then writes `audit.json` only if it passes the shared-format checks. `--no-ai` runs on the
rules alone; `--quiet` skips the table. Or upload the report in the web app with the same release folder.
`--claims-json claims.json` skips sentence extraction and audits a given list of claims (then `--report`
is not needed). The validator must print `valid`. A full run takes under 10 seconds.

## Configuration

| Setting | Where | What it does |
| --- | --- | --- |
| `API_ORIGIN` | environment (default `http://127.0.0.1:8000`) | Where the Next.js server proxies `/api/*`. Restart after changing |
| `NEXT_PUBLIC_DEFAULT_RELEASE_DIR` | `apps/web/.env.local` | Release folder pre-filled in the app. Restart after changing |
| `PORT`, `UVICORN_PORT` | environment | Web and API ports for `npm run dev` |
| `SO_RELEASE_DIR` | environment | Folder of the real release; turns on the real-data tests |
| `SO_ENVELOPE_DIR` | environment | An unsealed envelope's `release/` folder; turns on the envelope rehearsal tests |
| `SO_RELEASES_ROOT` | environment, for any shared or deployed instance | If set, `/audit` only accepts release folders inside this directory. Leave it unset for local use |
| `SO_AI_API_KEY`, `SO_AI_MODEL` | `.env` (copy `.env.example`; git ignores `.env`) | Turn on the optional AI helper (claim plans and Review-page wording). With either unset it stays off. `SO_AI_BASE_URL` and `SO_AI_TIMEOUT` are optional |
| `SO_AI` | `.env` or environment | `off`, `0` or `false` switches the AI helper off even when the key and model are set |

If ports 3000 or 8000 are busy:

```bash
PORT=3001 UVICORN_PORT=8001 API_ORIGIN=http://127.0.0.1:8001 npm run dev
```

## Tests and checks

```bash
npm test            # Python: engine, API, export, extraction (real-data tests are skipped by default)
npm run test:web    # web unit tests (vitest)
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
- **Claim types covered:** see "How a verdict is decided". Any other kind of claim gets
  `insufficient_evidence` ("No check exists yet for this kind of claim") for a person to check, and the
  optional AI helper may propose a check for it. A check that fails on an unusual release never stops
  the audit: that claim alone becomes `insufficient_evidence`, marked for checking by hand.
- **Receptor status depends on the column:** HER2-positive is 22.5% (164 of 728) by the clinical IHC
  status the tool uses, but 14.9% (114 of 766) by the 2012 study's final status. Claims like this are
  marked fragile with low confidence so a reviewer looks at them.
- **Slide counts need the slide manifest**, which sits next to release A; envelope releases have none.
- **Denominators are the samples with a recorded value.** "64% of patients are postmenopausal" is
  checked as 705 of 973 with a recorded menopause status (72.5%), not 705 of all 1,101. Triple-negative
  is counted among tumours with all three receptor results recorded (116 of 722).
- **Lymph-node status is not checked:** the release has node counts but no single agreed
  "node-positive" field, so such claims get `insufficient_evidence` for a person to judge.
- **Blind-tested:** two independent agents wrote 7 reports (87 claims) with pandas answer keys before
  seeing the tool; all 7 are now in `tests/reports` (reports 6–12) and run with the test suite.
- **The suggested decision is advice.** Every verdict needs a human review before export, and the
  Decision Record names who must sign off.

## How it is built

```text
apps/web/          Next.js App Router, TypeScript, Tailwind CSS: the screens above (design notes in apps/web/DESIGN.md)
apps/api/app/      FastAPI transport and request/response models (stateless)
second_opinion/    Python audit engine and CLI, shared by the API and the CLI
tests/             Engine, API and web-flow tests; tests/reports holds our own reports with known answers
docs/              Plan, challenge snapshot, demo shot list, stack references
```

Browser → Next.js (proxies `/api/*`) → FastAPI → `second_opinion` (pandas) → evidence, `audit.json`
and Decision Record. No database. The API keeps no session: the browser sends back what it needs.

| Engine module | Role |
| --- | --- |
| `extract.py`, `unanswerable.py` | Split the report into sentences, type each claim, parse numbers, detect "the data can't answer this" |
| `release.py` | Load a release folder (any envelope), checksums, which samples are in which data layer |
| `checks/` | One check per claim type: count, coverage, share, comparison, rank, ratio, statistic; `attributes.py` reads receptor status, stage, histology, mutations, copy number and deaths the same way for every check |
| `verdict.py`, `robustness.py`, `skeptic.py` | Tolerance rules, the eight ways of counting, label-shuffle and leave-one-site-out tests |
| `ladder.py` | The Claim Ladder wording rules (fixed rules, same output every time) |
| `audit.py` | Runs a list of claims through all of the above and returns the audit result |
| `decision.py`, `export.py`, `roles.py` | Suggested decision, `audit.json` and Decision Record, role views |

| API route | Purpose |
| --- | --- |
| `POST /extract`, `POST /classify` | Report text → sentences and claims; type one ticked sentence |
| `POST /audit` | Claims + release folder → audit result |
| `POST /practice-release` | A release-A folder for the practice run (local copy or temporary download) |
| `POST /decision`, `POST /export` | Suggested decision; `audit.json` and Decision Record (refused until every claim is reviewed) |
| `GET /roles`, `POST /roles` | Role views |
| `POST /ai/narrate` | Optional AI wording for a role view, with blanks for the numbers; always answers 200 (AI text or `template`) |
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
