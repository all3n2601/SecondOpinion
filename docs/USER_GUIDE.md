# User guide

How to use the app once it is running. See [Getting started](GETTING_STARTED.md) if it is not.

## Try it in one click

1. On the Start page, leave the release folder empty or enter one. If it is empty, the practice run
   fills it in with release A: `SO_RELEASE_DIR`, else `../oncosys-hackathon-challenge/data/tcga-brca/raw`,
   else a temporary download (about 70 MB, checked against the frozen checksums, reused afterwards).
   To pre-fill the box, copy `apps/web/.env.example` to `apps/web/.env.local`, set
   `NEXT_PUBLIC_DEFAULT_RELEASE_DIR`, and restart.
2. Click **Run the practice audit**. It loads the practice report, finds the three claims and
   audits them. Each step on the right fills in with what it found (claims, verdicts, how many hold
   under every way of counting, how many sentences were rewritten). Then **Open the audit board**.

## Audit your own report

1. **Start:** upload a `.md`, `.txt` or `.pdf` report (or paste the text), enter the release folder, click
   **Check the files** (it lists the files and checksums, or what is missing), then **Run the audit**
   to go straight through, or **Find claims only** to adjust the list first. A PDF's text is read on
   the server (pypdf, `POST /report-file`, `second_opinion/report_file.py`) with page numbers, running
   headers and footers dropped and words split at line ends joined back, then shown in the report box so
   you can check it before the audit. A scanned PDF has no text to read: paste the text, or run OCR first.
2. **Claims:** untick sentences that are not claims, or tick ones the tool skipped. **Run audit**.
3. **Audit board:** one entry per claim with the verdict, how solid it is and the Claim Ladder.
   **Open evidence** shows the calculation, the "report vs data" gauge, the files and checksums, the
   code that reproduces the number, the sample IDs (CSV download), the eight ways of counting and the
   skeptic tests. Switch the board to **Report** (`/board/report`) to read the report as written with
   each claim marked where it sits by its verdict icon and word (the final verdict, after any review).
   Click a marked sentence to open its evidence; **Back to the report**, the browser's Back button and a
   reload all return you to the same sentence (its place is in the address, `#mark-C2`). **Show in
   report** on a board entry jumps the other way. Claims that can't be found in the text (the report was
   edited after the audit) are listed under the report so none is hidden.
4. **Review:** accept or override each verdict (an override needs a reason and your role). The page is a list
   of claims beside one open entry: it opens on the role's **Overview**, **Start reviewing** opens the first
   claim not yet reviewed, and **Save and next** moves on until every claim is done. The open claim is in the
   address (`#review-C2`), so reload and the back button keep your place.
   **Continue to decision** unlocks when every claim is reviewed. The page layout follows the role
   (see below).
5. **Decision:** read the suggested decision and who must sign off, choose one, give a reason,
   **Export**, then download `audit.json` and `decision_record.md`. Below the form, the report is shown under
   the chosen decision: a **preview** that changes as you pick a decision (the suggested one at first), and
   **the report after this decision** once you export. Each claim is marked with its final verdict and what
   the decision does to it. *Fix a problem* and *Narrow the question* write in the Claim Ladder's wording (struck and
   inserted) where a claim does not hold, or say it must be reworded by hand; *Stop* marks those claims *Hold*;
   *Proceed* keeps the report as written. Click a claim for its evidence; **Back to the decision**, Back and
   reload return to it (`/decision#mark-C2`). The choice and reason (exported or not) are kept in the tab with
   the audit and cleared as soon as the audit or any review changes.

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
`SO_CHALLENGE_DIR`), with release A fetched. The `cryptography` package that unsealing needs comes with
our own `requirements.txt` (Step 3), so there is nothing extra to install.

**From the terminal**, in the challenge repository, with our `.venv` (it already has `cryptography`):

```bash
cd ../oncosys-hackathon-challenge
../SecondOpinion/.venv/bin/python envelopes/unseal.py <number> <four words>
```

Rehearse with the public practice envelope:

```bash
../SecondOpinion/.venv/bin/python envelopes/unseal.py practice orange meadow pilot lantern
```

Windows (PowerShell). Set `PYTHONUTF8` first: `unseal.py` prints check marks and can otherwise stop with
a `UnicodeEncodeError` (the app's **Unseal envelope** button sets it for you):

```powershell
cd ..\oncosys-hackathon-challenge
$env:PYTHONUTF8 = 1
..\SecondOpinion\.venv\Scripts\python.exe envelopes\unseal.py practice orange meadow pilot lantern
```

**Which release to audit against.** Our product's input in the envelope is
`envelopes/opened/E<number>/claim_auditor_report.md`. The envelope's `release/` folder is the input for
Cohort Control Tower (see the table in `envelopes/README.md`); it is a changed release with no RNA file
and no manifests. The practice brief says it describes "release A from `fetch.py`", and the product brief
lists "the TCGA-BRCA files from `fetch.py` and the manifests" as our data, so **check the judges' report
against release A**, `../oncosys-hackathon-challenge/data/tcga-brca/raw` (its manifests sit one folder
up and are read for slide counts). The tool works on an envelope's `release/` folder too, if the judges
ask for it.

From this repository:

```bash
.venv/bin/second-opinion --release ../oncosys-hackathon-challenge/data/tcga-brca/raw \
  --report ../oncosys-hackathon-challenge/envelopes/opened/E<number>/claim_auditor_report.md --out audit.json
.venv/bin/python ../oncosys-hackathon-challenge/format/validate.py audit.json
```

Windows (PowerShell):

```powershell
.venv\Scripts\second-opinion.exe --release ..\oncosys-hackathon-challenge\data\tcga-brca\raw `
  --report ..\oncosys-hackathon-challenge\envelopes\opened\E<number>\claim_auditor_report.md --out audit.json
.venv\Scripts\python.exe ..\oncosys-hackathon-challenge\format\validate.py audit.json
```

It prints one line per claim (verdict, the data's value or what is missing, fragile and close-call
warnings), then writes `audit.json` only if it passes the shared-format checks. `--no-ai` runs on the
rules alone; `--no-split` keeps the AI helper but does not split sentences the rules only half read
(they stay whole and come back "can't check"; the web app's Start page has the same "AI split" switch);
`--quiet` skips the table. Or upload the report in the web app with the same release folder.
`--claims-json claims.json` skips sentence extraction and audits a given list of claims (then `--report`
is not needed). The validator must print `valid`. A full run takes under 10 seconds.
