"""The "count it differently" choices every claim is rechecked under."""

from dataclasses import dataclass
from itertools import product

SUBTYPE_SOURCES = ("rna_call", "study_2012_label")
SEX_FILTERS = ("everyone", "women_only")
SAMPLE_SCOPES = ("primary_tumors", "all_samples")


@dataclass(frozen=True)
class Variant:
    subtype_source: str
    sex_filter: str
    sample_scope: str

    @property
    def id(self) -> str:
        return f"{self.subtype_source}|{self.sex_filter}|{self.sample_scope}"


def all_variants() -> list[Variant]:
    return [Variant(*combo) for combo in product(SUBTYPE_SOURCES, SEX_FILTERS, SAMPLE_SCOPES)]


def normalise_subtype(label: str) -> str:
    """Map "LumA" and "Luminal A" style spellings onto one name."""
    key = "".join(ch for ch in str(label).lower() if ch.isalnum())
    aliases = {
        "luma": "Luminal A",
        "luminala": "Luminal A",
        "lumb": "Luminal B",
        "luminalb": "Luminal B",
        "her2": "HER2-enriched",
        "her2enriched": "HER2-enriched",
        "basal": "Basal-like",
        "basallike": "Basal-like",
        "normal": "Normal-like",
        "normallike": "Normal-like",
    }
    return aliases.get(key, str(label))
