"""Shared types for the checks (kept apart from __init__ so check modules can import them)."""

from collections.abc import Callable

from second_opinion.model import Claim, Fact
from second_opinion.release import Release
from second_opinion.variants import Variant


class CannotCheck(Exception):
    """The release cannot answer this claim; the message says what is missing."""


Check = Callable[[Claim, Release, Variant], Fact]
