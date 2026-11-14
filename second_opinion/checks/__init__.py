"""Checks turn a claim into a Fact. To add one: import it here and add a CHECKS entry."""

from second_opinion.checks.agreement import check_agreement
from second_opinion.checks.base import Check, CannotCheck
from second_opinion.checks.attribute import check_rank, check_ratio, check_statistic
from second_opinion.checks.compare import check_comparison
from second_opinion.checks.count import check_count
from second_opinion.checks.coverage import check_coverage
from second_opinion.checks.share import check_share
from second_opinion.model import ClaimType

CHECKS: dict[ClaimType, Check] = {
    ClaimType.AGREEMENT: check_agreement,
    ClaimType.COMPARISON: check_comparison,
    ClaimType.COUNT: check_count,
    ClaimType.COVERAGE: check_coverage,
    ClaimType.SHARE: check_share,
    ClaimType.RANK: check_rank,
    ClaimType.RATIO: check_ratio,
    ClaimType.STATISTIC: check_statistic,
}

__all__ = ["CHECKS", "CannotCheck", "Check"]
