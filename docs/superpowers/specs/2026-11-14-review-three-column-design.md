# Review page: claim list + one claim at a time

Date: 2026-11-14 · Status: owner picked option A from two mockups; short design awaiting approval

## Intent

The Review page is one long scroll: overview, then every claim row with its evidence and form. Even after the
per-row layout work, a 3-claim audit is about 3,300px and a 15-claim report would be very long. The owner wants a
three-column layout (steps rail, then two columns) that conveys the audit more clearly. From two mockups they chose
**A: a claim list beside one open claim**.

## Goals

- At `lg` and wider, the Review page's content area is two columns beside the existing steps rail:
  - **Left (about 30%)**: page title, role picker, a compact summary (verdict stack bar with counts, "n of m reviewed"
    progress), the list of entries, and the "Continue to decision" gate.
  - **Right (the rest)**: the selected entry only.
- The list's first entry is **Overview** (the role's existing overview panel, unchanged); then one entry per claim with
  its id, verdict, review status ("accepted", "overridden to …", "to review") and the start of its text.
- Selecting an entry shows it on the right. A claim shows its existing row (answer, one chart, folds, review form).
- Flow: the page opens on Overview, which ends with "Start reviewing →" (first claim not yet reviewed). Each claim ends
  with **Previous**, and the form's save becomes **Save and next →**, which saves and opens the next claim not yet
  reviewed (or Overview when none is left).
- The selection is in the URL hash (`#review-C2`, the existing `claimAnchor`), so reload, back/forward and the
  checklist overview's "Go to a claim" chips select instead of scroll.
- Below `lg`: one column — summary and list first, then the selected entry; choosing an entry scrolls to it.

## Non-goals

- The steps rail is not resized now: it lives in `AppShell.tsx`, which another session has created and not committed.
  Taking it to 15% is a one-line change once that work lands.
- The Audit board keeps its layout.
- No change to what a claim row, the overviews, the narration or the review gate contain or do.

## Approaches

- **A. List + one claim (chosen by the owner).** Page length no longer grows with the report; review becomes a walk
  through the list. Cost: claims cannot be compared by scrolling.
- **B. Long list + review panel that stays on screen.** Smaller change, keeps scrolling; does not fix length.

## Builder calls

- Overview is the first entry and the default, rather than a separate column: the evidence and raw overviews are
  wide tables that do not fit a 30% column.
- The right column is sticky at `lg` (it scrolls on its own) so the list stays in view.
- `ReviewForm` gets an optional `onSaved` callback and a `saveLabel`; it is keyed by claim id so its draft resets per
  claim. Its behaviour (override needs a reason, both verdicts kept) is unchanged.
- The page drops the `max-w-4xl` page width so both columns get room (capped by the shell's existing max width).
- Keyboard: the list is a list of buttons with `aria-current` on the selected entry; the right column is a labelled
  region that takes focus after a selection made from the list.
