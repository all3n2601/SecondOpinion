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


@dataclass
class VariantResult:
    variant_id: str
    value: float | None
    numerator: int | None
    denominator: int | None
    query: str


@dataclass
class ClaimCheck:
    claim_text: str
    verdict: Verdict
    solidity: Solidity
    variants: list[VariantResult] = field(default_factory=list)
    honest_sentence: str | None = None
    missing_evidence: str | None = None
