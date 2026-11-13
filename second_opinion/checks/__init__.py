"""Checks turn a claim into a Fact. To add one: import it here and add a CHECKS entry."""

from second_opinion.checks.base import Check, CannotCheck
from second_opinion.checks.compare import check_comparison
from second_opinion.checks.count import check_count
from second_opinion.checks.coverage import check_coverage
from second_opinion.checks.share import check_share
from second_opinion.model import ClaimType

CHECKS: dict[ClaimType, Check] = {
    ClaimType.COMPARISON: check_comparison,
    ClaimType.COUNT: check_count,
    ClaimType.COVERAGE: check_coverage,
    ClaimType.SHARE: check_share,
}

__all__ = ["CHECKS", "CannotCheck", "Check"]
