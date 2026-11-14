"""Sentences from the blind reports (tests/ai_hard/blind*_report.md) that the rules once got wrong or missed.

Each verdict was worked out from the raw release by someone who had not seen this code. These run with the rules
only (the AI is off in tests); they need the real release in SO_RELEASE_DIR.
"""

import pytest

from second_opinion.audit import audit_claims
from second_opinion.extract import extract_claims
from second_opinion.model import Verdict

S, C, I = Verdict.SUPPORTED, Verdict.CONTRADICTED, Verdict.INSUFFICIENT_EVIDENCE

CASES = [
    ("Under the 2012 consortium labels, Normal-like is the rarest group, at under 2% of labelled tumors.", S),
    ("The 257 primary tumors without an RNA subtype call were left out because their RNA quality was too low.", I),
    ("Just over a quarter of patients, 27%, were diagnosed before age 50.", S),
    ("Patients diagnosed at 65 or older made up roughly 35% of the cohort.", C),
    ("Lobular carcinoma patients were diagnosed about six years later on average than patients with ductal carcinoma.", C),
    ("The median overall-survival time on record was 843 days, a little over two years.", S),
    ("Three in four stage IV patients died during follow-up, compared with fewer than one in ten stage I patients.", S),
    ("HER2-enriched tumors had a lower death rate than Luminal A tumors.", C),
    ("TP53 mutations are concentrated in basal-like tumors, where 85% carry one, against roughly one in ten Luminal A tumors.", S),
    ("Just over half of the tumors scored HER2-positive by immunohistochemistry carry an ERBB2 amplification.", S),
    ("The ER protein comparison includes 698 primary tumors with both RPPA data and a definitive ER result.", S),
    ("Mean ER-alpha protein is 2.18 in ER-positive tumors against -0.87 in ER-negative tumors, a gap of about three units.", S),
    ("GATA3 protein in ER-positive tumors exceeds that in ER-negative tumors by more than two units.", C),
    ("Where both the RNA-seq call and the 2012 label exist, the two agree for 90% of tumors.", S),
    ("Most tumors in the release were diagnosed in 2010 or later.", C),
]


@pytest.mark.parametrize("sentence, verdict", CASES, ids=[s[:40] for s, _ in CASES])
def test_blind_sentence(release_dir, sentence, verdict):
    claims = extract_claims(sentence).claims
    assert len(claims) == 1, [c.text for c in claims]
    [result] = audit_claims(claims, release_dir).claims
    assert result.verdict == verdict, (result.claim.type, result.correct_value, result.missing_evidence)


ROUND_B = [
    ("We analysed the 1,101 primary breast tumors in TCGA-BRCA release A (1,247 samples in total), of which 535 (48.6%) "
     "carry all five data layers: survival, mutation, copy number, RNA and protein.", I),  # was S: 1,247 unchecked
    ("We analysed the 1,101 primary breast tumors in TCGA-BRCA release A, of which 535 (50.6%) carry all five data layers.", C),
    ("HER2 overexpression by immunohistochemistry was uncommon (22.5%; 164 of 728 tumors with a definitive result), and "
     "triple-negative disease made up 15–17% of tumors with all three receptors known.", S),
    # was C: the reading checks the 2.0-2.5 difference but not n = 698 (coverage gate)
    ("ER-alpha protein was higher in ER-positive than in ER-negative tumors, with a mean RPPA difference of 2.0–2.5 units (n = 698).", I),
    ("Mean ERALPHA protein (RPPA) is 2.18 in the 529 ER+ tumors with protein data against -0.87 in the 169 ER- tumors, "
     "a gap of about 3.1 units.", I),  # was S: 529, 169 and 3.1 unchecked (coverage gate)
    ("Every one of the 742 primary tumors with protein data also has RNA-seq data.", S),
    ("Basal-like tumors are almost all ER-negative: 124 of 136 with a known ER status (91.2%).", S),
    ("Mean cyclin B1 protein (RPPA CYCLINB1) is lower in Basal-like than in Luminal A tumors.", C),
    ("Diagnosis years span 1988–2013, and 2010 is the busiest single year with 225 diagnoses.", S),
    ("The largest single disagreement is a group of 31 tumors that the 2012 study placed in LumB and that RNA-seq calls LumA.", S),
]


@pytest.mark.parametrize("sentence, verdict", ROUND_B, ids=[s[:40] for s, _ in ROUND_B])
def test_blind_round_b_sentence(release_dir, sentence, verdict):
    test_blind_sentence(release_dir, sentence, verdict)


TABLE = """**Table 1.** PAM50 RNA subtype of primary tumors with an RNA-seq subtype call (n = 844).

| Group | n | % |
|---|---|---|
| Luminal A | 421 | 49.9 |
| Basal-like | 141 | 12.8 |
| Normal-like | 23 | 2.7 |
"""


def test_a_percent_column_is_read_as_percents(release_dir):
    claims = [c for c in extract_claims(TABLE).claims if " | " in c.text]  # the rows (the caption is its own claim)
    results = {r.claim.text.split("|")[0].strip(): r.verdict for r in audit_claims(claims, release_dir).claims}
    assert results == {"Luminal A": S, "Basal-like": C, "Normal-like": S}  # 141 of 844 is 16.7%, not 12.8%
