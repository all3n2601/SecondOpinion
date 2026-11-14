// A claim the coverage gate held back (`coverage_gaps` set): the data could answer it, but the rules did not read
// every part of the sentence. It is worded as "not fully read", never as data the release lacks.

import type { Claim, ClaimResult } from "./types";

export const NOT_FULLY_READ = "Not fully read";

export function notFullyRead(claim: Claim): boolean {
  return (claim.coverage_gaps?.length ?? 0) > 0;
}

/** "The rules could not read every part of this sentence, so it was not checked: this sentence also states …". */
export function notFullyReadText(result: ClaimResult): string {
  const why = (result.missing_evidence ?? result.claim.needed_data ?? "").replace(/[.\s]+$/, "");
  return `The rules could not read every part of this sentence, so it was not checked${why ? `: ${why}` : ""}.`;
}

/** Before the audit: `Not fully read: the rules could not check "N0", "15"; a person should check it`. */
export function notFullyReadParams(claim: Claim): string {
  const words = (claim.coverage_gaps ?? []).map((w) => `"${w}"`).join(", ");
  return `${NOT_FULLY_READ}: the rules could not check ${words}; a person should check it`;
}
