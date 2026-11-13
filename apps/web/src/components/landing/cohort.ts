// The hero's cohort: one dot per sample in release A of TCGA-BRCA, sorted into the groups that decide the
// denominator of the practice report's Luminal A claim. The numbers come from the release (see
// second_opinion/checks/population.py and the audit of practice_brief.md); nothing here is made up.

export type Group = "lumA" | "lumB" | "basal" | "her2" | "normalLike" | "noCall" | "notPrimary";

/** Group sizes, in the order the dots are laid out (Luminal A first, so its share reads as area). */
export const GROUPS: { group: Group; count: number }[] = [
  { group: "lumA", count: 421 },
  { group: "lumB", count: 192 },
  { group: "basal", count: 141 },
  { group: "her2", count: 67 },
  { group: "normalLike", count: 23 },
  { group: "noCall", count: 257 }, // primary tumors with no RNA subtype call
  { group: "notPrimary", count: 146 }, // 139 normal tissue, 7 metastatic
];

export const TOTAL = GROUPS.reduce((sum, g) => sum + g.count, 0); // 1,247
export const WITH_CALL = 844;
export const LUM_A = 421;
/** What "about 62%" of the 844 would be: the report's own figure, applied to the right denominator. */
export const CLAIMED = Math.round(0.62 * WITH_CALL); // 523

export interface Stage {
  /** The number this stage is about, as shown. */
  figure: string;
  label: string;
  /** Groups still in the count at this stage. */
  keep: Group[];
  /** Highlight Luminal A among what is kept. */
  highlight: boolean;
  /** Ring the dots the report's figure would add beyond the real count. */
  showClaim: boolean;
}

const CALLED: Group[] = ["lumA", "lumB", "basal", "her2", "normalLike"];

export const STAGES: Stage[] = [
  {
    figure: "1,247",
    label: "samples in the release",
    keep: [...CALLED, "noCall", "notPrimary"],
    highlight: false,
    showClaim: false,
  },
  {
    figure: "1,101",
    label: "are primary tumors; 139 normal tissue and 7 metastatic samples set aside",
    keep: [...CALLED, "noCall"],
    highlight: false,
    showClaim: false,
  },
  {
    figure: "844",
    label: "primary tumors have an RNA subtype call; 257 have none",
    keep: CALLED,
    highlight: false,
    showClaim: false,
  },
  {
    figure: "421",
    label: "of those 844 are Luminal A: 49.9%",
    keep: CALLED,
    highlight: true,
    showClaim: false,
  },
  {
    figure: `${CLAIMED}`,
    label: "is what the report’s “about 62%” would need. The data has 102 fewer.",
    keep: CALLED,
    highlight: true,
    showClaim: true,
  },
];

/** One entry per dot, in layout order. */
export function cohortGroups(): Group[] {
  return GROUPS.flatMap(({ group, count }) => Array<Group>(count).fill(group));
}
