# How a verdict is decided

All verdicts come from code. There is no AI in the verdict path and no API key anywhere.

- A stated number is **supported** if it equals the computed value after rounding to the report's own
  precision. For "about / roughly / nearly" it is supported within **2 percentage points** (shares)
  or **2% of the count** (counts). Ranges ("55-65%") must contain the value.
- One-sided bounds are checked as bounds: "more than 150", "at least 1,000", "fewer than 1%".
- Amount words become numbers: "a third", "half", "one in ten" (within 2 points); "most" / "the
  majority" is more than 50%; "nearly all" at least 90%; "a minority" under 50%.
- Rankings ("the most frequently mutated gene", "the second most common subtype", "the two most
  frequently mutated genes") must hold exactly; ties count as holding. Ratios ("about two to one",
  "twice as many") are supported within 15% ("about") or 10% of the stated ratio.
- A sentence that makes several checks ("7 metastatic and 139 normal-tissue samples", "about 77% are
  ER-positive and 66% PR-positive", "Luminal A is the largest subtype, at about 62%") is checked part by
  part and takes the verdict of its worst part; every part is listed in the finding.
- Otherwise it is **contradicted**, and the tool gives the correct value with its denominator.
- A direction claim ("higher in ER-positive") is supported when the sign of the difference matches.
- Claims about treatment, response, cause or prediction, survival differences between groups,
  measures the release does not hold (Ki-67, grade, tumor size, race, BMI, ...), or "large enough"
  judgments are `insufficient_evidence`, with what data would be needed.
- The primary number always follows the organizers' reference definitions: primary tumors by barcode,
  PAM50 from `PAM50Call_RNAseq`, receptor status from the clinical IHC columns (Positive among
  Positive + Negative), deaths from `survival.tsv` OS. The other ways of counting (including the 2012
  study's columns) only decide the robust/fragile tag; they never change the verdict.
- Close calls are flagged for the reviewer: a ranking won by under 2 points, a share near the edge of
  its tolerance, a count right at its bound.

Claim types checked: counts (samples, patients, sample types, sexes, deaths, slides), shares (PAM50
subtype, ER / PR / HER2 / hormone-receptor / triple-negative status, stage, histology, menopause, sex,
gene mutation, ERBB2-style amplification and deep deletion, deaths), data-layer coverage, also within a
subgroup ("protein data covers most triple-negative tumors"), rankings, ratios, comparisons of a share
between groups ("TP53 mutations are more common in Basal-like than Luminal A tumors"), protein
comparisons (ER-alpha by ER status), median / mean age, and "the data can't answer this".
