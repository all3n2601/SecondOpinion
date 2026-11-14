# Role-aware Review page

Date: 2026-11-14 · Status: approved design, ready to plan

## Intent

The Review page (`/review`) has a "Viewing as" role picker with four roles (Program leader, Data-use reviewer,
Researcher, Data engineer), but picking a role changes nothing on that page: everyone sees the same
Accept / Override ledger. A program leader does not read what a data engineer reads. The page should present the
same audit at each viewer's level: a plain-language story with simple visuals for people with little code
background, rising to raw numbers, sample IDs and code for the technical roles. An optional AI helper writes the
story and caption text for each view.

## Goals

- Each role sees a view matched to its audience, on the Review page:
  - **Program leader → `story`**: plain-language headline, one simple "how many claims held up" visual, a short
    story sentence per claim. No jargon, no code, no sample IDs.
  - **Data-use reviewer → `checklist`**: verdict breakdown plus review progress; each claim shows "what the report
    says vs. what the data says".
  - **Researcher → `evidence`**: robustness (how many ways of counting agree), skeptic tests, corrected wording.
  - **Data engineer → `raw`**: dense table of counts, sample IDs, file checksums, the code behind each check.
- Every role still reviews every claim (Accept / Override with reason). The "all claims reviewed before decision"
  gate is unchanged.
- The AI helper writes story/caption prose. Every number on screen comes from deterministic code, never from the
  model.
- With the AI off or failing, every view still works, using built-in template text.
- Roles added through the "Add a role" form pick one of the four views, so new roles get a real view too.

## Non-goals

- The Decision page's `RoleSummary` stays as it is.
- No change to how claims are checked, verdicts, or the export / Decision Record format.
- No per-visit variation: "fresh" means fitted to the audience, not different on each visit.
- No charting library.

## Anti-goals (would be a failure even if it works)

- A number on screen that the model produced or could have altered.
- The model receiving any data value (counts, correct values, sample IDs, checksums). The project's AI rule is that
  the model sees only the report text and schema, never data; this feature keeps that rule.
- A role that cannot review, or a view that hides the Accept / Override form.
- The page being blank, broken or stuck "loading" when the AI is off, slow or wrong.

## Constraints

- Stack: Next.js app in `apps/web` (Tailwind, lucide icons, existing tokens in `lib/ui.ts`), FastAPI in
  `apps/api`, logic in the `second_opinion` package. AI client: `second_opinion/ai/client.py`
  (`make_client()` → `ChatClient.complete_json`, OpenAI-compatible, optional, configured from `.env`).
- Audit state is client-side (`lib/audit-context.tsx`, persisted to sessionStorage by `lib/persist.ts`).
- Audits are small (about 5–20 claims), so hand-drawn SVG/HTML visuals are enough.
- Accessibility pass already done on this app; new visuals need text equivalents (aria labels or a visible
  number next to every bar).

## Approaches considered

- **A. Per-role preset view around the same review ledger, AI writes slotted prose (chosen).** Each role maps to
  one of four view presets in `roles.yaml`; the page shows a role-specific overview panel plus role-specific claim
  rows, all keeping Accept / Override. The AI writes text containing named blanks; code fills the blanks. Chosen
  because it fits each audience, keeps the "never guess" promise, and works with the AI off.
- **B. AI also chooses the layout.** Same building blocks, but the model picks panels and order per role. More
  "AI" for a demo, but unpredictable and dependent on the AI being on. Can sit on top of A later.
- **C. Fixed views, no AI.** Simplest, but drops the AI help the user asked for.

## Design

### 1. Role → view preset

- `Role` gains `view: "story" | "checklist" | "evidence" | "raw"` in `second_opinion/roles.py`
  (`VALID_VIEWS`), in `roles.yaml`, in the web `Role` type and in the `/roles` API.
- A role in `roles.yaml` with no `view` gets one from its `detail`: `summary → story`, `standard → checklist`,
  `full → evidence`. The four shipped roles get explicit views: Program leader `story`, Data-use reviewer
  `checklist`, Researcher `evidence`, Data engineer `raw`.
- `validate_role` rejects an unknown view. `AddRoleForm` gets a "How it looks" select with the four views, each
  with a one-line plain description; default `checklist`.
- An unknown role name in state (e.g. a stale stored role) falls back to `checklist`.

### 2. Review page layout

```
Breadcrumb · title · intro (intro sentence also varies by view)
Viewing as [role ▾]
┌ Overview panel (per view) ───────────────────────────┐
│ headline / caption (AI or template)                 │
│ visual                                               │
└──────────────────────────────────────────────────────┘
progress bar  "4 of 7 reviewed"        (unchanged, all views)
┌ Claim rows ──────────────────────────────────────────┐
│ per-view claim body                                  │
│ Accept / Override form (unchanged behaviour)         │
└──────────────────────────────────────────────────────┘
Continue to decision (gate unchanged)
```

Overview panel per view:

| View | Overview | Claim row body (above the form) |
|---|---|---|
| story | Headline sentence; one stacked bar "held up / wrong / can't tell" with counts as words ("5 held up, 2 were wrong") | Claim in quotes (report text), then one plain story sentence ("The report says about 62% of patients…; the data shows 48%."). No ids shown except a small claim number. |
| checklist | Verdict counts (existing `VerdictBadge` style) + review progress; short caption | Verdict badge, claim text, report-says vs data-shows (reuse `ClaimVsData` where it fits) |
| evidence | Grid: claim × "ways of counting agree" (n of m) and skeptic result; caption | Corrected wording (ladder), robustness, flips_on, skeptic p-value and site flips |
| raw | Table: claim id, verdict, count, n sample IDs, layer/file; file checksums | Count text, sample IDs (all, collapsible), `fact.code` in a code block |

Existing rendering bits in `RoleSummary.tsx` (`Counts`, `corrected`, robustness/skeptic/sample/code sections) should
be pulled out and shared rather than duplicated.

### 3. AI prose with named blanks

- New endpoint `POST /ai/narrate`. Request: `view` and, per claim, only `id`, final verdict (`finalVerdict`, so
  overrides count), `solidity`, whether it was overridden, and the claim's report text (already sent to the model
  during extraction). Counts and data values are **not** sent; the model only knows which slot names exist.
- The model returns JSON: `headline`, `caption`, and `claims: {id: sentence}`. Every quantity, count and
  direction goes through a named slot that code fills:
  - audit level: `{supported}`, `{contradicted}`, `{insufficient}`, `{total}`, `{reviewed}`, `{fragile}`
  - per claim: `{stated}`, `{data_shows}`, `{direction}` (code-computed "higher than" / "lower than" / "the same as"
    the stated figure), `{agree}`, `{ways}`
- Server-side validation (new module `second_opinion/ai/narrate.py`) rejects the whole response if any text:
  - contains a standalone number (digits, `%`, decimals) outside a slot. Tokens that mix letters and digits
    (HER2, TP53, PAM50) are allowed only if they appear word for word in that claim's report text (or, for the
    headline/caption, in any claim's text). They are names, not values.
  - contains a number word or quantity word (`one`…`twenty`, `half`, `dozen`, `none`, `all`, `every`, `most`,
    `majority`, `few`, `several`, `many`) or a comparison word (`higher`, `lower`, `more`, `fewer`, `less`, `above`,
    `below`, `over`, `under`, `exceeds`). Counts and directions must come from slots.
  - uses an unknown slot, uses a per-claim slot in the headline/caption, misses a claim, or exceeds a length cap
    (headline ≤ 160 chars, caption ≤ 200, claim sentence ≤ 220).
  - One correction retry naming the problems, as the planner does; then the endpoint reports the AI as unavailable.
- **Templates live in the web client only** (`lib/narrate.ts`), one per view, in the same slotted shape. The page
  renders template text immediately with no network wait. The endpoint returns
  `{source: "ai", headline, caption, claims}` or `{source: "template", reason}`. On `"template"` (AI off,
  failed, or rejected) the client keeps its own templates. Python never holds template text.
- `lib/narrate.ts` fills slots from the audit, formatting numbers the same way the rest of the app does. Where a
  claim has no value for a slot the AI used (e.g. `{data_shows}` on an insufficient-evidence claim, or a
  multi-part claim with no single stated value), that claim shows its template sentence instead; other claims keep
  their AI text.
- Text shown from the AI carries the existing `AiStamp` marker so viewers know the wording was AI-written.
- Caching: the result is kept in audit context keyed by `role view + claim ids + verdicts`, persisted with the rest
  of the state, so switching roles back and forth or reloading does not call the model again. An override changes
  the key for that view, so the prose is refreshed.
- Loading: the view renders at once with template text, then swaps in AI text when it arrives (no spinner blocking
  the review form).

### 4. Tests

- Python: `roles.py` view default + validation; `narrate.py` validation (standalone number, number/quantity word,
  comparison word, letter-digit token allowed only when in the claim text, unknown slot, misplaced slot, missing
  claim, length), retry then `"template"`, using `ScriptedClient`; API test for `/ai/narrate` with AI off and with
  a scripted client.
- Web: `apps/web` has no test runner today; add a minimal one (Node's built-in `node --test` with type stripping,
  or vitest) for `lib/narrate.ts`: template output per view, slot filling, per-claim fallback when a slot has no
  value. Typecheck and lint pass.

### 5. Builder calls made during review (owner may revisit)

- The AI text check is strict: number words, quantity words and comparison words are rejected. Direction comes
  from a code-filled `{direction}` slot. This means AI text is less colourful but never states a count or direction
  it was not given.
- Letter-digit names (HER2, PAM50) are allowed when copied from the claim's own report text.
- Templates live only in the web client, so the page never waits on the network to show text.
- Counts and prose use the final verdict (after overrides).
- `ReviewForm` is split into a per-view claim body and the unchanged Accept / Override form.

## Left to the builder

- Exact template wording per view (plain language for `story`), and exact visual styling within the existing
  design tokens.
- Prompt wording for the narrate call.
- How to factor shared section renderers out of `RoleSummary.tsx`.
- Whether the slot list needs another entry once real claims are rendered; any new slot must hold a
  code-computed value.
