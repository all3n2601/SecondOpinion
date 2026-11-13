# SecondOpinion Implementation Plan

**Goal:** Take a research report and a TCGA-BRCA release folder, and for every factual sentence say whether the data supports it, how solid that answer is, and the strongest honest way to word it, then record one reviewed decision and export a valid `audit.json`.

**Architecture:** Browser (Next.js) → `/api/*` proxy → FastAPI (thin transport) → `second_opinion/` Python engine (pandas, deterministic code sets every verdict). The API is **stateless**: the browser holds the working state and sends it back on each call. The CLI and the API call the same engine functions.

**Tech Stack:** Next.js 16 App Router + TypeScript + Tailwind v4 (no component library), FastAPI + Pydantic v2, pandas 3, jsonschema, PyYAML, pytest.

**Spec:** [`docs/challenge/products/research-claim-auditor.md`](../../challenge/products/research-claim-auditor.md), [`docs/challenge/format/README.md`](../../challenge/format/README.md), [`docs/PLAN.md`](../../PLAN.md), the idea guide [`docs/Evidentia_Idea_and_Build_Guide.pdf`](../../Evidentia_Idea_and_Build_Guide.pdf) ("Evidentia" is its old working name; this project is **SecondOpinion**), and [`docs/STACK_REFERENCES.md`](../../STACK_REFERENCES.md).

## Global Constraints

- Code freeze **Saturday Nov 14, 2:15 PM ET**. Demos 2:30–4:00 PM. A finished workflow beats an ambitious one that doesn't run.
- Verdicts come **only from code**. An LLM, if used at all, may only suggest which sentences are claims, behind a flag, never required. **No API keys in the repo.** Everything must run with no AI.
- Verdict values are exactly `supported`, `contradicted`, `insufficient_evidence`. Decisions are exactly `Proceed`, `Fix a problem`, `Narrow the question`, `Stop`.
- Judged data is the frozen TCGA-BRCA release (checksums in `sources.csv`). **No raw TCGA files committed.** `envelopes/opened/` stays git-ignored.
- Always show counts with their denominator (`421 of 844`), never a bare percentage. Missing values are shown as `unknown`, never dropped silently or treated as zero.
- No diagnosis, treatment advice, risk scores or clinical claims anywhere, including the README. Every screen carries: *"Research prototype. Not a clinical decision system. Verdicts need human review."*
- Tolerance rules (verbatim from the idea guide §4.2): a stated number is **supported** if it equals ours after rounding to the report's own precision; for "about / roughly / nearly / ~" it is supported within **2 percentage points** (shares) or **2% of the count** (counts). Otherwise **contradicted**, with `correct_value` such as `49.9% (421 of 844)`.
- The primary number always uses the organizers' definitions in `reference_analyses.py` (A1: ER-alpha by clinical ER status, 529 positive / 169 negative / difference 3.051; A2: PAM50 RNA-seq subtype share, 844 subtyped, LumA 421). Other ways of counting only set the solid/fragile tag, they never change the verdict.
- `audit.json` follows format v0.2 and must pass `docs/challenge/format/validate.py`.
- Setup stays at three commands. Python 3.11–3.14, Node ≥ 22.
- Tests that need real TCGA files read the folder from the env var `SO_RELEASE_DIR` and are skipped when it is unset. All other tests use the tiny generated release from `tests/helpers.py`.

## Review Focus

Inputs a real reviewer will hit that the spec doesn't spell out, most likely first. Each has a test in the task that owns the code.

1. **Release without RNA file or manifest** (every sealed envelope is like this) and a claim about "all five layers" or RNA. The tool must say so, not crash. → Task A2, A3.
2. **Approximate and range claims** ("about 62%", "nearly 40%", "55–65%", "1,101", "62 %"). → Task B2, A4.
3. **Subtype spelling traps**: `LumA` vs `Luminal A` vs `Luminal-A`, `Basal` vs `Basal-like`, `Her2` vs `HER2-enriched`. → Task B2, A3.
4. **Missing and unusual rows**: 12 male samples, 4 samples with no gender, 139 normal-tissue and 7 metastasis samples mixed in. Women-only must exclude unknown-sex rows and report how many. → Task A3.
5. **Bad input**: empty report, report with no checkable claims, release path that doesn't exist or lacks files. Clear message, no stack trace. → Task B4, A5, A8.

---

## How we work

### Who owns what

| Person | Owns | Why this split |
| --- | --- | --- |
| **Allen** | The audit engine core: contracts, release loader, checks, verdict rules, robustness, pipeline, `/audit`, integration and final run | Everything else plugs into it, so the contracts are written first |
| **Benoy** | Reading the report: sentence splitting, claim typing, "data can't answer" detection, skeptic tests, Claim Ladder wording, our own test reports | Self-contained text processing with clear inputs and outputs |
| **Akshaya** | The web app's main path: shell, upload, claims list, Claim Ladder board, evidence panel, accessibility | One coherent UI slice, built against a fixture so it never waits on the engine |
| **Meghana** | Decisions and outputs: decision rules, `audit.json` + Decision Record export, roles, review queue, decision screen, README / licenses / demo video | One slice from rules to screen to file |

### File ownership (so we never edit the same file)

Only the owner edits these. Need a change in someone else's file? Message them.

| Owner | Files |
| --- | --- |
| Allen | `second_opinion/model.py`, `release.py`, `checks/`, `verdict.py`, `robustness.py`, `audit.py`, `cli.py`, `apps/api/app/main.py`, `apps/api/app/routes/audit.py`, `tests/helpers.py`, `tests/conftest.py`, `apps/web/src/lib/types.ts` |
| Benoy | `second_opinion/extract.py`, `unanswerable.py`, `skeptic.py`, `ladder.py`, `apps/api/app/routes/extract.py`, `tests/reports/` and the matching tests |
| Akshaya | `apps/web/src/app/` pages for `/`, `/claims`, `/board`, `apps/web/src/components/` (all except the ones listed under Meghana), `apps/web/src/lib/api.ts`, `audit-context.tsx` |
| Meghana | `second_opinion/decision.py`, `export.py`, `roles.py`, `roles.yaml`, `apps/api/app/routes/export.py`, `routes/roles.py`, pages for `/review`, `/decision`, components `RolePicker`, `RoleSummary`, `ReviewForm`, `DecisionPanel`, `README.md` setup/demo sections, `THIRD_PARTY.md`, `LICENSE` |

### Git rules

- Branch per task: `feat/<name>-<task-id>` (for example `feat/benoy-b2-claim-typing`). Small pull requests, one task each.
- Run `npm test` (Python) and, for web changes, `npm run lint && npm run typecheck` before you push.
- Allen reviews and merges. Merge `main` into your branch before you open the PR.
- Commit messages: `feat: …`, `fix: …`, `test: …`, `docs: …`.
- Never commit data files, `.env*`, keys or `envelopes/opened/`.

### Setup (everyone, 15 minutes, once)

```bash
git clone <our repo> && cd SecondOpinion
python3.13 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
npm ci
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git ../oncosys-hackathon-challenge
python ../oncosys-hackathon-challenge/data/tcga-brca/fetch.py
export SO_RELEASE_DIR="$PWD/../oncosys-hackathon-challenge/data/tcga-brca/raw"
```

Check it worked: `npm test` passes, and `npm run dev` shows "API connected" at http://localhost:3000. If the fetch prints `CHANGED`, tell the group and don't use that file.

Read before your first task: this plan's "The shape of the system" section, then your own section. Web work: also read `apps/web/AGENTS.md` and the relevant files under `node_modules/next/dist/docs/`.

### How each task is written

Every task says what it is in plain words, which files you touch, the exact names other people rely on (**Interfaces**), and then small steps: write the test, watch it fail, write the code, watch it pass, commit. If a step says the test must fail first, run it and look at the failure; that proves the test is real. A task is **done** only when its "Done when" line is true.

### Words we use

| Word | Meaning |
| --- | --- |
| **Release** | The folder of five data files (`clinical.tsv`, `survival.tsv`, `mutation_gene_level.tsv.gz`, `copy_number_gistic.tsv.gz`, `protein_rppa.tsv.gz`). Judges' envelope releases have **no RNA file and no manifest**. |
| **Claim** | One sentence of the report that states something checkable, with a type. |
| **Fact** | What the data actually shows for a claim: value, numerator/denominator, sample IDs, files, code. |
| **Variant** | One of the 8 "count it differently" combinations (subtype label × everyone/women only × primary only/all samples). |
| **Solidity** | `holds_under_every_variant` ("robust"), `holds_under_some_variants` ("fragile"), or `not_applicable`. |
| **Claim Ladder** | The claim's sentence with over-strong words crossed out and the honest version beneath it. |
| **Review** | A person's accept/override of one verdict, with a reason and role. Both verdicts are kept. |

---

## The shape of the system

```text
report.md ──► extract.py ──► Claim[] ──► (user ticks) ──► audit.py ──► AuditResult ──► (user reviews) ──► export.py ──► audit.json + decision_record.md
                 │                                          │
           unanswerable.py                       checks/* → verdict.py → robustness.py → skeptic.py → ladder.py
```

### Practice report: the three results everything must reproduce

| Claim | Verdict | Solidity | Correct value / missing |
| --- | --- | --- | --- |
| 535 of 1,101 primary tumors have all five data layers | `supported` | n/a | `535 of 1,101` |
| Luminal A is about 62% of primary tumors with an RNA subtype call | `contradicted` | holds under all 8 variants | `49.9% (421 of 844)` |
| Highest ER-alpha protein responded best to hormone therapy | `insufficient_evidence` | `not_applicable` | needs treatment and response data |

Other share values (all contradict 62%, so the claim is robust): women only 416 of 833 = 49.9%; 2012 label 231 of 522 = 44.3%; all samples 434 of 956 = 45.4%.

### Contracts (Allen writes these first in Task A1; everyone builds on them)

All in `second_opinion/model.py` as plain dataclasses, used directly as FastAPI request/response models. `apps/web/src/lib/types.ts` mirrors them field for field (snake_case, same names).

```python
class ClaimType(str, Enum):  # COUNT SHARE COMPARISON AGREEMENT COVERAGE NOT_ANSWERABLE UNMAPPED

@dataclass
class ClaimParams:
    stated_value: float | None = None   # 62.0 for "62%", 535 for "535"; range: the lower end
    stated_high: float | None = None    # upper end of a range like "55–65%"
    stated_total: float | None = None   # 1101 in "535 of 1,101"
    unit: str | None = None             # "percent" | "count" | "all" (for "every ...")
    decimals: int | None = None         # digits after the point as written: "49.9%" -> 1
    approximate: bool = False           # about / roughly / nearly / ~ / around
    subject: str | None = None          # "primary_tumors" | "all_five_layers" | "samples" | "patients" | "has_protein" | "has_survival" | "has_mutation" | "has_copy_number" | "has_rna"
    subtype: str | None = None          # normalised, e.g. "Luminal A"
    direction: str | None = None        # "higher" | "lower"
    measure: str | None = None          # e.g. "ER-alpha protein"
    group_a: str | None = None          # e.g. "ER-positive"
    group_b: str | None = None          # e.g. "ER-negative"

@dataclass
class Claim:
    id: str                             # "C1", "C2", ... in report order
    text: str                           # the sentence exactly as written
    sentence_index: int
    type: ClaimType
    params: ClaimParams = field(default_factory=ClaimParams)
    needed_data: str | None = None      # NOT_ANSWERABLE only: "treatment and response data"
    clinical_terms: list[str] = field(default_factory=list)  # flagged words: "responded", "hormone therapy"

@dataclass
class SentenceInfo:  index: int; text: str; claim_id: str | None
@dataclass
class ExtractResult: sentences: list[SentenceInfo]; claims: list[Claim]

@dataclass
class Fact:
    label: str                          # plain words: "primary tumors with a PAM50 RNA-seq call that are Luminal A"
    value: float | None                 # percent (shares), count (counts), mean difference (comparisons)
    numerator: int | None
    denominator: int | None
    sample_ids: list[str]
    files: list[str]                    # release file names used
    code: str                           # copy-pasteable pandas snippet that reproduces the value
    unknown_count: int = 0              # rows left out because the value was missing
    extra: dict[str, float | int | str] = field(default_factory=dict)  # comparisons: n_a, n_b, mean_a, mean_b

@dataclass
class VariantResult:  variant_id: str; fact: Fact | None; verdict: Verdict | None   # replaces the old VariantResult
@dataclass
class SkepticResult:  shuffle_p: float | None; n_sites: int; site_flips: list[str]
@dataclass
class LadderSegment:  text: str; struck: bool = False; inserted: bool = False
@dataclass
class Review:         decision: str; final_verdict: Verdict; reason: str; reviewer_role: str   # decision: "accept" | "override"

@dataclass
class ClaimResult:                      # replaces the old ClaimCheck
    claim: Claim
    verdict: Verdict
    solidity: Solidity
    fact: Fact | None
    correct_value: str | None           # contradicted only
    missing_evidence: str | None        # insufficient_evidence only
    variants: list[VariantResult]
    flips_on: list[str]                 # e.g. ["subtype_source=study_2012_label"]
    skeptic: SkepticResult | None
    ladder: list[LadderSegment]
    limitation: str | None
    review: Review | None = None

@dataclass
class ReleaseInfo:  name: str; files: list[dict[str, str]]    # [{"file": ..., "sha256": ...}]
@dataclass
class AuditResult:  release: ReleaseInfo; claims: list[ClaimResult]; notes: list[str]   # notes: "No RNA file in this release."
@dataclass
class DecisionSuggestion:  decision: Decision; rule: str; reasons: list[str]; sign_off: list[str]; would_change: list[str]
@dataclass
class DecisionChoice:      choice: Decision; reason: str; reviewer_role: str
```

### API (stateless; browser path is `/api/...`, FastAPI route is without `/api`)

| Method + route | Body → response | Owner |
| --- | --- | --- |
| `POST /extract` | `{report_text}` → `ExtractResult` | Benoy |
| `POST /classify` | `{text, sentence_index}` → `Claim` (ticking a sentence we skipped) | Benoy |
| `POST /audit` | `{release_dir, claims: Claim[]}` → `AuditResult` | Allen |
| `POST /decision` | `{audit}` → `DecisionSuggestion` (uses a claim's `review.final_verdict` when present) | Meghana |
| `POST /export` | `{audit, decision: DecisionChoice}` → `{audit_json, decision_record_md}`; **422 if any claim has no review** | Meghana |
| `GET /roles`, `POST /roles` | list roles / add one | Meghana |

Each route group lives in its own file under `apps/api/app/routes/` and is mounted once in `main.py` by Allen (Task A1), so nobody edits `main.py` again.

### Order of work and who waits for whom

```text
Thu night   A1 contracts + stubs ─┬─► B1, B3 (Benoy)   K1 (Akshaya)   M1 (Meghana)      A2 → A3 → A4: Checkpoint 1
Fri         A5 pipeline, A6, A7   │   B2, B4, B5, B6   K2 → K3 → K4 → K5   M2, M3, then M4 → M5 → M6 (after K1)
Sat 10:00   A8 integration · everyone: polish, rehearse the envelope, README, video · freeze 2:15 PM
```

Until Allen's A1 lands (about an hour), everyone does the setup and reads. After A1, **nobody waits on the engine**: the API stubs return `tests/fixtures/practice_audit_result.json`, so the web app, export and decision code can all be built and tested against the practice result.

---

# Allen: engine core, integration

First hour: setup, then Task A1 straight away, because everyone else is waiting for it.

### Task A1: Contracts, fixtures, API skeleton (Thu night, ~60 min)

Plain words: write down the shapes everyone shares, a hand-made "expected answer" for the practice report, and stub endpoints that return it. After this, the others can build in parallel.

**Files:**
- Modify: `second_opinion/model.py` (add everything in "Contracts"; remove the old `VariantResult` and `ClaimCheck`, nothing else uses them)
- Create: `tests/fixtures/practice_audit_result.json` (an `AuditResult` for the three practice claims, using the values in the table above, 8 variants for claim C2 with the numbers listed under it, `solidity` per the table)
- Create: `tests/helpers.py` with `make_mini_release(dest: Path) -> Path` and `MINI: dict[str, int]` (see Task A2), `tests/conftest.py` with fixtures `release_dir` (skips unless `SO_RELEASE_DIR` set) and `mini_release` (tmp_path release); register the `realdata` marker under `[tool.pytest.ini_options]` in `pyproject.toml` (`markers = ["realdata: needs the real TCGA release in SO_RELEASE_DIR"]`)
- Create: `apps/api/app/routes/__init__.py`, `extract.py`, `audit.py`, `export.py`, `roles.py` (each an `APIRouter` whose endpoints return the fixture or an empty-but-valid object)
- Modify: `apps/api/app/main.py` (mount the four routers once)
- Create: `apps/web/src/lib/types.ts` (TypeScript mirror of the contracts)
- Test: `tests/test_contracts.py`

**Interfaces:**
- Produces: every name in "Contracts" and "API". `AuditResult` must round-trip through JSON: `AuditResult` → `dataclasses.asdict` → JSON → back.

- [ ] **Step 1: Write the failing tests** in `tests/test_contracts.py`:

```python
def test_fixture_is_a_valid_audit_result():
    data = json.loads(Path("tests/fixtures/practice_audit_result.json").read_text())
    audit = TypeAdapter(AuditResult).validate_python(data)
    assert [c.verdict for c in audit.claims] == [
        Verdict.SUPPORTED, Verdict.CONTRADICTED, Verdict.INSUFFICIENT_EVIDENCE]
    assert audit.claims[1].correct_value == "49.9% (421 of 844)"
    assert len(audit.claims[1].variants) == 8

def test_stub_endpoints_exist():
    for path in ("/extract", "/audit", "/decision", "/export", "/roles"):
        assert any(r.path == path for r in app.routes)
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_contracts.py -v`. Expected: FAIL (names missing).
- [ ] **Step 3: Implement** the dataclasses, the fixture, the routers and `types.ts`. In `types.ts`, `Verdict` and `Decision` are string-literal unions with exactly the Python values.
- [ ] **Step 4: Run** the same command plus `npm run typecheck`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: shared contracts, practice fixture, API skeleton`. **Tell the others: "A1 is on main."**

**Done when:** `GET /api/docs` lists all routes and the others have pulled `main`.

### Task A2: Release loader (Thu night, ~45 min)

Plain words: open a release folder, check the files, and answer "which samples are in which layer?". Must work on a folder with **no RNA file and no manifest**.

**Files:**
- Modify: `second_opinion/release.py` (replace the dict-returning `load_release`)
- Modify: `tests/helpers.py` (fill in `make_mini_release`)
- Test: `tests/test_release.py`

**Interfaces:**
- Produces:

```python
@dataclass
class Release:
    folder: Path
    clinical: pd.DataFrame            # as read from clinical.tsv
    survival_ids: set[str]
    mutation_ids: set[str]            # column headers of the mutation file
    copy_number_ids: set[str]
    protein_ids: set[str]
    protein: pd.DataFrame             # protein_rppa, index = protein name, columns = sample ids
    rna_ids: set[str] | None          # None when the folder has no rna_hiseq.tsv.gz
    checksums: dict[str, str]         # file name -> sha256 of every file present
    def primary_ids(self) -> list[str]: ...        # clinical sampleID where chars [13:15] == "01"
    def layer_ids(self, layer: str) -> set[str]: ...  # layer in {"survival","mutation","copy_number","protein","rna"}; raises KeyError("rna") text "no RNA file in this release" if rna_ids is None
def load_release(folder: str | Path) -> Release: ...
```
- `FileNotFoundError` message lists the missing files (keep the current wording). Keep `RELEASE_FILES`.

`make_mini_release`: writes the five files with a handful of samples and **fixed, documented counts** in `MINI` (for example `MINI = {"samples": 12, "primary": 8, "male_primary": 2, "unknown_sex_primary": 1, "rna_subtyped_primary": 6, "luma_rna_primary": 3, "all_layers_primary": 4}`), including `LumA`-style RNA labels and `Luminal A`-style 2012 labels, normal (`-11`) and metastasis (`-06`) samples, and no RNA file.

- [ ] **Step 1: Write failing tests**:

```python
def test_mini_release_layers(mini_release):
    r = load_release(mini_release)
    assert len(r.primary_ids()) == MINI["primary"]
    assert r.rna_ids is None

def test_missing_rna_is_a_clear_error(mini_release):
    with pytest.raises(KeyError, match="no RNA file"):
        load_release(mini_release).layer_ids("rna")

def test_missing_files_listed(tmp_path):
    with pytest.raises(FileNotFoundError, match="clinical.tsv"):
        load_release(tmp_path)

@pytest.mark.realdata
def test_real_release_headline_numbers(release_dir):
    r = load_release(release_dir)
    assert len(r.primary_ids()) == 1101
    full = set(r.primary_ids()) & r.survival_ids & r.mutation_ids & r.copy_number_ids & r.protein_ids
    assert len(full) == 535
```
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_release.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `Release` and `load_release`. Read mutation/copy-number files with `nrows=0` to get sample IDs from the header (they are large); read protein fully (131 rows). Hash with 1 MB chunks.
- [ ] **Step 4: Run** the tests (with `SO_RELEASE_DIR` set so the real-data test runs). Expected: PASS.
- [ ] **Step 5: Commit** `feat: release loader with layer sample sets`.

**Done when:** loading the real release takes under 5 seconds and the real-data test passes.

### Task A3: Count, coverage and share checks (Thu night, ~90 min) → Checkpoint 1

Plain words: three small functions that turn a claim into a Fact using the organizers' definitions. This is the heart of the project.

**Files:**
- Create: `second_opinion/checks/__init__.py` (registry), `population.py`, `count.py`, `coverage.py`, `share.py`
- Modify: `second_opinion/variants.py` only to add the default variant constant `PRIMARY_VARIANT = Variant("rna_call", "everyone", "primary_tumors")`
- Test: `tests/test_checks_basic.py`

**Interfaces:**
- Consumes: `Release`, `Claim`, `Variant`, `normalise_subtype`.
- Produces:

```python
# checks/population.py
def population(release: Release, variant: Variant) -> pd.DataFrame
    # clinical rows after: sample_scope ("primary_tumors" -> sampleID[13:15]=="01"; "all_samples" -> all),
    # sex_filter ("women_only" -> gender == "FEMALE"; rows with missing gender are excluded and counted)
def subtype_column(variant: Variant) -> str   # "PAM50Call_RNAseq" | "PAM50_mRNA_nature2012"

# checks/__init__.py
class CannotCheck(Exception): ...        # message says what is missing, e.g. "no RNA file in this release"
Check = Callable[[Claim, Release, Variant], Fact]
CHECKS: dict[ClaimType, Check]

# count.py   check_count   : subject "primary_tumors" / "samples" / "patients" / "all_five_layers"
# coverage.py check_coverage: "every primary tumor has <layer>" -> Fact with numerator = have, denominator = primary, sample_ids = the MISSING ones
# share.py   check_share   : subtype share among samples that have a subtype call; Fact.unknown_count = samples with no call
```

Rules: "all five layers" counts survival ∩ mutation ∩ copy number ∩ protein, plus RNA when `rna_ids` is not None. When there is no RNA file, add a note in `Fact.extra["note"] = "no RNA file in this release; counted four layers"` so the verdict step and the UI can show it. A claim that is *about* RNA expression when `rna_ids is None` raises `CannotCheck("no RNA file in this release")`. Every `Fact.code` must be a snippet someone can paste into a notebook after `r = load_release(...)`.

- [ ] **Step 1: Write failing tests**:

```python
@pytest.mark.realdata
def test_practice_count(release_dir):
    claim = Claim("C1", "...", 0, ClaimType.COUNT, ClaimParams(535, None, 1101, "count", subject="all_five_layers"))
    f = CHECKS[ClaimType.COUNT](claim, load_release(release_dir), PRIMARY_VARIANT)
    assert (f.numerator, f.denominator) == (535, 1101)

@pytest.mark.realdata
@pytest.mark.parametrize("variant_id, num, den", [
    ("rna_call|everyone|primary_tumors", 421, 844),
    ("rna_call|women_only|primary_tumors", 416, 833),
    ("study_2012_label|everyone|primary_tumors", 231, 522),
    ("rna_call|everyone|all_samples", 434, 956),
])
def test_luminal_a_share_by_variant(release_dir, variant_id, num, den):
    ...  # build the Variant from variant_id, run check_share, assert (numerator, denominator) and round(value, 1)

def test_share_ignores_spelling(mini_release):   # LumA vs Luminal A give the same subtype
def test_women_only_counts_unknown_sex(mini_release):  # Fact.unknown_count or extra["excluded_unknown_sex"] == MINI["unknown_sex_primary"]
def test_rna_claim_without_rna_file_cannot_be_checked(mini_release):  # CannotCheck
```
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_checks_basic.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the modules. `population()` is shared by all checks, so the filters live in exactly one place.
- [ ] **Step 4: Run** with `SO_RELEASE_DIR` set. Expected: PASS.
- [ ] **Step 5: Commit** `feat: count, coverage and share checks`.

**Done when:** the four real-data numbers above pass. **Checkpoint 1 (Thursday):** after A4 below, post in Discord: "Practice report: 535 supported, 62% contradicted → 49.9% (421 of 844), hormone therapy insufficient evidence."

### Task A4: Verdict rules (Thu night, ~45 min)

Plain words: given a claim and the Fact, decide supported/contradicted and write the `correct_value`.

**Files:**
- Create: `second_opinion/verdict.py`
- Test: `tests/test_verdict.py`

**Interfaces:**
- Produces: `judge(claim: Claim, fact: Fact) -> tuple[Verdict, str | None]` (verdict, `correct_value` for contradicted else `None`), and `format_fact(fact: Fact, unit: str | None) -> str` giving `"49.9% (421 of 844)"` or `"535 of 1,101"` (thousands separators, one decimal for percents).

- [ ] **Step 1: Write failing tests**, one row per rule from Global Constraints:

```python
@pytest.mark.parametrize("params, num, den, expected", [
    (dict(stated_value=62, unit="percent", approximate=True), 421, 844, Verdict.CONTRADICTED),
    (dict(stated_value=50, unit="percent", approximate=True), 421, 844, Verdict.SUPPORTED),     # 49.9 is within 2 points
    (dict(stated_value=49.9, unit="percent", decimals=1), 421, 844, Verdict.SUPPORTED),
    (dict(stated_value=50.0, unit="percent", decimals=1), 421, 844, Verdict.CONTRADICTED),     # exact claim, wrong digit
    (dict(stated_value=50, unit="percent"), 421, 844, Verdict.SUPPORTED),                       # 49.9 rounds to 50 at 0 decimals
    (dict(stated_value=45, stated_high=55, unit="percent"), 421, 844, Verdict.SUPPORTED),     # range contains 49.9
    (dict(stated_value=535, unit="count", stated_total=1101), 535, 1101, Verdict.SUPPORTED),
    (dict(stated_value=540, unit="count", stated_total=1101), 535, 1101, Verdict.CONTRADICTED),
    (dict(stated_value=540, unit="count", approximate=True), 535, 1101, Verdict.SUPPORTED),    # within 2% of the count
])
def test_judge(params, num, den, expected): ...

def test_contradicted_returns_correct_value():
    assert judge(...)[1] == "49.9% (421 of 844)"
def test_comparison_direction():   # direction "higher", fact.value = +3.051 -> supported; value = -0.2 -> contradicted
def test_coverage_claim_with_missing_samples_is_contradicted():  # correct_value mentions the count of missing
```
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_verdict.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `judge`. Round the computed percent to `claim.params.decimals` (default 0) before comparing for exact claims; for approximate claims use the tolerances in Global Constraints. A comparison is `supported` when the sign of `fact.value` matches `direction` and `fact.value != 0`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: verdict rules with tolerance`.

### Task A5: Pipeline, `/audit`, CLI (Fri morning, ~90 min)

Plain words: run every claim through its check and verdict, and return an `AuditResult`. Robustness, skeptic and ladder plug in later, so for now they are empty or `not_applicable`.

**Files:**
- Create: `second_opinion/audit.py`
- Modify: `second_opinion/cli.py`, `apps/api/app/routes/audit.py`
- Test: `tests/test_audit.py`, `tests/test_api_audit.py`

**Interfaces:**
- Consumes: `CHECKS`, `judge`, `Release`; Benoy's `build_ladder(claim, result) -> list[LadderSegment]` (Task B6) and `skeptic_for(...)` (Task B5): import them inside `try/except ImportError` until they exist, or default to `[]`/`None`.
- Produces:

```python
def audit_claims(claims: list[Claim], release_dir: str | Path) -> AuditResult
```
`NOT_ANSWERABLE` and `UNMAPPED` claims get `insufficient_evidence`, `missing_evidence` taken from `claim.needed_data` (for `UNMAPPED`: `"No check exists yet for this kind of claim"`), `solidity=NOT_APPLICABLE`. `CannotCheck` becomes `insufficient_evidence` with the exception message as `missing_evidence`. `AuditResult.notes` carries "No RNA file in this release." and any checksum mismatch against `sources.csv` fingerprints if available. `ReleaseInfo.files` lists every release file with its sha256 (from `Release.checksums`).

CLI: `second-opinion --release <dir> --report <report.md> --out audit.json` runs extract → audit → a default "accept all" review → export, so the CLI works end to end once Meghana's M2 lands (until then it writes the `AuditResult` JSON).

- [ ] **Step 1: Write failing tests**: the practice report claims (build the three `Claim` objects by hand in the test) give `[SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE]` with `correct_value == "49.9% (421 of 844)"` and `missing_evidence` containing "treatment"; the API test posts them to `/audit` and gets the same; a bad `release_dir` gives HTTP 400 with `"detail"` naming the folder; an empty `claims` list returns a valid `AuditResult` with `claims == []` and the release file checksums (the Start screen uses this to check the folder).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** The endpoint is a plain `def` (not `async`) because pandas work blocks.
- [ ] **Step 4: Run** `npm test`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: audit pipeline, /audit endpoint and CLI`.

**Done when:** `curl` the endpoint on the real release returns the three practice verdicts in under 10 seconds.

### Task A6: Comparison and agreement checks (Fri, ~90 min)

Plain words: "ER-alpha protein is higher in ER-positive tumors" — compute the two group means and the difference.

**Files:**
- Create: `second_opinion/checks/compare.py`; `checks/agreement.py` (stretch, only if A7 is done)
- Test: `tests/test_checks_compare.py`

**Interfaces:**
- Produces: `check_comparison(claim, release, variant) -> Fact` registered under `ClaimType.COMPARISON`. Uses the definition in `reference_analyses.py` A1: primary tumors in the protein file with clinical `breast_carcinoma_estrogen_receptor_status` of `Positive` or `Negative`; protein row `ERALPHA`. `Fact.value` = mean(group_a) − mean(group_b); `extra` holds `n_a`, `n_b`, `mean_a`, `mean_b`; `sample_ids` are the 698 used. Direction `lower` flips the sign convention in `judge`, not here. Unknown measure or group → `CannotCheck("this release has no <measure> measurement")`.

- [ ] **Step 1: Write failing test:**

```python
@pytest.mark.realdata
def test_er_alpha_matches_reference_analysis_a1(release_dir):
    claim = Claim("C9", "...", 0, ClaimType.COMPARISON, ClaimParams(direction="higher", measure="ER-alpha protein", group_a="ER-positive", group_b="ER-negative"))
    f = CHECKS[ClaimType.COMPARISON](claim, load_release(release_dir), PRIMARY_VARIANT)
    assert (f.extra["n_a"], f.extra["n_b"]) == (529, 169)
    assert round(f.value, 3) == 3.051
```
- [ ] **Step 2–5:** run (FAIL), implement, run (PASS), commit `feat: comparison check matching reference analysis A1`.

### Task A7: Robustness (Fri, ~90 min)

Plain words: redo each claim's check under all 8 variants and tag it robust or fragile. This is our "count it differently" feature.

**Files:**
- Create: `second_opinion/robustness.py`
- Modify: `second_opinion/audit.py` (call it for SHARE and COMPARISON claims only)
- Test: `tests/test_robustness.py`

**Interfaces:**
- Produces: `run_variants(claim: Claim, release: Release) -> list[VariantResult]` (all 8; a variant that cannot be checked gets `fact=None, verdict=None`), `solidity_of(variants: list[VariantResult], primary: Verdict) -> tuple[Solidity, list[str]]` (the flips are strings like `"subtype_source=study_2012_label"`: the single choice that differs from the primary variant in the flipping variants).

- [ ] **Step 1: Write failing tests**: 62% claim → `HOLDS_EVERYWHERE`, 8 variants, `flips_on == []`; a constructed claim "about 45% are Luminal A" → `FRAGILE` and `flips_on` contains `"subtype_source=study_2012_label"` (primary 49.9% is outside 45±2, 2012 label 44.3% inside); count claims → `NOT_APPLICABLE`.
- [ ] **Step 2–5:** run (FAIL), implement, run (PASS), commit `feat: eight-variant robustness`.

### Task A8: Integration, hardening, rehearsal (Fri evening → Sat morning)

Plain words: make it hold up on the judges' unseen report.

**Files:**
- Modify: whatever the failures point to. Test: `tests/test_envelope.py`

- [ ] **Step 1:** `python ../oncosys-hackathon-challenge/envelopes/unseal.py practice orange meadow pilot lantern`, then run the CLI on `envelopes/opened/practice/release/` with Benoy's test reports. Write `test_envelope.py` (skipped unless `SO_ENVELOPE_DIR` is set) asserting the run finishes, writes a valid `audit.json`, and notes the missing RNA file.
- [ ] **Step 2:** Fix every wrong verdict Benoy's reports expose. Time the full run: unseal + audit + export must be under 2 minutes, three times in a row.
- [ ] **Step 3:** Handle the Review Focus items in order; each has a test already in its owner's task.
- [ ] **Step 4:** Final repo checks: `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`, a secret scan (`gitleaks detect`), fresh-clone setup on a second machine.
- [ ] **Step 5:** Tag the submitted commit.

---

# Benoy: reading the report

First hour: setup, then read the practice brief (`docs/challenge/products/research-claim-auditor/practice_brief.md`) and Section "Contracts" above. Your work needs no data files: it is text in, claims out. Start with B1 as soon as Allen's A1 is on `main`.

### Task B1: Sentence splitting (Thu night, ~45 min)

Plain words: cut the report into sentences without breaking on `1,101`, `49.9%`, `fetch.py` or `e.g.`.

**Files:**
- Create: `second_opinion/extract.py`
- Test: `tests/test_extract_sentences.py`

**Interfaces:**
- Produces: `split_sentences(report_text: str) -> list[SentenceInfo]` with `claim_id=None` for now. Skip Markdown headings (`#`), horizontal rules and code fences; strip `*`, `_` and backticks from the text but keep the words; treat each bullet as its own sentence; `index` counts sentences from 0 in order.

- [ ] **Step 1: Write failing tests**:

```python
def test_numbers_and_filenames_do_not_split():
    out = split_sentences("The cohort has 1,101 tumors (49.9% subtyped). See fetch.py for details.")
    assert [s.text for s in out] == ["The cohort has 1,101 tumors (49.9% subtyped).", "See fetch.py for details."]

def test_headings_and_emphasis():
    out = split_sentences("# Title\n\n*A note.* Body text.")
    assert [s.text for s in out] == ["A note.", "Body text."]

def test_empty_report():
    assert split_sentences("  \n ") == []
```
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_extract_sentences.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** with a regex that splits on `[.!?]` followed by whitespace and an uppercase letter or end of text, after protecting digit-comma-digit, decimals and `\w+\.\w+` tokens.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: report sentence splitting`.

### Task B2: Claim typing and parameter parsing (Fri morning, ~2 h)

Plain words: decide which sentences are checkable claims, what type each is, and pull out the numbers and words the checks need.

**Files:**
- Modify: `second_opinion/extract.py`
- Test: `tests/test_extract_claims.py`

**Interfaces:**
- Consumes: `split_sentences`, `normalise_subtype` (`second_opinion/variants.py`), `detect_unanswerable` (Task B3).
- Produces: `classify_sentence(info: SentenceInfo, claim_id: str) -> Claim | None` (None = not a claim) and `extract_claims(report_text: str) -> ExtractResult`. Claim ids are `C1, C2, …` in report order across *claims only*.

Typing rules (first match wins, written as an ordered list of small functions so each can be tested alone):
1. Clinical or causal wording (via `detect_unanswerable`) → `NOT_ANSWERABLE`, with `needed_data` and `clinical_terms`.
2. A percent or "N of M" with a subtype name → `SHARE` (`unit="percent"` or `"count"`, `subtype` normalised, `subject="primary_tumors"`).
3. "higher / lower / more / less … in …" with two groups → `COMPARISON` (`direction`, `measure`, `group_a`, `group_b`).
4. "every / all / each" + a data layer → `COVERAGE` (`unit="all"`, `subject="has_protein"` etc.).
5. A number about samples, tumors or patients → `COUNT` ("535 of 1,101 … all five" → `subject="all_five_layers"`, `stated_value=535`, `stated_total=1101`).
6. Contains a number that matches none of the above → `UNMAPPED` (kept as a claim so the tool says "no check yet" instead of silently skipping).
7. Otherwise `None`.

Number parsing: thousands separators (`1,101`), `62 %`, `49.9%`, ranges `55–65%` / `55-65 %` (`stated_value=55, stated_high=65`), `decimals` from the text, and `approximate=True` for about, roughly, nearly, around, approximately, `~`, `c.`.

- [ ] **Step 1: Write failing tests** (these sentences are the practice brief's, verbatim; add each new trap as another row):

```python
def claim(text):  # helper: classify one sentence
    return extract_claims(text).claims[0]

def test_practice_count():
    c = claim("Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data.")
    assert c.type is ClaimType.COUNT
    assert (c.params.stated_value, c.params.stated_total, c.params.subject) == (535, 1101, "all_five_layers")

def test_practice_share():
    c = claim("Luminal A is the largest RNA subtype, accounting for about 62% of primary tumors with an RNA subtype call.")
    assert c.type is ClaimType.SHARE
    assert (c.params.stated_value, c.params.unit, c.params.approximate, c.params.subtype) == (62, "percent", True, "Luminal A")

def test_practice_not_answerable():
    c = claim("Patients whose tumors had the highest ER-alpha protein responded best to hormone therapy, which suggests protein data could guide treatment research.")
    assert c.type is ClaimType.NOT_ANSWERABLE and "responded" in c.clinical_terms and "treatment" in c.needed_data

def test_practice_brief_gives_exactly_three_claims():
    result = extract_claims(Path("docs/challenge/products/research-claim-auditor/practice_brief.md").read_text())
    assert [c.id for c in result.claims] == ["C1", "C2", "C3"]
    assert [c.type for c in result.claims] == [ClaimType.COUNT, ClaimType.SHARE, ClaimType.NOT_ANSWERABLE]

@pytest.mark.parametrize("text, value, high, approx", [
    ("Luminal B makes up nearly 23% of subtyped tumors.", 23, None, True),
    ("Basal-like is between 15 and 18 percent of subtyped primary tumors.", 15, 18, False),
    ("Basal-like is 15–18 % of subtyped primary tumors.", 15, 18, False),
    ("Her2 is 7.9% of subtyped primary tumors.", 7.9, None, False),
])
def test_number_forms(text, value, high, approx): ...

@pytest.mark.parametrize("raw", ["LumA", "Luminal A", "Luminal-A", "luminal a"])
def test_subtype_spelling(raw):   # all give params.subtype == "Luminal A"

def test_sentence_with_no_claim_is_skipped():
    assert extract_claims("Protein measurements add a useful layer.").claims == []

def test_unknown_number_sentence_is_kept_as_unmapped():
    assert claim("The median age was 58 years.").type is ClaimType.UNMAPPED
```
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_extract_claims.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** with regexes and keyword lists in module-level constants (easy to extend on Saturday). Pass subtype names through `normalise_subtype`; extend its alias table in `variants.py` only after asking Allen (add `"luminal-a"` style handling by stripping non-alphanumerics, which it already does).
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: claim typing and number parsing`.

**Done when:** all rows pass and the three practice claims come out exactly as in the table above.

### Task B3: "The data can't answer this" detection (Thu night, ~45 min; do it right after B1)

Plain words: spot sentences about treatment, response, cause, prediction or survival benefit, and say what data would be needed. Saying "this data can't answer that" is a winning result.

**Files:**
- Create: `second_opinion/unanswerable.py`
- Test: `tests/test_unanswerable.py`

**Interfaces:**
- Produces:

```python
@dataclass
class Unanswerable:  terms: list[str]; needed_data: str
def detect_unanswerable(sentence: str) -> Unanswerable | None
```
Keyword groups (module-level dict, edit freely): treatment/therapy/"hormone therapy"/"guide treatment" → `"treatment and outcome data"`; responded/response/"responded best" → `"treatment-response data"`; causes/drives/predicts/determines/leads to → `"experimental or longitudinal data that can test cause or prediction"`; "survival benefit"/improves survival → `"treatment-arm survival data"`. When several groups match, join the needs with `" and "`, without duplicates. Match whole words, case-insensitive. Also list in the module docstring what the release *does* contain (clinical, survival, mutation, copy number, protein) so the message is honest.

- [ ] **Step 1: Write failing tests**: the practice sentence → terms include `"responded"` and `"hormone therapy"`, `needed_data` contains `"treatment"`; "ER-alpha drives growth" → needs cause data; "The response rate table is attached" → hmm: decide and test one deliberate behaviour, "response" alone triggers (be conservative: flag); a plain count sentence returns `None`; "therapy" inside "therapyx" does not match.
- [ ] **Step 2–5:** run (FAIL), implement, run (PASS), commit `feat: detect questions the data cannot answer`.

### Task B4: `/extract` and `/classify` endpoints (Fri, ~45 min)

**Files:**
- Modify: `apps/api/app/routes/extract.py`
- Test: `tests/test_api_extract.py`

**Interfaces:**
- Consumes: `extract_claims`, `classify_sentence`. Produces: `POST /extract {report_text}` → `ExtractResult`; `POST /classify {text, sentence_index}` → `Claim`, where a sentence with nothing checkable returns type `UNMAPPED` (the user ticked it, so it becomes a claim and the audit says "no check exists yet").

- [ ] **Step 1: Write failing tests** with `TestClient`: practice brief text → 3 claims and every sentence listed with `claim_id` set only for claim sentences; empty `report_text` → HTTP 422 with `"detail"` "The report is empty"; a report with no checkable sentence → 200 with `claims == []` (the UI shows "nothing to check").
- [ ] **Step 2–5:** run (FAIL), implement, run (PASS), commit `feat: extract and classify endpoints`.

### Task B5: Skeptic tests (Fri afternoon, ~90 min)

Plain words: two sanity checks for comparison claims: "does the difference survive shuffling the labels?" and "does it survive dropping one hospital at a time?".

**Files:**
- Create: `second_opinion/skeptic.py`
- Test: `tests/test_skeptic.py`

**Interfaces:**
- Produces:

```python
def shuffle_test(values: pd.Series, groups: pd.Series, n: int = 200, seed: int = 0) -> float
    # p = share of shuffles whose |mean difference| >= the real |difference|, with +1 smoothing: (hits + 1) / (n + 1)
def leave_one_site_out(values: pd.Series, groups: pd.Series, sites: pd.Series) -> list[str]
    # site codes whose removal flips the sign of the mean difference (group order = sorted unique group labels)
def skeptic_for(claim: Claim, release: Release) -> SkepticResult | None
    # COMPARISON claims only; site code = the tissue_source_site column in clinical.tsv; n_sites = number of distinct sites
```

- [ ] **Step 1: Write failing tests**: synthetic data with a clear difference → `shuffle_test(...) < 0.05`; identical groups → `> 0.2`; fixed seed gives the same value twice; a dataset where one site drives the effect → that site appears in `leave_one_site_out`; a real-data test (marked `realdata`) for the ER-alpha comparison: `shuffle_p < 0.01`.
- [ ] **Step 2–5:** run (FAIL), implement with `numpy.random.default_rng(seed)`, run (PASS), commit `feat: skeptic tests`. Tell Allen the function is ready (he calls `skeptic_for` in `audit.py`).

### Task B6: Claim Ladder wording (Fri afternoon, ~90 min)

Plain words: rewrite each claim as crossed-out over-strong words plus the honest version. Rules, no AI, same output every time.

**Files:**
- Create: `second_opinion/ladder.py`
- Test: `tests/test_ladder.py`

**Interfaces:**
- Produces: `build_ladder(claim: Claim, result: ClaimResult) -> list[LadderSegment]`. Rules in order:
  1. Contradicted number: strike the stated number and any "about/roughly…" before it; insert `correct_value`.
  2. Vague amount (about, most, nearly all, majority): strike it, insert the exact `N of M`.
  3. Clinical or treatment wording (`claim.clinical_terms`): strike those words; append a segment (inserted) `"— not answerable from this data; would need: <needed_data>"`.
  4. Cause or prediction words (causes, drives, predicts, determines): strike, insert "was associated with".
  5. Over-generalising (breast cancer patients, all women, in general): append the scope `"in this TCGA-BRCA release, among N primary tumors"` using the fact's denominator.
  For a `supported` claim with nothing to change: one unstruck segment (the sentence itself).

- [ ] **Step 1: Write failing tests**: the practice 62% claim yields segments where the struck text includes "about 62%" and the inserted text contains `"49.9% (421 of 844)"`, and `"".join(s.text for s in segments if not s.struck)` reads as a sentence containing both `"421 of 844"` and `"Luminal A"`; the hormone sentence has struck `"responded best"` and an inserted segment containing `"treatment"`; a supported count claim returns a single segment with `struck=False`; no segment text is empty.
- [ ] **Step 2–5:** run (FAIL), implement, run (PASS), commit `feat: claim ladder rewriting`.

### Task B7: Our own test reports (Fri evening, ~2 h, most valuable test of the weekend)

Plain words: write reports with different errors, the way the judges will, and find out where we break.

**Files:**
- Create: `tests/reports/report_1.md` … `report_3.md` and `report_N.expected.json` (list of `{claim_contains, verdict}` pairs), `tests/test_own_reports.py` (skipped unless `SO_RELEASE_DIR`)

Each report has 4–5 claims and between them cover: every claim type; an approximate number ("nearly 17%"); a range; a wrong count; a claim with the wrong subtype spelling (`Basal` vs `Basal-like`); a claim mixing a checkable part and a clinical part; a claim about RNA (for the no-RNA release); a claim about male samples; a claim about normal-tissue samples. Work out each expected verdict by hand with pandas first, then write them down.

- [ ] **Step 1:** write the reports and expected files. **Step 2:** `.venv/bin/python -m pytest tests/test_own_reports.py -v` (FAIL is fine and useful). **Step 3:** send every mismatch to the owner (parsing → you; checks/verdict → Allen) with the sentence and expected vs actual. **Step 4:** rerun until green. **Step 5:** commit `test: own reports with known answers`.

---

# Akshaya: the web app's main path

First hour: setup, read `apps/web/AGENTS.md`, open `apps/web/src/app/page.tsx` and `globals.css` to see how pages and Tailwind are set up, then read `tests/fixtures/practice_audit_result.json` (after A1). Everything you build reads the fixture shape, so the real engine will drop in without changes. No component library: Tailwind only.

Design rules (apply to every screen):
- Verdict is **text + icon + colour**, never colour alone: `✓ Supported`, `✕ Contradicted`, `? Insufficient evidence`. Solidity is text too: `Robust (8 of 8)` / `Fragile: flips when <choice>`.
- Plain words, short sentences. Technical terms get a tooltip from `lib/glossary.ts`.
- Every focusable element has a visible focus ring. Everything works with the keyboard alone.
- The research banner from K1 is on every screen.
- Server Components by default; add `"use client"` only for pages and components with state or handlers.

### Task K1: App shell, API client, shared state (Thu night / Fri morning, ~2 h)

Plain words: the frame every screen sits in, plus the one place that holds the report, claims and audit result.

**Files:**
- Create: `apps/web/src/lib/api.ts`, `apps/web/src/lib/audit-context.tsx`, `apps/web/src/components/ResearchBanner.tsx`, `StepNav.tsx`, `Breadcrumb.tsx`
- Modify: `apps/web/src/app/layout.tsx` (banner, `StepNav`, provider), `apps/web/src/app/page.tsx` is replaced in K2
- Test: `npm run lint && npm run typecheck && npm run build`

**Interfaces:**
- Consumes: `lib/types.ts` (from A1).
- Produces:

```ts
// api.ts: each throws Error(detail) with the API's "detail" text on a non-2xx response
extractClaims(reportText: string): Promise<ExtractResult>
classifySentence(text: string, sentenceIndex: number): Promise<Claim>
runAudit(releaseDir: string, claims: Claim[]): Promise<AuditResult>
suggestDecision(audit: AuditResult): Promise<DecisionSuggestion>
exportAudit(audit: AuditResult, decision: DecisionChoice): Promise<{ audit_json: unknown; decision_record_md: string }>
getRoles(): Promise<Role[]>;  saveRole(role: Role): Promise<Role[]>

// audit-context.tsx (client): useAudit() returns
{ reportText, setReportText, releaseDir, setReleaseDir,
  sentences, claims, setExtract(result), toggleClaim(sentenceIndex),   // claims the user keeps
  audit, setAudit(result), setReview(claimId, review),                // review lives on audit.claims[i].review
  role, setRole(name) }
```
`Role` is `{ name: string; sections: string[]; detail: "summary" | "standard" | "full"; explain_terms: boolean }` (Meghana owns `roles.yaml`; define the TS type here and tell her).

- [ ] **Step 1:** write `api.ts` and the context against the stub endpoints (they already return the fixture). **Step 2:** `npm run typecheck` (FAIL until types resolve). **Step 3:** build the banner (exact text from Global Constraints), `StepNav` (Start → Claims → Audit board → Review → Decision, current step marked with `aria-current="step"`), `Breadcrumb`. **Step 4:** `npm run lint && npm run typecheck && npm run build`. Expected: PASS. **Step 5:** commit `feat: web shell, api client, audit context`. Tell Meghana: "K1 is on main."

**Done when:** `useAudit()` can be used from any page and `/api/audit` stub data is typed end to end.

### Task K2: Start screen (Fri morning, ~90 min)

Plain words: upload the report, say where the data folder is, run claim extraction.

**Files:**
- Modify: `apps/web/src/app/page.tsx`; Create: `components/ReportUpload.tsx`, `components/ReleasePicker.tsx`

Behaviour: file input accepts `.md` and `.txt` and also a paste box (read the file with `FileReader`); a "Use the practice report" button loads `practice_brief.md` text (copy it into `apps/web/public/practice_brief.md`); text field for the release folder with a default of the env-provided path (`NEXT_PUBLIC_DEFAULT_RELEASE_DIR`, documented in `.env.example`); a **Check the files** button calls `POST /audit` with no claims to confirm the folder and show "5 of 5 files found, checksums listed" or the API's error message; **Find claims** calls `extractClaims`, stores the result, goes to `/claims`. Role picker is added later by Meghana (Task M4).

- [ ] Steps: build the page; verify by hand with the stub (click practice report → Find claims → lands on `/claims` with 3 claims); `npm run lint && npm run typecheck && npm run build`; commit `feat: start screen`.

### Task K3: Claims list (Fri morning, ~90 min)

Plain words: show every sentence, mark the checkable ones, let the user fix mistakes.

**Files:** Create `apps/web/src/app/claims/page.tsx`, `components/ClaimRow.tsx`.

Behaviour: every sentence in report order; claim sentences have a checked checkbox, a type chip (`Count`, `Share`, `Comparison`, `Coverage`, `Not answerable`, `No check yet`) and the extracted numbers in words ("62%, approximate, Luminal A"); unticking removes the claim, ticking a non-claim sentence calls `classifySentence` and adds it. Empty claim list shows "Nothing checkable found. Tick a sentence to check it." **Run audit** calls `runAudit(releaseDir, claims)`, shows a progress state ("Checking 3 claims…"), stores the result, goes to `/board`. API errors show in an `aria-live="polite"` region, not an alert box.

- [ ] Steps: build; verify untick/tick/empty states by hand; lint, typecheck, build; commit `feat: claims list`.

### Task K4: Audit board with the Claim Ladder (Fri midday, ~3 h) — the main screen

Plain words: one card per claim, with the verdict, how solid it is, and the crossed-out wording.

**Files:** Create `apps/web/src/app/board/page.tsx`, `components/ClaimCard.tsx`, `VerdictBadge.tsx`, `SolidityTag.tsx`, `LadderText.tsx`, `StatementLabel.tsx`.

Behaviour:
- Card: claim id, original sentence, `VerdictBadge`, `SolidityTag`, `LadderText` (struck segments with `<del>`, inserted segments in bold), the number with its denominator ("49.9% (421 of 844)"), `StatementLabel` tags (`Computed` for numbers from the data, `Reported` for text from the report, `Interpretation` for ladder inserts), and an **Open evidence** link to `/board/<claimId>`.
- Contradicted: show `correct_value`. Insufficient: show `missing_evidence` as "Would need: …". Any `audit.notes` (for example no RNA file) appear in a banner above the cards.
- Cards are in a list with headings; arrow keys are not required, Tab order is enough.
- Counts by verdict at the top ("1 supported · 1 contradicted · 1 insufficient evidence").

- [ ] Steps: build with the fixture; check the three practice cards match the table in "The shape of the system"; lint/typecheck/build; commit `feat: audit board and claim ladder`. Screenshot for Checkpoint 1/2.

### Task K5: Evidence panel (Fri afternoon, ~3 h)

Plain words: click any number and see exactly where it came from, so a judge can reproduce it.

**Files:** Create `apps/web/src/app/board/[claimId]/page.tsx`, `components/EvidencePanel.tsx`, `RobustnessTable.tsx`, `CodeBlock.tsx`, `SampleList.tsx`.

Behaviour: the calculation in words (`fact.label` plus numerator/denominator); source files with the release checksums from `audit.release.files`; `CodeBlock` with the `fact.code` and a **Copy code** button (button text changes to "Copied" and an `aria-live` region announces it); `SampleList` showing the first 20 IDs and **Download all sample IDs (CSV)** (generate in the browser from `fact.sample_ids`, file name `<claimId>-samples.csv`, header `sample_id`); `RobustnessTable` with one row per variant (variant in words, value as `N of M`, verdict text) and the flipping row highlighted; skeptic results ("Shuffled labels 200 times: real difference larger than 99% of shuffles", "Leaving out each of 40 hospitals: never flips"); the limitation text; `Breadcrumb` (Board > C2). **Re-run with a changed rule** is a stretch: a select for each of the three choices that calls `runAudit` with the claim and shows the new result next to the old one only if Allen exposes a variant parameter; skip otherwise.

- [ ] Steps: build; check the 62% claim shows 8 variants and the four numbers 49.9/49.9/44.3/45.4 per the fixture; check the not-answerable claim shows "what's missing" and no table; lint/typecheck/build; commit `feat: evidence panel`.

### Task K6: Accessibility and glossary (Sat morning, ~2 h)

- [ ] Add `lib/glossary.ts` (terms: robust, fragile, variant, denominator, subtype call, release, checksum, claim ladder) and an accessible `Term` component (keyboard-focusable, shown on focus and hover, `aria-describedby`).
- [ ] Keyboard-only run-through of the whole flow (Start → … → Decision); fix every trap and every missing focus ring.
- [ ] Run Lighthouse accessibility on `/`, `/claims`, `/board`, `/board/C2`; fix everything below 95.
- [ ] Check colour contrast and that verdict meaning survives greyscale; commit `fix: accessibility pass`.

---

# Meghana: decisions, outputs, documentation

First hour: setup, read the shared-format guide (`docs/challenge/format/README.md`) and the schema, and open `tests/fixtures/practice_audit_result.json` (after A1). Your first two tasks need no web code and no real data.

### Task M1: Overall decision rules (Thu night, ~45 min)

Plain words: from the claim results, suggest Proceed / Fix a problem / Narrow the question / Stop, with reasons.

**Files:** Create `second_opinion/decision.py`; Test `tests/test_decision.py`.

**Interfaces:**
- Consumes: `AuditResult`, `Decision`. Produces:

```python
def suggest_decision(audit: AuditResult) -> DecisionSuggestion
```
Rules, in order (first match wins), using each claim's `review.final_verdict` when a review exists, else `verdict`:
1. Any release file `sha256` missing or `audit.notes` contains a line starting `"Checksum mismatch"` → `Stop`.
2. Any claim `contradicted` → `Fix a problem`.
3. Any claim `insufficient_evidence` or `solidity == FRAGILE` → `Narrow the question`.
4. Otherwise → `Proceed`.
`rule` is a short sentence ("Rule 2: at least one claim is contradicted"); `reasons` lists each claim id and why; `sign_off` is `["Data-use reviewer", "Principal investigator"]` for every decision; `would_change` lists plain statements such as `"If treatment-response data were added, C3 could be tested"` for each insufficient claim and `"If C2 were reworded to 49.9% (421 of 844), it could be published"` for each contradicted one.

- [ ] **Step 1: Write failing tests**: the practice fixture → `Fix a problem` with `C2` in `reasons`; fixture with C2 removed → `Narrow the question`; only supported + robust claims → `Proceed`; a checksum-mismatch note → `Stop` (beats everything); an override review that turns C2 into `supported` → `Narrow the question` (C3 still open).
- [ ] **Step 2–5:** run `.venv/bin/python -m pytest tests/test_decision.py -v` (FAIL), implement, run (PASS), commit `feat: decision rules`.

### Task M2: `audit.json` export that passes the validator (Fri morning, ~2 h) — required output

Plain words: build the file the organizers' checker reads. If this is wrong, we lose the objective score, so it gets the most careful tests.

**Files:**
- Create: `second_opinion/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `AuditResult` (with reviews), `DecisionChoice`, the vendored schema at `docs/challenge/format/findings.schema.json`.
- Produces:

```python
def build_audit_json(audit: AuditResult, decision: DecisionChoice | None, team: str = "SecondOpinion") -> dict
def validate_audit_json(doc: dict) -> list[str]   # error messages, empty when valid (jsonschema Draft 2020-12 against the schema file)
```
Mapping (exactly this, so output is predictable):

| audit.json field | Source |
| --- | --- |
| `format_version` | `"0.2"` |
| `producer` | `{"team": team, "product": "Research Claim Auditor", "track": "evidence-navigator"}` |
| `data` | `{"dataset": "TCGA-BRCA", "releases": [{"name": audit.release.name, "files": audit.release.files}]}` |
| `question` | `"Are the claims in the report supported by release <name>?"` |
| `verdict` | `decision.choice.value` if a decision is given, else omitted |
| finding `id`, `kind` | `claim.id`, `"claim_check"` |
| `claim_text`, `claim_verdict` | claim text, **final** verdict (the review's `final_verdict` if present, else the machine verdict), value strings exactly `supported` / `contradicted` / `insufficient_evidence` |
| `correct_value` | only when the final verdict is `contradicted`; the engine's string, e.g. `49.9% (421 of 844)` |
| `summary` | contradicted: `"<correct_value> in the data, not what the report says."`; supported: `"Recomputed from the data: <N of M>."`; insufficient: `"The data cannot answer this; would need: <missing_evidence>."` |
| `severity` | contradicted → `medium`, insufficient_evidence → `low`, supported → `none` |
| `confidence` | `high` if solidity is holds-under-every-variant or the claim is supported/insufficient from a keyword rule; `medium` if fragile; `medium` otherwise |
| `evidence` | one `{"kind": "file", "id": <file>, "release": <release name>, "note": "<fact.label>; <robust N of 8 or fragile: flips on …>"}` per file in `fact.files`; for insufficient claims with no files, one `{"kind": "claim", "id": claim.id, "note": "no data field can test this claim"}` |
| `limitation` | `result.limitation` if set |
| `needs_human_review` | `true` for every finding (also those already reviewed; the human review is recorded in the Decision Record) |

- [ ] **Step 1: Write failing tests**:

```python
def test_practice_fixture_exports_a_valid_file():
    doc = build_audit_json(load_fixture(), decision=None)
    assert validate_audit_json(doc) == []
    c2 = next(f for f in doc["findings"] if f["id"] == "C2")
    assert (c2["kind"], c2["claim_verdict"], c2["correct_value"]) == ("claim_check", "contradicted", "49.9% (421 of 844)")

def test_correct_value_only_for_contradicted():
    doc = build_audit_json(load_fixture(), None)
    assert all(("correct_value" in f) == (f["claim_verdict"] == "contradicted") for f in doc["findings"])

def test_override_changes_final_verdict():   # review final_verdict supported on C2 -> claim_verdict "supported", no correct_value
def test_official_validator_accepts_output(tmp_path):
    # write the doc to tmp_path/audit.json and run the real script:
    # subprocess.run([sys.executable, "docs/challenge/format/validate.py", str(path)]) returns exit code 0
def test_empty_audit_still_validates():   # zero claims -> doc validates (schema requires findings array; if minItems rejects it, return the validator's message)
```
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_export.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Fix whatever `validate.py` complains about, the script is the judge. Evidence entries must never be empty (schema `minItems: 1`).
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: audit.json export matching shared format v0.2`. Tell Allen so the CLI can call `build_audit_json`.

**Done when:** `python docs/challenge/format/validate.py audit.json` prints its success line on the fixture-derived file.

### Task M3: Decision Record and `/decision`, `/export` endpoints (Fri midday, ~2 h)

**Files:**
- Modify: `second_opinion/export.py`, `apps/api/app/routes/export.py`
- Test: `tests/test_decision_record.py`, `tests/test_api_export.py`

**Interfaces:**
- Produces: `build_decision_record(audit: AuditResult, decision: DecisionChoice, suggestion: DecisionSuggestion, today: date, tool_version: str = "0.1.0") -> str` (Markdown with these sections in this order: report and release name with file checksums, date and tool version; chosen decision, the reviewer's reason and role, and the rule that suggested it; a table of claims (original text, machine verdict, robust/fragile, corrected wording from the ladder, human override with reason or "none"); important limitations; who must sign off; "What would change this decision"; the research-only line). `POST /decision` returns `suggest_decision(audit)`. `POST /export` returns `{audit_json, decision_record_md}` and **422 with detail "Every claim needs a review before export"** when any claim has `review is None`, naming the unreviewed ids.

- [ ] **Step 1: Write failing tests**: record contains "421 of 844", each claim id, the override reason text when present, "Principal investigator", and the research-only line; API export with one unreviewed claim → 422 and the id in `detail`; fully reviewed → 200 and `audit_json` validates.
- [ ] **Step 2–5:** run (FAIL), implement, run (PASS), commit `feat: decision record and export endpoints`.

### Task M4: Roles (Fri afternoon, ~2 h; after K1 is on main)

Plain words: four roles that read the same facts with different wording and detail, plus a way to add a role without touching code.

**Files:**
- Create: `second_opinion/roles.py`, `roles.yaml`, `apps/web/src/components/RolePicker.tsx`, `RoleSummary.tsx`, `AddRoleForm.tsx`
- Modify: `pyproject.toml` (add `pyyaml>=6,<7` to dependencies), `apps/web/src/app/page.tsx` (one line to place `RolePicker`: ask Akshaya, or send her the snippet), `apps/api/app/routes/roles.py`
- Test: `tests/test_roles.py`

**Interfaces:**
- Produces: `load_roles(path: Path = ROLES_FILE) -> list[Role]`, `add_role(role: Role, path: Path = ROLES_FILE) -> list[Role]` (rejects duplicate names and empty `sections`), with `Role` as the dataclass `Role(name: str, sections: list[str], detail: str, explain_terms: bool)` in `roles.py`. `roles.yaml` ships four roles: **Program leader** (`summary`; sections `decision`, `counts`, `sign_off`), **Data-use reviewer** (`standard`; `claims`, `review_queue`, `decision_record`), **Researcher** (`full`; `corrected_wording`, `robustness`, `skeptic`), **Data engineer** (`full`; `sample_ids`, `files`, `code`). Valid section names are exactly those listed. `GET /roles` and `POST /roles` wrap them.
- Web: `RolePicker` (a `<select>` with an accessible label, saved with `setRole`), `RoleSummary` (renders the decision page header for the chosen role: Program leader sees one sentence — the decision, the main risk, the next step — and counts by verdict; others see their sections), `AddRoleForm` (name, checkboxes for sections, detail level, "explain terms" toggle; posts to `/roles` and refreshes the list).

- [ ] **Step 1: Write failing tests**: four default roles load; `add_role` writes a fifth that survives reload (use `tmp_path` copy of the file); duplicate name → `ValueError`; unknown section → `ValueError`; API round trip.
- [ ] **Step 2–5:** run (FAIL), implement backend, run (PASS); build the three components; `npm run lint && npm run typecheck && npm run build`; commit `feat: roles with add-a-role form`.

**Done when:** adding a role in the browser makes it appear in the picker immediately and in `roles.yaml`.

### Task M5: Review queue (Fri afternoon, ~3 h)

Plain words: a person confirms or overrides every verdict; both the tool's and the person's are kept.

**Files:** Create `apps/web/src/app/review/page.tsx`, `components/ReviewForm.tsx`.

Behaviour: one form per claim showing the tool's verdict and the key number; radio **Accept** / **Override** (override reveals a verdict select and a required reason); reviewer role select (from `getRoles()`); saving calls `setReview(claim.id, review)`; progress "2 of 3 reviewed"; **Continue to decision** disabled until every claim has a review, with the reason shown as text next to the disabled button ("1 claim still needs a review"). Reviews survive navigating between pages.

- [ ] Steps: build; check the gate (disabled → enabled after the third review); lint/typecheck/build; commit `feat: review queue with gate`.

### Task M6: Decision screen and downloads (Sat morning, ~2 h)

**Files:** Create `apps/web/src/app/decision/page.tsx`, `components/DecisionPanel.tsx`.

Behaviour: calls `suggestDecision(audit)` on load; shows the suggested decision, its rule, reasons, who must sign off, and "What would change this decision"; the reviewer picks one of the four decisions (default = suggestion), writes a reason, chooses a role; **Export** calls `exportAudit`, then offers two downloads: `audit.json` and `decision_record.md`. API 422 messages show inline. `RoleSummary` (M4) is the page header. Another conflict case: if a claim's review overrides the machine verdict, show both side by side with a "Resolved by <role>" line.

- [ ] Steps: build; run the whole flow with the practice report; the downloaded `audit.json` passes `python docs/challenge/format/validate.py audit.json`; lint/typecheck/build; commit `feat: decision screen and exports`.

### Task M7: README, licenses, video (Sat morning, ~2 h)

**Files:** Modify `README.md`; Create `THIRD_PARTY.md`, `LICENSE`.

- [ ] README top: one-paragraph summary, the user (a reviewer asked "can we trust this report?") and the one workflow, team members, three-command setup, how to run on an envelope (`python envelopes/unseal.py <num> <four words>` then the CLI or the web app pointing at `envelopes/opened/<E>/release/`), the demo video link, **limitations** (only subtype calls for 844 of 1,101 primary tumors; no treatment data; RNA file absent in envelope releases), data credits (TCGA Research Network, UCSC Xena, NCI IDC). Remove any sentence that sounds clinical.
- [ ] `THIRD_PARTY.md`: every library in `pyproject.toml` and `apps/web/package.json` with its license. `LICENSE`: the team's chosen license (agree it with the group first).
- [ ] Record the 3-minute video from the script below, upload it, put the link at the top of the README.
- [ ] Commit `docs: README, third-party list, license`.

**Demo script (3 minutes):** 0:00 start screen, "Reviewers get reports like this and must decide: can we publish it?" · 0:20 upload the practice report, board appears, "one supported, one wrong, one the data can't answer" · 0:50 open the 62% claim, evidence panel, "the report said 62%; it's 49.9%, 421 of 844, and never 62% however you count it; here is the code and the sample IDs" · 1:40 open the hormone-therapy claim, "no treatment data, so we don't guess; here's what data would be needed" · 2:10 switch role to Program leader, "same facts, simpler view; the tool suggests Fix a problem" · 2:40 export `audit.json` and the Decision Record, "validated, with who must sign off. Research prototype, never a clinical decision."

---

# Everyone: shared milestones

| When | Milestone | Who |
| --- | --- | --- |
| Thu night | A1 on `main`; A2–A4 give the three practice verdicts; **Checkpoint 1 posted in Discord** | Allen (A1–A4); Benoy B1, B3; Akshaya K1; Meghana M1 |
| Fri morning | Pipeline + `/audit` + CLI (A5); claim typing (B2, B4); start screen and claims list (K2, K3); `audit.json` export validates (M2) | all |
| Fri afternoon | Robustness (A7), skeptic (B5), ladder (B6), board + evidence panel (K4, K5), roles + review queue (M4, M5) | all |
| Fri evening | **Checkpoint 2: repo swap with the paired team.** Each of us follows only the README on a fresh clone; fix everything they trip on. Benoy's own reports run (B7); Allen fixes mismatches | all |
| Sat 10:00–2:15 | Decision screen (M6), README and video (M7), accessibility (K6), integration and rehearsal (A8): unseal the practice envelope, run, export, in under 2 minutes, three times in a row. **Code freeze 2:15 PM** | all |

### Final submission checklist (Allen runs it with Meghana, Sat before 2:15)

- [ ] Public repo, submitted commit = the one we demo; no secrets (`gitleaks detect`), no raw TCGA files, `envelopes/opened/` ignored.
- [ ] README names the product, track, user, workflow, team; setup works from a fresh clone on another machine.
- [ ] `audit.json` from the practice envelope passes `docs/challenge/format/validate.py`.
- [ ] One result is traceable to samples, file and code in the UI; one limitation is visible in the UI; human review gate works; research-only banner on every screen.
- [ ] Demo video link in the README; `THIRD_PARTY.md` and `LICENSE` present.
- [ ] `npm test`, `npm run lint`, `npm run typecheck`, `npm run build` all pass.
