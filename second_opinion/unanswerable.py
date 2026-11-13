"""Spot sentences the release cannot answer, and say what data would be needed.

A TCGA-BRCA release contains: clinical data (sex, sample type, ER/PR/HER2 status, subtype labels),
survival (vital status and follow-up time), gene-level mutation calls, GISTIC copy number and
RPPA protein levels. Some releases also carry RNA-seq expression; judges' envelope releases do not.

It does NOT contain which treatment anyone received, how they responded, or any experiment or
randomised comparison. So claims about treatment, response, cause, prediction or survival benefit
get "the data can't answer this", with the missing data named. That is a correct, useful result.

Plain survival counts ("1,080 tumors have survival data") stay answerable: the survival file exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Keyword group -> (what would be needed, words that trigger it). Matching is whole-word and
# case-insensitive. Edit freely; keep phrases lower-case.
#
# Left out on purpose:
#   "treated"   - methods text says "missing values were treated as unknown".
#   "driver"    - "driver mutations" is ordinary genomics wording in a count claim.
#   "predicted" - "predicted subtype" is how PAM50 calls are described.
KEYWORD_GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "treatment": (
        "treatment and outcome data",
        (
            "hormone therapy", "endocrine therapy", "targeted therapy", "guide treatment",
            "guide therapy", "treatment", "treatments", "therapy", "therapies",
            "chemotherapy", "tamoxifen", "trastuzumab",
            # "treated" alone is left out (see above); these phrases only ever mean a treatment
            "treated with", "best treated", "were treated", "was treated", "is treated", "are treated",
            "inhibitor", "inhibitors", "PARP", "olaparib", "talazoparib", "palbociclib", "ribociclib",
            "abemaciclib", "CDK4/6", "aromatase", "letrozole", "anastrozole", "exemestane", "fulvestrant",
            "pertuzumab", "lapatinib", "neratinib", "pembrolizumab", "immunotherapy", "radiotherapy",
            "radiation therapy", "neoadjuvant", "adjuvant", "mastectomy", "lumpectomy", "drug", "drugs",
            "should receive", "should be offered", "eligible for", "candidates for", "benefit from",
            "benefits from", "benefited from", "benefitted from", "sensitive to", "resistant to", "resistance to",
        ),
    ),
    "response": (
        "treatment-response data",
        ("responded best", "responded", "respond", "responds", "response", "responses", "responders"),
    ),
    "cause": (
        "experimental or longitudinal data that can test cause or prediction",
        (
            "causes", "cause", "caused", "causing", "drives", "drive", "driven by", "driving",
            "predicts", "predict", "predictive", "predicting", "determines", "determine",
            "determined by", "leads to", "lead to", "led to", "results in",
        ),
    ),
    "survival_benefit": (
        "treatment-arm survival data",
        (
            "survival benefit", "survival advantage", "improves survival", "improved survival",
            "improve survival", "prolongs survival", "prolonged survival",
        ),
    ),
    "diagnosis": (
        "clinical diagnostic data; and this tool never makes diagnostic or risk statements about individuals",
        (
            "diagnose", "diagnoses", "diagnostic test", "screening test", "risk score", "risk scores",
            "should be screened", "biopsy", "biopsies",
        ),
    ),
}


@dataclass
class Unanswerable:
    terms: list[str]  # matched words, lower-case, in sentence order
    needed_data: str  # e.g. "treatment and outcome data and treatment-response data"


def _pattern(phrase: str) -> re.Pattern[str]:
    words = r"\s+".join(re.escape(word) for word in phrase.split())
    return re.compile(rf"(?<!\w){words}(?!\w)", re.IGNORECASE)


_PATTERNS = [
    (group, phrase, _pattern(phrase))
    for group, (_, phrases) in KEYWORD_GROUPS.items()
    for phrase in phrases
]


def detect_unanswerable(sentence: str) -> Unanswerable | None:
    """Return the clinical/causal words in `sentence` and the data they would need, or None."""
    hits: list[tuple[int, int, str]] = []  # (start, -length, phrase)
    groups: set[str] = set()
    for group, phrase, pattern in _PATTERNS:
        for match in pattern.finditer(sentence):
            hits.append((match.start(), -len(phrase), phrase))
            groups.add(group)
    if not hits:
        return None

    terms: list[str] = []
    for _, _, phrase in sorted(hits):
        if phrase not in terms:
            terms.append(phrase)

    needs: list[str] = []
    for group, (need, _) in KEYWORD_GROUPS.items():
        if group in groups and need not in needs:
            needs.append(need)

    return Unanswerable(terms=terms, needed_data=" and ".join(needs))
