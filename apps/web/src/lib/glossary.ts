// Plain-word meanings for the technical terms the app uses. Shown by the <Term> tooltip and in the
// role summary's "Words used" list, so each term is explained the same way everywhere.

export type GlossaryKey =
  | "robust"
  | "fragile"
  | "variant"
  | "denominator"
  | "subtypeCall"
  | "release"
  | "checksum"
  | "claimLadder";

export interface GlossaryEntry {
  term: string;
  meaning: string;
}

export const GLOSSARY: Record<GlossaryKey, GlossaryEntry> = {
  robust: {
    term: "Robust",
    meaning: "The verdict stays the same under every reasonable way of counting we tried.",
  },
  fragile: {
    term: "Fragile",
    meaning: "The verdict changes with how you count, for example which subtype label is used. Treat it with care.",
  },
  variant: {
    term: "Variant",
    meaning:
      "One reasonable way of counting: which subtype label, which people and which samples. We recount each claim under every variant.",
  },
  denominator: {
    term: "Denominator",
    meaning: "The total a share is taken out of: the “844” in “421 of 844”. Samples with an unknown value are left out of it.",
  },
  subtypeCall: {
    term: "Subtype call",
    meaning:
      "The label that puts a tumor in a group such as Luminal A or Basal. The release has two: one from RNA-seq and one from the 2012 study.",
  },
  release: {
    term: "Release",
    meaning: "One fixed, dated copy of the TCGA-BRCA data files. Every number is computed from the release you chose.",
  },
  checksum: {
    term: "Checksum (SHA-256)",
    meaning: "A fingerprint of a file. If even one byte of the file changes, the checksum changes, so it proves which data was used.",
  },
  claimLadder: {
    term: "Claim ladder",
    meaning:
      "Rewrites a sentence down to what the data supports: over-strong words are struck through and the honest wording is added.",
  },
};
