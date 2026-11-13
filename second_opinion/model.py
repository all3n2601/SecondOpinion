from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Solidity(str, Enum):
    HOLDS_EVERYWHERE = "holds_under_every_variant"
    FRAGILE = "holds_under_some_variants"
    NOT_APPLICABLE = "not_applicable"


class Decision(str, Enum):
    PROCEED = "Proceed"
    FIX = "Fix a problem"
    NARROW = "Narrow the question"
    STOP = "Stop"


class ClaimType(str, Enum):
    COUNT = "COUNT"
    SHARE = "SHARE"
    COMPARISON = "COMPARISON"
    AGREEMENT = "AGREEMENT"
    COVERAGE = "COVERAGE"
    NOT_ANSWERABLE = "NOT_ANSWERABLE"
    UNMAPPED = "UNMAPPED"


@dataclass
class ClaimParams:
    stated_value: float | None = None  # 62.0 for "62%", 535 for "535"; range: the lower end
    stated_high: float | None = None  # upper end of a range like "55-65%"
    stated_total: float | None = None  # 1101 in "535 of 1,101"
    unit: str | None = None  # "percent" | "count" | "all" (for "every ...")
    decimals: int | None = None  # digits after the point as written: "49.9%" -> 1
    approximate: bool = False  # about / roughly / nearly / ~ / around
    subject: str | None = None  # "primary_tumors" | "all_five_layers" | "samples" | ...
    subtype: str | None = None  # normalised, e.g. "Luminal A"
    direction: str | None = None  # "higher" | "lower"
    measure: str | None = None  # e.g. "ER-alpha protein"
    group_a: str | None = None  # e.g. "ER-positive"
    group_b: str | None = None  # e.g. "ER-negative"


@dataclass
class Claim:
    id: str  # "C1", "C2", ... in report order
    text: str  # the sentence exactly as written
    sentence_index: int
    type: ClaimType
    params: ClaimParams = field(default_factory=ClaimParams)
    needed_data: str | None = None  # NOT_ANSWERABLE only
    clinical_terms: list[str] = field(default_factory=list)


@dataclass
class SentenceInfo:
    index: int
    text: str
    claim_id: str | None


@dataclass
class ExtractResult:
    sentences: list[SentenceInfo]
    claims: list[Claim]


@dataclass
class Fact:
    label: str  # plain words
    value: float | None  # percent (shares), count (counts), mean difference (comparisons)
    numerator: int | None
    denominator: int | None
    sample_ids: list[str]
    files: list[str]  # release file names used
    code: str  # copy-pasteable pandas snippet that reproduces the value
    unknown_count: int = 0  # rows left out because the value was missing
    extra: dict[str, float | int | str] = field(default_factory=dict)  # n_a, n_b, mean_a, mean_b


@dataclass
class VariantResult:
    variant_id: str
    fact: Fact | None
    verdict: Verdict | None


@dataclass
class SkepticResult:
    shuffle_p: float | None
    n_sites: int
    site_flips: list[str]


@dataclass
class LadderSegment:
    text: str
    struck: bool = False
    inserted: bool = False


@dataclass
class Review:
    decision: str  # "accept" | "override"
    final_verdict: Verdict
    reason: str
    reviewer_role: str


@dataclass
class ClaimResult:
    claim: Claim
    verdict: Verdict
    solidity: Solidity
    fact: Fact | None
    correct_value: str | None  # contradicted only
    missing_evidence: str | None  # insufficient_evidence only
    variants: list[VariantResult]
    flips_on: list[str]  # e.g. ["subtype_source=study_2012_label"]
    skeptic: SkepticResult | None
    ladder: list[LadderSegment]
    limitation: str | None
    review: Review | None = None


@dataclass
class ReleaseInfo:
    name: str
    files: list[dict[str, str]]  # [{"file": ..., "sha256": ...}]


@dataclass
class AuditResult:
    release: ReleaseInfo
    claims: list[ClaimResult]
    notes: list[str]  # "No RNA file in this release."


@dataclass
class DecisionSuggestion:
    decision: Decision
    rule: str
    reasons: list[str]
    sign_off: list[str]
    would_change: list[str]


@dataclass
class DecisionChoice:
    choice: Decision
    reason: str
    reviewer_role: str
