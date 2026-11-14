# Review Three-Column Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Review page becomes a claim list beside one open entry (Overview or a claim), with Save and next.

**Architecture:** Pure navigation helpers in `lib/review-nav.ts` (tested); a hash-synced selection hook; a
`ReviewList` component for the left column; the page composes list + selected entry. `ReviewForm` gains a save
callback and label. Claim rows, overviews, narration and the gate keep their behaviour.

**Tech Stack:** Next.js 16 / React 19 / Tailwind 4 in `apps/web`, vitest 3.

**Spec:** `docs/superpowers/specs/2026-11-14-review-three-column-design.md`

## Global Constraints

- At `lg`+: left column about 30% (title, role picker, verdict stack bar + counts, "n of m reviewed", list, gate); right column the selected entry, sticky.
- List entries: **Overview** first, then each claim: id, verdict, status ("accepted" / "overridden to …" / "to review"), start of its text.
- Selection lives in the URL hash as `#review-<id>` (`claimAnchor`); no hash or an unknown id means Overview.
- Overview ends with "Start reviewing →"; a claim ends with "← Previous" and the form's "Save and next →".
- Below `lg`: one column, list first; choosing an entry scrolls it into view.
- Do not touch `AppShell.tsx` or `layout.tsx` (another session's uncommitted work). Audit board unchanged.
- Stage only files this plan names.

## Review Focus

1. A hash naming an id not in this audit (an old link after a new audit) opens Overview, not a blank pane.
2. Saving the last unreviewed claim opens Overview and enables "Continue to decision".
3. "Save and next" on an already-reviewed claim goes to the next claim still to review, wrapping past the end.
4. An audit with no claims shows Overview and "The report had no claims to review." — no empty claim pane.
5. Switching role keeps the selected entry.

---

### Task 1: Navigation helpers

**Files:**
- Create: `apps/web/src/lib/review-nav.ts`, `apps/web/src/lib/review-nav.test.ts`

**Interfaces:**
- Produces:
  - `OVERVIEW = "overview"`; `type Entry = string` (`OVERVIEW` or a claim id)
  - `entryFromHash(hash: string, ids: string[]): Entry`
  - `hashFor(entry: Entry): string` — `""` for Overview, else `#${claimAnchor(id)}`
  - `nextToReview(claims: ClaimResult[], after: Entry): Entry` — first unreviewed claim after `after` in list order, wrapping, never `after` itself; `OVERVIEW` when none
  - `previousEntry(ids: string[], current: Entry): Entry` — the claim before, or `OVERVIEW` from the first claim
  - `reviewStatus(result: ClaimResult): string` — `"to review"`, `"accepted"`, or `"overridden to <VERDICT_LABEL>"`

- [ ] **Step 1: Write the failing tests** (`review-nav.test.ts`, fixture claims C1..C3 built like `insights.test.ts`'s `result()`; `review` set where noted)

```ts
it("reads the selected claim from the hash, Overview otherwise", () => {
  expect(entryFromHash("#review-C2", ["C1", "C2"])).toBe("C2");
  expect(entryFromHash("", ["C1"])).toBe(OVERVIEW);
  expect(entryFromHash("#review-C9", ["C1", "C2"])).toBe(OVERVIEW); // Review Focus 1
  expect(entryFromHash("#elsewhere", ["C1"])).toBe(OVERVIEW);
});
it("writes the hash back", () => {
  expect(hashFor(OVERVIEW)).toBe("");
  expect(hashFor("C2")).toBe("#review-C2");
});
it("goes to the next claim still to review, wrapping", () => {
  // C1 reviewed, C2 and C3 not
  expect(nextToReview(claims, OVERVIEW)).toBe("C2");
  expect(nextToReview(claims, "C2")).toBe("C3");
  expect(nextToReview(claims, "C3")).toBe("C2"); // Review Focus 3: wraps
  expect(nextToReview(claims, "C1")).toBe("C2");
});
it("opens Overview when every claim is reviewed", () => {
  expect(nextToReview(allReviewed, "C3")).toBe(OVERVIEW); // Review Focus 2
  expect(nextToReview([], OVERVIEW)).toBe(OVERVIEW); // Review Focus 4
});
it("steps back to the previous claim, then Overview", () => {
  expect(previousEntry(["C1", "C2"], "C2")).toBe("C1");
  expect(previousEntry(["C1", "C2"], "C1")).toBe(OVERVIEW);
});
it("words a claim's review status", () => {
  expect(reviewStatus(unreviewed)).toBe("to review");
  expect(reviewStatus(accepted)).toBe("accepted");
  expect(reviewStatus(overriddenToSupported)).toBe("overridden to Supported");
});
```

(`nextToReview(claims, after)` never returns `after` itself: it is called right after `after` was saved, while `claims` may still show it unreviewed. Add `expect(nextToReview(onlyC3Unreviewed, "C3")).toBe(OVERVIEW)`.)

- [ ] **Step 2:** `cd apps/web && npx vitest run src/lib/review-nav.test.ts` — FAIL, module not found.
- [ ] **Step 3:** Implement `lib/review-nav.ts` (`claimAnchor` imported from `components/review/ChecklistOverview`; `VERDICT_LABEL` from `lib/review`).
- [ ] **Step 4:** Same command — PASS.
- [ ] **Step 5:** Commit both files: `feat(web): review navigation helpers`.

### Task 2: The two-column page

**Files:**
- Create: `apps/web/src/components/review/ReviewList.tsx`, `apps/web/src/lib/use-review-selection.ts`
- Modify: `apps/web/src/app/review/page.tsx`, `apps/web/src/components/ReviewForm.tsx`

**Interfaces:**
- Consumes: Task 1 helpers.
- Produces:
  - `useReviewSelection(ids: string[]): [Entry, (e: Entry) => void]` — state initialised from `location.hash` after mount, kept in step with `hashchange`; setting it writes the hash with `history.pushState` (so back/forward walk entries) and is a no-op for the current entry.
  - `ReviewList({ claims, selected, onSelect })` — `<ol>` of buttons (`aria-current="true"` on the selected one); Overview first; each claim shows a verdict dot (`bg-supported` / `bg-contradicted` / `bg-insufficient`), mono id, `VERDICT_LABEL[finalVerdict]`, `reviewStatus`, and the claim text truncated to one line.
  - `ReviewForm` props gain `onSaved?: () => void` (called after a successful save) and `saveLabel?: string` (replaces "Save review" / "Update review" when given; the button stays enabled when there is nothing to change, so it can move on).

- [ ] **Step 1:** `ReviewForm`: add the two props as described; nothing else changes.
- [ ] **Step 2:** `use-review-selection.ts` as described (client only; `ids` change → re-validate the current entry with `entryFromHash`).
- [ ] **Step 3:** `ReviewList.tsx` as described.
- [ ] **Step 4:** `page.tsx`: wrapper drops `pageWidth`'s `max-w-4xl` for `mx-auto w-full max-w-7xl px-5 py-8 sm:px-8`; grid `lg:grid-cols-[minmax(17rem,30%)_minmax(0,1fr)] lg:gap-8`.
  - Left: breadcrumb, title, one-line intro, `RolePicker`, `Counts`-style stack bar with counts, the existing progress bar, `ReviewList`, the gate (existing markup).
  - Right (`lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:overflow-y-auto`, `<section aria-label>` with `tabIndex={-1}`, focused after a list click):
    - Overview: `ReviewOverview` (unchanged), then a primary "Start reviewing →" button → `nextToReview(claims, OVERVIEW)`; hidden when that is Overview; with no claims the existing "The report had no claims to review." line instead.
    - A claim: `ReviewForm key={id}` with the `ClaimBody`, `saveLabel="Save and next →"`, `onSaved` → `nextToReview(claims, id)`; under it a quiet "← Previous" → `previousEntry`.
  - Below `lg`, after a selection, `scrollIntoView` the right section.
  - The checklist overview's chips already link `#review-<id>`: they now select through the hook.
- [ ] **Step 5:** `cd apps/web && npx tsc --noEmit -p . && npm run lint && npx vitest run` — clean.
- [ ] **Step 6:** Commit the four files: `feat(web): review as a claim list beside one open claim`.

### Task 3: Check it in the app, then docs

**Files:**
- Modify: `README.md` (the Review step and **Role views** paragraphs)

- [ ] **Step 1:** Practice audit → `/review` at 1280×800. Check, in this order: opens on Overview; "Start reviewing" opens the first unreviewed claim; Save and next walks C1 → C2 → C3 → Overview; gate enables after the last; reload keeps the selection; back button returns to the previous entry; `#review-C9` opens Overview; switching role keeps the entry; at 390px wide the list comes first and a tap scrolls to the claim.
- [ ] **Step 2:** Screenshots `.playwright-mcp/three-col-overview.png`, `three-col-claim.png`, `three-col-phone.png`; look at each.
- [ ] **Step 3:** README: the Review step reads as a list beside one open claim with Save and next.
- [ ] **Step 4:** Commit README and the spec/plan docs: `docs: review list layout`.
