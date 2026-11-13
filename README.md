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

Monorepo scaffold with a Next.js interface, a FastAPI health endpoint and counting-variant
endpoint, and the shared Python audit engine. Claim extraction, verdict calculations,
report uploads, and audit export are not implemented yet.

See [docs/PLAN.md](docs/PLAN.md) for scope and build order, and
[docs/Idea_Analysis_Report.pdf](docs/Idea_Analysis_Report.pdf) for why this idea was chosen.

Documentation: [local docs index](docs/README.md), including the official challenge specification,
rules, dataset guide, findings schema, and validator.

## Structure

```text
apps/web/          Next.js App Router, TypeScript, Tailwind CSS
apps/api/app/      FastAPI transport and Pydantic response models
second_opinion/    Shared Python engine and CLI
tests/            Python engine and API tests
docs/             Scope and project notes
```

The frontend proxies `/api/*` to FastAPI. Audit logic belongs in `second_opinion/`, so the
API and CLI can share it. No database or monorepo build framework is required.
shadcn/ui components can be added as the Claim Ladder is built.

## Setup

Use Node.js 22+ and Python 3.11–3.14 (Python 3.13 recommended).
Run all commands from the repository root:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
```

`pyproject.toml` defines the Python package and dependencies; `requirements.txt` installs it
with development dependencies. `package-lock.json` locks the npm workspace dependencies.

Optional frontend configuration: copy `apps/web/.env.example` to `apps/web/.env.local`.
The default API origin is `http://127.0.0.1:8000`. The proxy origin is server-only and is
read at startup/build time; rebuild the frontend when changing it for production.

## Run

```bash
npm run dev
```

- Frontend: http://localhost:3000
- API documentation through the frontend proxy: http://localhost:3000/api/docs
- Direct API health: http://127.0.0.1:8000/health
- Counting variants from the shared engine: http://localhost:3000/api/variants

`npm run dev:web` and `npm run dev:api` start services separately. Stop with Ctrl+C.
If ports 3000 or 8000 are occupied, use:

```bash
PORT=3001 UVICORN_PORT=8001 API_ORIGIN=http://127.0.0.1:8001 npm run dev
```

The workspace pins a patched minimatch for the TypeScript ESLint dependency tree.
For production, run `npm run build`, then start `npm run start:web` and
`npm run start:api` as separate services. Deployments must configure the frontend's
`API_ORIGIN` to reach the backend. FastAPI's `/api` root path matches the frontend proxy.

## Data and CLI

The web scaffold does not require TCGA files. To prepare the audit engine's data:

```bash
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git ../oncosys-hackathon-challenge
python ../oncosys-hackathon-challenge/data/tcga-brca/fetch.py
```

The release folder contains the five TCGA-BRCA files. The CLI currently loads those files
and raises `NotImplementedError`; once the engine is implemented, its intended usage is:

```bash
.venv/bin/python -m second_opinion.cli --release <release-folder> --report <report.md> --out audit.json
python ../oncosys-hackathon-challenge/format/validate.py audit.json
```

## Checks

```bash
npm run lint
npm run typecheck
npm run build
npm test
```

## Third-party

TCGA data: UCSC Xena and NCI Imaging Data Commons, see the challenge repo's `DATA_LICENSES.md`.
No raw TCGA files are committed here.
