# Role-aware Review Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Review page shows each role its own view (story / checklist / evidence / raw), with AI-written prose whose numbers are always filled in by code.

**Architecture:** Roles gain a `view` preset in `roles.yaml`. The web Review page renders a per-view overview panel and per-view claim body around the unchanged Accept / Override form. Prose comes from slotted templates in the web client; an optional `POST /ai/narrate` returns AI prose in the same slotted shape, which a strict Python validator checks before it reaches the browser.

**Tech Stack:** FastAPI + pydantic, `second_opinion` package (pytest), Next.js 16 / React 19 / Tailwind 4 (`apps/web`), vitest for web unit tests.

**Spec:** `docs/superpowers/specs/2026-11-14-role-aware-review-design.md`

## Global Constraints

- Views: exactly `story`, `checklist`, `evidence`, `raw`. Default from detail: `summary → story`, `standard → checklist`, `full → evidence`. Shipped roles: Program leader `story`, Data-use reviewer `checklist`, Researcher `evidence`, Data engineer `raw`. Unknown role name in the browser → `checklist`.
- The model never receives a data value: only `view`, and per claim `id`, final verdict, `solidity`, `overridden`, report `text`.
- Audit slots: `{supported}`, `{contradicted}`, `{insufficient}`, `{total}`, `{reviewed}`, `{fragile}`. Claim slots: `{stated}`, `{data_shows}`, `{direction}`, `{agree}`, `{ways}`. Claim slots are not allowed in headline/caption.
- Rejected words (whole word, case-insensitive): `one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty half dozen none all every most majority few several many higher lower more fewer less above below over under exceeds`.
- Length caps: headline ≤ 160 chars, caption ≤ 200, claim sentence ≤ 220 (measured on the slotted text).
- Letter+digit tokens (HER2, PAM50) allowed only if they appear in that claim's text (headline/caption: any claim's text), case-insensitive.
- Templates live only in `apps/web/src/lib/narrate.ts`. `/ai/narrate` always answers 200 with `{source: "ai", headline, caption, claims}` or `{source: "template", reason}`.
- Counts and prose use `finalVerdict()` (after overrides). Every role keeps Accept / Override; the "all reviewed" gate is unchanged.
- AI-written text carries an AI marker (extend `components/AiStamp.tsx`).
- No charting library. Every bar has its number visible next to it or an aria label.
- `second_opinion/roles.yaml` currently has uncommitted edits (a "Test" role, header comment stripped) that are not part of this work. Do not stage them; ask the user before Task 1 whether to restore the file.

## Review Focus

1. **Audit with zero claims** — overview panels and templates must not divide by zero or render an empty bar; story headline reads naturally. Test in Task 3 (`templateFor` with `[]`) and Task 7 manual check.
2. **Override after prose was fetched** — the narration key includes final verdicts, so overriding a claim refetches and never shows prose written for the old verdict. Test in Task 3 (`narrationKey` changes on override) and Task 5.
3. **AI answer with wrong claim ids** (missing, extra, renamed) — rejected, falls back to template. Test in Task 2.
4. **Multi-part claim or insufficient-evidence claim where the AI used `{data_shows}`** — that claim alone shows its template sentence, others keep AI text. Test in Task 3.
5. **Role added from an older `roles.yaml` with no `view`, or a stored role name that no longer exists** — derived view / `checklist`, page never blank. Tests in Task 1 and Task 4.

---

### Task 1: Role `view` field (Python + API)

**Files:**
- Modify: `second_opinion/roles.py`
- Modify: `second_opinion/roles.yaml` (add `view:` to the four shipped roles; header comment documents `view`)
- Test: `tests/test_roles.py`

**Interfaces:**
- Produces: `VALID_VIEWS: tuple[str, ...] = ("story", "checklist", "evidence", "raw")`; `VIEW_FOR_DETAIL: dict[str, str]`; `Role.view: Literal["story","checklist","evidence","raw"] | None = None` as the **last** dataclass field (positional construction in existing tests keeps working). `load_roles` and `validate_role` always return roles with `view` set. `GET/POST /roles` include `view`.

- [ ] **Step 1: Write the failing tests** in `tests/test_roles.py`:
  - update `test_four_default_roles_load`: `got["Program leader"] == Role("Program leader", ["decision","counts","sign_off"], "summary", True, "story")`, and views of the other three are `checklist`, `evidence`, `raw`.
  - `test_missing_view_comes_from_detail(tmp_path)`: yaml with roles of detail summary/standard/full and no `view` → views `story`/`checklist`/`evidence`.
  - `test_unknown_view_is_rejected(roles_file)`: `add_role(Role("X", ["code"], "full", False, "fancy"))` raises `ValueError` whose message contains `"story, checklist, evidence, raw"`.
  - `test_added_role_without_view_gets_one(roles_file)`: `add_role(Role("Y", ["code"], "summary", False))[-1].view == "story"`, and it survives `load_roles`.
  - extend `test_api_round_trip`: posted role with `"view": "raw"` comes back with `"view": "raw"`; `GET /roles` items all have a `view` key.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_roles.py -v` → new tests FAIL.
- [ ] **Step 3: Implement** in `second_opinion/roles.py`: constants above; `load_roles` reads `r.get("view") or VIEW_FOR_DETAIL[detail]`; `validate_role` fills a missing view the same way and rejects one not in `VALID_VIEWS` with `f"View must be one of: {', '.join(VALID_VIEWS)}."`; `add_role` header comment mentions `view`. Add explicit `view:` lines to the shipped roles in `roles.yaml`.
- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_roles.py tests/test_api.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: roles carry a view preset (story, checklist, evidence, raw)` (stage only `roles.py`, the `view` lines of `roles.yaml` per the user's answer, and the test).

### Task 2: Narration validator and `POST /ai/narrate`

**Files:**
- Create: `second_opinion/ai/narrate.py`
- Modify: `apps/api/app/routes/ai.py`
- Test: `tests/test_ai_narrate.py`

**Interfaces:**
- Consumes: `ChatClient`, `AIError`, `make_client`, `ScriptedClient` from `second_opinion/ai/client.py`.
- Produces:
  - `AUDIT_SLOTS: frozenset[str]`, `CLAIM_SLOTS: frozenset[str]`, `BANNED_WORDS: frozenset[str]` (values from Global Constraints).
  - `@dataclass(frozen=True) class NarrateClaim: id: str; verdict: str; solidity: str; overridden: bool; text: str`
  - `@dataclass(frozen=True) class Narration: headline: str; caption: str; claims: dict[str, str]`
  - `class NarrateError(AIError)`
  - `check_narration(data: dict, claims: list[NarrateClaim]) -> tuple[Narration | None, list[str]]` — problems as short plain strings naming the field (`"headline: ..."`, `"claims.C3: ..."`).
  - `build_prompt(view: str, claims: list[NarrateClaim]) -> tuple[str, str]` — system prompt states the view's audience (story: no jargon, plain words for someone without code background; checklist: reviewer; evidence: researcher; raw: engineer, terse), the slot list, the banned words, the caps, and JSON shape `{"headline","caption","claims":{id: sentence}}`.
  - `narrate(view: str, claims: list[NarrateClaim], client: ChatClient) -> Narration` — one correction round (same pattern as `plan_claim` in `second_opinion/ai/planner.py`: append "Your previous answer was rejected:" + problems), then `NarrateError("The AI wording did not pass the checks")`. `AIError` from the client propagates.
  - Route `POST /ai/narrate`: request `{view: Literal[4 views], claims: list[{id, verdict, solidity, overridden, text}]}` (max 100 claims, `text` max 2000 chars); response model `{source: Literal["ai","template"], headline: str|None, caption: str|None, claims: dict[str,str]|None, reason: str|None}`. `make_client()` is `None` → `source="template", reason="The AI helper is off"`; `AIError` (incl. `NarrateError`) → `source="template", reason=str(err)`. Never 5xx for AI trouble.

- [ ] **Step 1: Write failing tests** in `tests/test_ai_narrate.py` (helper `claims()` returns two `NarrateClaim`s: `C1` supported text `"About 62% of HER2-positive tumours were Luminal B."`, `C2` contradicted text `"Most samples came from site A."`):
  - `test_valid_answer_passes`: `{"headline": "{contradicted} of {total} claims did not hold up.", "caption": "...", "claims": {"C1": "The report says {stated}; the data agrees.", "C2": "The data shows {data_shows}, {direction} the report."}}` → Narration, no problems.
  - `test_digit_outside_slot_rejected`: headline `"2 of {total} claims failed."` → problem mentioning `headline`.
  - `test_percent_and_decimal_rejected`: claim sentence containing `"62%"` and one containing `"0.5"` → rejected.
  - `test_number_and_comparison_words_rejected`: parametrize over `"two"`, `"Most"`, `"none"`, `"lower"`, `"exceeds"` → rejected; `"someone"` and `"overall"` are **not** rejected (whole-word match).
  - `test_letter_digit_name_allowed_only_from_claim_text`: `"HER2"` in C1's sentence passes; `"TP53"` in C1's sentence is rejected; `"HER2"` in headline passes (it is in some claim's text).
  - `test_unknown_and_misplaced_slots_rejected`: `{foo}` anywhere → rejected; `{stated}` in headline → rejected.
  - `test_wrong_claim_ids_rejected`: missing `C2` → rejected; extra `C9` → rejected.
  - `test_length_caps`: headline of 161 chars rejected; claim sentence of 221 rejected; caption of 201 rejected.
  - `test_retry_then_success` and `test_retry_then_error` with `ScriptedClient([bad, good])` / `([bad, bad])`; assert second user prompt contains `"Your previous answer was rejected"`; second case raises `NarrateError`.
  - `test_prompt_carries_no_data_values`: `build_prompt` output contains claim ids and texts, and contains no key named `correct_value`, `fact`, `sample_ids`.
  - API: `test_narrate_endpoint_ai_off` (monkeypatch `apps.api.app.routes.ai.make_client` → `None`) → 200, `source == "template"`; `test_narrate_endpoint_ai_ok` with a scripted good answer → `source == "ai"`; `test_narrate_endpoint_ai_down` with `ScriptedClient([AIError("down")])` → `source == "template"`, `reason == "down"`; unknown view → 422.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_ai_narrate.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement** `narrate.py`. Check order per string: find `{name}` slots (`re.findall(r"\{(\w+)\}")`), check names; remove slots; then tokenize words (`re.findall(r"[A-Za-z0-9%.]+")`-style); a token containing a digit is allowed only if it has a letter and is in the allowed-names set; a token in `BANNED_WORDS` (lowercased, stripped of punctuation) is a problem. Then route in `ai.py`.
- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_ai_narrate.py tests/test_ai_client.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: AI narration endpoint with slot-only numbers`.

### Task 3: Web test runner and `lib/narrate.ts`

**Files:**
- Modify: `apps/web/package.json` (devDependency `vitest` pinned to `3.2.4`; script `"test": "vitest run"`), root `package.json` (`"test:web": "npm run test --workspace apps/web"`)
- Create: `apps/web/vitest.config.ts` (alias `@` → `./src`, environment `node`)
- Modify: `apps/web/src/lib/types.ts` (add `export type RoleView = "story" | "checklist" | "evidence" | "raw";`, `Role.view: RoleView`, `NarrateResponse`)
- Create: `apps/web/src/lib/narrate.ts`
- Test: `apps/web/src/lib/narrate.test.ts`

**Interfaces:**
- Consumes: `finalVerdict`, `formatCount` from `lib/review.ts`; `formatResultFact` from `lib/claim-format.ts`; `describeStated` from `lib/ai-plan.ts`.
- Produces:
  - `type Slotted = { headline: string; caption: string; claims: Record<string, string> }`
  - `interface NarrateResponse { source: "ai" | "template"; headline: string | null; caption: string | null; claims: Record<string, string> | null; reason: string | null }` (in `types.ts`)
  - `auditSlots(claims: ClaimResult[]): Record<string, string>` — counts by `finalVerdict`, `reviewed` = claims with a review, `fragile` = solidity `holds_under_some_variants`.
  - `claimSlots(result: ClaimResult): Record<string, string>` — keys only where a value exists: `stated` (from `ai_plan.stated` via `describeStated`, else `claim.params` with "about " hedge and `%` when unit is a percent; absent for claims with `parts`), `data_shows` (contradicted → `correct_value`; supported → `formatResultFact`; else absent), `direction` (`"higher than"` / `"lower than"` / `"the same as"` from `fact.value` vs `params.stated_value`, only when both are numbers and the claim type is `SHARE` or `COUNT`), `agree`/`ways` (count of `variants` whose verdict equals the claim's tool verdict / `variants.length`, only when `variants.length > 0`).
  - `fillSlots(text: string, values: Record<string, string>): string | null` — `null` if any slot in `text` has no value.
  - `templateFor(view: RoleView, claims: ClaimResult[]): Slotted` — per-claim sentence chosen by final verdict so it only uses slots that claim has (always succeeds with `fillSlots`).
  - `renderNarration(view: RoleView, claims: ClaimResult[], ai: Slotted | null): { headline: string; caption: string; claims: Record<string, { text: string; ai: boolean }>; ai: boolean }` — uses AI text where `fillSlots` succeeds, else the template text for that piece.
  - `narrationKey(view: RoleView, claims: ClaimResult[]): string` — view + each `id:finalVerdict`.

- [ ] **Step 1: Install and wire vitest**: `npm install -D vitest@3.2.4 --workspace apps/web`; add config and scripts. Run `npm run test:web` → "No test files found" (exit non-zero is fine at this step).
- [ ] **Step 2: Write failing tests** in `narrate.test.ts` with a small `result(overrides)` factory building a `ClaimResult`:
  - `fillSlots("{a} of {b}", {a: "2", b: "7"}) === "2 of 7"`; `fillSlots("{a}", {}) === null`.
  - `auditSlots` counts use the overridden verdict (a contradicted claim overridden to supported counts as supported).
  - `templateFor` for each of the four views on a mixed audit fills completely (every piece passes `fillSlots(…, slots) !== null`); `templateFor(view, [])` gives a headline with no `NaN`, `undefined` or `{`.
  - `renderNarration` with AI claim text `"The data shows {data_shows}."` for an insufficient-evidence claim → that claim's `ai === false` and text equals the template's; another claim keeps `ai === true`.
  - `claimSlots` for a claim with `parts` has no `stated` key.
  - `narrationKey` differs after an override changes a final verdict, and is equal for an override that keeps the verdict.
  - `direction` is `"lower than"` for a SHARE claim stated 62 with `fact.value` 48.
- [ ] **Step 3: Run** `npm run test:web` → FAIL.
- [ ] **Step 4: Implement** `narrate.ts`. Template copy is the builder's call; `story` uses plain words only (no "variant", "solidity", "skeptic", "PAM50"), `raw` is terse. Templates must themselves pass the Python rules (no banned words, no bare digits) so a reviewer sees one voice.
- [ ] **Step 5: Run** `npm run test:web && npm run typecheck` → PASS.
- [ ] **Step 6: Commit** `feat(web): slotted narration templates with vitest`.

### Task 4: Role views in the web app

**Files:**
- Modify: `apps/web/src/lib/roles.ts`
- Modify: `apps/web/src/components/AddRoleForm.tsx`
- Test: `apps/web/src/lib/roles.test.ts`

**Interfaces:**
- Consumes: `RoleView`, `Role.view` from Task 3.
- Produces: `ROLE_VIEWS: { id: RoleView; label: string; description: string }[]` (labels: "Story", "Checklist", "Evidence", "Raw data"; one-line plain descriptions); `viewFor(roles: Role[] | null, name: string): RoleView` (unknown name or `roles === null` → `"checklist"`). `useRoleView(): RoleView` hook combining `useAudit().role` and `useRoles()`.

- [ ] **Step 1: Write failing tests** in `roles.test.ts`: `viewFor(null, "Anyone") === "checklist"`; `viewFor(roles, "Program leader") === "story"`; `viewFor(roles, "Deleted role") === "checklist"`. (Import only pure exports; keep the hook in the same file but make sure the test does not render it.)
- [ ] **Step 2: Run** `npm run test:web` → FAIL.
- [ ] **Step 3: Implement** the exports, and in `AddRoleForm` a "How it looks" radio group from `ROLE_VIEWS` (default `checklist`), sent as `view` in `saveRole`.
- [ ] **Step 4: Run** `npm run test:web && npm run typecheck && npm run lint` → PASS.
- [ ] **Step 5: Commit** `feat(web): role view presets and view picker in Add a role`.

### Task 5: Fetching and caching AI prose

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/lib/use-narration.ts`
- Modify: `apps/web/src/lib/audit-context.tsx` (`reset` also clears the narration cache)
- Test: `apps/web/src/lib/use-narration.test.ts` (cache functions only)

**Interfaces:**
- Consumes: `narrationKey`, `renderNarration`, `Slotted` (Task 3); `finalVerdict`.
- Produces:
  - `narrate(view: RoleView, claims: ClaimResult[]): Promise<NarrateResponse>` in `api.ts` — sends only `{id, verdict: finalVerdict, solidity, overridden: review?.decision === "override", text: claim.text}` per claim.
  - `readCachedNarration(key: string): Slotted | null`, `writeCachedNarration(key: string, value: Slotted): void`, `clearNarrationCache(): void` — sessionStorage key `secondopinion:narration:v1`, every access in try/catch (same reasoning as `lib/persist.ts`: sessionStorage, never localStorage).
  - `useNarration(view: RoleView, claims: ClaimResult[] | null): ReturnType<typeof renderNarration> & { pending: boolean }` — renders template text immediately; fetches once per `narrationKey` when not cached; a template/failed response is not cached and not retried for the same key in this page session; never throws.

- [ ] **Step 1: Write failing tests**: write then read returns the value; `clearNarrationCache()` empties it; read with corrupt JSON in storage returns `null` (stub `globalThis.sessionStorage` with a Map-backed object).
- [ ] **Step 2: Run** `npm run test:web` → FAIL.
- [ ] **Step 3: Implement** the API call, cache helpers and hook (ignore stale responses whose key no longer matches).
- [ ] **Step 4: Run** `npm run test:web && npm run typecheck` → PASS.
- [ ] **Step 5: Commit** `feat(web): fetch and cache AI narration per role view`.

### Task 6: Shared section renderers

**Files:**
- Create: `apps/web/src/components/review/sections.tsx`
- Modify: `apps/web/src/components/RoleSummary.tsx`

**Interfaces:**
- Produces (moved out of `RoleSummary.tsx`, behaviour unchanged): `Counts({ claims }: { claims: ClaimResult[] })`, `CorrectedWording({ result })`, `RobustnessLine({ result, full }: { result: ClaimResult; full: boolean })`, `SkepticLine({ result })`, `SampleIds({ result, limit }: { result: ClaimResult; limit: number })`, `CodeFor({ result })`, `FileChecksums({ files }: { files: ReleaseInfo["files"] })`.

- [ ] **Step 1: Move** the renderers; `RoleSummary`'s `Section` switch calls them. No visual change on `/decision`.
- [ ] **Step 2: Run** `npm run typecheck && npm run lint` → PASS. Open `/decision` with the practice audit for all four roles; output identical to before.
- [ ] **Step 3: Commit** `refactor(web): share role section renderers`.

### Task 7: Per-view overview and claim bodies on `/review`

**Files:**
- Create: `apps/web/src/components/review/ReviewOverview.tsx` (switch on view), `StoryOverview.tsx`, `ChecklistOverview.tsx`, `EvidenceOverview.tsx`, `RawOverview.tsx`, `ClaimBody.tsx` (switch on view; four small bodies in one file)
- Modify: `apps/web/src/components/ReviewForm.tsx` — current verdict / key-number block moves into the checklist body; `ReviewForm` gains `body: ReactNode` rendered above the unchanged form
- Modify: `apps/web/src/components/AiStamp.tsx` — add `AiWordingStamp` ("Worded by the AI helper; numbers from our code")
- Modify: `apps/web/src/app/review/page.tsx` — `useRoleView()`, `useNarration()`, intro sentence per view, overview above progress bar, `ClaimBody` into each `ReviewForm`

**Interfaces:**
- Consumes: `useRoleView` (Task 4), `useNarration` (Task 5), section renderers (Task 6), `ClaimVsData` (existing), `AiWordingStamp`.
- Produces: `ReviewOverview({ view, audit, narration })`, `ClaimBody({ view, result, sentence }: { view: RoleView; result: ClaimResult; sentence: { text: string; ai: boolean } })`.

Content per view (from the spec table):
- **story**: headline + caption; one horizontal stacked bar held up / wrong / can't tell with the counts as visible text beside it; claim body = report text in quotes + story sentence; no ids beyond a small claim number, no code, no sample IDs.
- **checklist**: `Counts` + review progress + caption; claim body = previous ReviewForm header (badge, text, key number) + `ClaimVsData`.
- **evidence**: grid of claim × "n of m ways of counting agree" bar + skeptic result + caption; claim body = `CorrectedWording`, `RobustnessLine full`, `SkepticLine`.
- **raw**: table (claim id, final verdict, count text, sample count, files) + `FileChecksums`; claim body = count text, `SampleIds` (all, inside `<details>`), `CodeFor`.

- [ ] **Step 1: Build** the components and wire the page. AI marker shows next to headline/caption and on claim sentences where `ai === true`.
- [ ] **Step 2: Run** `npm run typecheck && npm run lint && npm run test:web` → PASS.
- [ ] **Step 3: Manual check** (app at http://localhost:3000, practice audit): switch "Viewing as" across all four roles on `/review`; each shows its overview and bodies; Accept/Override works in each; overriding a claim in `story` updates the bar and the sentence; with `SO_AI=off` the page shows template text and no AI marker; an audit with zero claims shows no broken bar.
- [ ] **Step 4: Commit** `feat(web): role-aware Review page views`.

### Task 8: Final verification

- [ ] **Step 1: Run** `npm test && npm run test:web && npm run lint && npm run typecheck` from the repo root → all PASS (paste counts in the handoff).
- [ ] **Step 2:** Update README's roles section with one line per view and the `view` key in `roles.yaml`. Commit `docs: role views`.
