// Which entry the Review page has open (the Overview or one claim), how it maps to the URL hash, and where
// "Save and next" and "Previous" go. Pure functions: no React, no window.

import { finalVerdict, VERDICT_LABEL } from "./review";
import type { ClaimResult } from "./types";

export const OVERVIEW = "overview";

/** `OVERVIEW` or a claim id. */
export type Entry = string;

/** The hash fragment that names a claim on the Review page. */
export function claimAnchor(id: string): string {
  return `review-${id}`;
}

/** The entry a hash names; Overview for no hash, another fragment, or an id this audit does not have. */
export function entryFromHash(hash: string, ids: string[]): Entry {
  const prefix = `#${claimAnchor("")}`;
  if (!hash.startsWith(prefix)) return OVERVIEW;
  const id = decodeURIComponent(hash.slice(prefix.length));
  return ids.includes(id) ? id : OVERVIEW;
}

export function hashFor(entry: Entry): string {
  return entry === OVERVIEW ? "" : `#${claimAnchor(entry)}`;
}

/**
 * The first claim still to review after `after` in list order, wrapping round; Overview when none is left.
 * Never `after` itself: it is called just after `after` was saved, before `claims` shows that review.
 */
export function nextToReview(claims: ClaimResult[], after: Entry): Entry {
  const start = claims.findIndex((c) => c.claim.id === after);
  for (let step = 1; step <= claims.length; step++) {
    const c = claims[(start + step) % claims.length];
    if (c.claim.id !== after && c.review === null) return c.claim.id;
  }
  return OVERVIEW;
}

/** The claim before `current`, or Overview from the first claim. */
export function previousEntry(ids: string[], current: Entry): Entry {
  const i = ids.indexOf(current);
  return i > 0 ? ids[i - 1] : OVERVIEW;
}

/** "to review", "accepted" or "overridden to Supported". */
export function reviewStatus(result: ClaimResult): string {
  if (!result.review) return "to review";
  if (result.review.decision === "accept") return "accepted";
  return `overridden to ${VERDICT_LABEL[finalVerdict(result)]}`;
}
