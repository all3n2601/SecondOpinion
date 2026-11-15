# Development

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

Windows (PowerShell; the settings last until you close that window):

```powershell
$env:PORT = 3001; $env:UVICORN_PORT = 8001; $env:API_ORIGIN = "http://127.0.0.1:8001"; npm run dev
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

Windows (PowerShell):

```powershell
$env:SO_RELEASE_DIR = (Resolve-Path ..\oncosys-hackathon-challenge\data\tcga-brca\raw).Path
$env:SO_ENVELOPE_DIR = (Resolve-Path ..\oncosys-hackathon-challenge\envelopes\opened\practice\release).Path
npm test
```

`npm test` and `npm run dev` run Python through `scripts/py.mjs`, which picks `.venv/bin/python` or
`.venv\Scripts\python.exe`, so the same npm commands work on every system. The PDF fixtures in
`tests/pdf/` are printed from Markdown reports by `tests/pdf/make_fixtures.py` (needs Chrome or Edge).

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
| "No Python virtual environment found" | Create `.venv` in the repository root (step 3) |
| "This PDF has no text to read" | The PDF is a scanned image. Paste the text, or run the PDF through OCR first |
| PDF text looks off in the report box | PDF text has no paragraph marks, so a table or a two-column layout can come out in an odd order. Fix it in the box, or paste the text |
| Windows: `npm.ps1 cannot be loaded because running scripts is disabled` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or type `npm.cmd` instead of `npm` |
| Windows: `npm ci` fails with `EPERM` or "file in use" | A running `npm run dev` (or an editor) holds a file in `node_modules`. Stop it with Ctrl+C and run `npm ci` again |
| Windows: `py` or `python` is not found | Install Python from python.org (tick "Add python.exe to PATH") or with winget, then open a new PowerShell window |
| Windows: `UnicodeEncodeError` from `unseal.py` | Run `$env:PYTHONUTF8 = 1` in that PowerShell window first |


## How it is built

```text
apps/web/          Next.js App Router, TypeScript, Tailwind CSS: the screens above (design notes in apps/web/DESIGN.md)
apps/api/app/      FastAPI transport and request/response models (stateless)
second_opinion/    Python audit engine and CLI, shared by the API and the CLI
tests/             Engine, API and web-flow tests; tests/reports holds our own reports with known answers
scripts/py.mjs     Runs the .venv Python for the npm scripts on macOS, Linux and Windows
docs/              Plan, challenge snapshot, stack references
```

Browser → Next.js (proxies `/api/*`) → FastAPI → `second_opinion` (pandas) → evidence, `audit.json`
and Decision Record. No database. The API keeps no session: the browser sends back what it needs.

| Engine module | Role |
| --- | --- |
| `report_file.py` | Read an uploaded report file: Markdown and text decoded, PDF text pulled out and cleaned |
| `extract.py`, `unanswerable.py` | Split the report into sentences, type each claim, parse numbers, detect "the data can't answer this" |
| `release.py` | Load a release folder (any envelope), checksums, which samples are in which data layer |
| `checks/` | One check per claim type: count, coverage, share, comparison, rank, ratio, statistic; `attributes.py` reads receptor status, stage, histology, mutations, copy number and deaths the same way for every check |
| `verdict.py`, `robustness.py`, `skeptic.py` | Tolerance rules, the eight ways of counting, label-shuffle and leave-one-site-out tests |
| `ladder.py` | The Claim Ladder wording rules (fixed rules, same output every time) |
| `audit.py` | Runs a list of claims through all of the above and returns the audit result |
| `decision.py`, `export.py`, `roles.py` | Suggested decision, `audit.json` and Decision Record, role views |

| API route | Purpose |
| --- | --- |
| `POST /report-file` | A report file (Markdown, text or PDF) → its text, for the report box |
| `POST /extract`, `POST /classify` | Report text → sentences and claims (`split: false` skips the AI split); type one ticked sentence |
| `POST /audit` | Claims + release folder → audit result |
| `POST /practice-release` | A release-A folder for the practice run (local copy or temporary download) |
| `POST /decision`, `POST /export` | Suggested decision; `audit.json` and Decision Record (refused until every claim is reviewed) |
| `GET /roles`, `POST /roles` | Role views |
| `POST /ai/narrate` | Optional AI wording for a role view, with blanks for the numbers; always answers 200 (AI text or `template`) |
| `GET /health`, `GET /variants` | Status; the eight ways of counting |

Interactive API docs while running: <http://localhost:3000/api/docs>. See [docs/PLAN.md](PLAN.md)
and the [implementation plan](superpowers/plans/2026-11-12-secondopinion-claim-auditor.md).

Production: `npm run build`, then `npm run start:web` and `npm run start:api` as separate services,
with `API_ORIGIN` set for the frontend and `SO_RELEASES_ROOT` set on the API.
