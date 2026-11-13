"""Tiny generated TCGA-BRCA release for tests (no real data, no RNA file, no manifest)."""

import gzip
from pathlib import Path

import pandas as pd

# 13 clinical rows: 10 primary (-01), 2 solid-tissue normal (-11), 1 metastasis (-06).
# Counts below are true for the files written by make_mini_release() and are relied on by later tests.
MINI: dict[str, int] = {
    # all clinical rows (primary + normal + metastasis)
    "samples": 13,
    # sampleID chars [13:15] == "01"
    "primary": 10,
    # primary rows with gender MALE (2); FEMALE is the rest except the unknown one
    "male_primary": 2,
    # primary rows whose gender is missing (NaN)
    "unknown_sex_primary": 1,
    # primary rows with a PAM50Call_RNAseq value (LumA/LumB/Basal/Her2/Normal spelling)
    "rna_subtyped_primary": 7,
    # primary rows with PAM50Call_RNAseq == "LumA"
    "luma_rna_primary": 3,
    # primary rows with a PAM50_mRNA_nature2012 value (Luminal A/Luminal B/Basal-like/... spelling)
    "study_2012_subtyped_primary": 7,
    # primary rows with PAM50_mRNA_nature2012 == "Luminal A" (differs from the RNA set on purpose)
    "luma_2012_primary": 3,
    # primary samples present in survival AND mutation AND copy number AND protein
    "all_layers_primary": 6,
    # sampleID ends in -11 (Solid Tissue Normal)
    "normal": 2,
    # sampleID ends in -06 (Metastatic); it carries an RNA call "LumA" on purpose (must not count as primary)
    "metastasis": 1,
}

# (sampleID, gender, PAM50Call_RNAseq, PAM50_mRNA_nature2012, ER status, site, sample_type)
_NA = None
_CLINICAL = [
    ("TCGA-AA-0001-01", "FEMALE", "LumA", "Luminal A", "Positive", "AA", "Primary Tumor"),
    ("TCGA-AA-0002-01", "FEMALE", "LumA", "Luminal A", "Positive", "AA", "Primary Tumor"),
    ("TCGA-AA-0003-01", "FEMALE", "LumA", _NA, "Positive", "AA", "Primary Tumor"),
    ("TCGA-BB-0004-01", "FEMALE", "LumB", "Luminal B", "Positive", "BB", "Primary Tumor"),
    ("TCGA-BB-0005-01", "FEMALE", "Basal", "Basal-like", "Negative", "BB", "Primary Tumor"),
    ("TCGA-BB-0006-01", "MALE", "Her2", "HER2-enriched", "Negative", "BB", "Primary Tumor"),
    ("TCGA-CC-0007-01", "MALE", _NA, _NA, "Positive", "CC", "Primary Tumor"),
    ("TCGA-CC-0008-01", _NA, "Normal", "Normal-like", "Positive", "CC", "Primary Tumor"),
    ("TCGA-CC-0009-01", "FEMALE", _NA, "Luminal A", "Indeterminate", "CC", "Primary Tumor"),
    ("TCGA-CC-0010-01", "FEMALE", _NA, _NA, "Negative", "CC", "Primary Tumor"),
    ("TCGA-AA-0001-11", "FEMALE", _NA, _NA, "Positive", "AA", "Solid Tissue Normal"),
    ("TCGA-BB-0004-11", "FEMALE", _NA, _NA, "Positive", "BB", "Solid Tissue Normal"),
    ("TCGA-AA-0011-06", "FEMALE", "LumA", _NA, "Positive", "AA", "Metastatic"),
]

_SURVIVAL = [  # primaries 1-9 and the metastasis; not 10, not the normals
    f"TCGA-AA-{n:04d}-01" if n < 4 else f"TCGA-BB-{n:04d}-01" if n < 7 else f"TCGA-CC-{n:04d}-01"
    for n in range(1, 10)
] + ["TCGA-AA-0011-06"]
_MUTATION = [_CLINICAL[i][0] for i in (0, 1, 2, 3, 4, 5, 6, 8, 9, 12)]       # primaries 1-7, 9, 10 + met
_COPY_NUMBER = [_CLINICAL[i][0] for i in (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11)]  # primaries 1-6, 8-10 + normals
_PROTEIN = [_CLINICAL[i][0] for i in (0, 1, 2, 3, 4, 6, 7, 8)]               # primaries 1-5, 7-9


def _write_gz(path: Path, df: pd.DataFrame) -> None:
    with gzip.open(path, "wt", newline="") as f:
        df.to_csv(f, sep="\t", index=False, lineterminator="\n")


def _matrix(first_col: str, rows: list[str], ids: list[str], values: list[float]) -> pd.DataFrame:
    data = {first_col: rows}
    for j, sid in enumerate(ids):
        data[sid] = [values[(i + j) % len(values)] for i in range(len(rows))]
    return pd.DataFrame(data)


def make_mini_release(dest: Path) -> Path:
    """Write the five release files (no RNA file, no manifest) into `dest` and return it."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    clinical = pd.DataFrame(
        _CLINICAL,
        columns=[
            "sampleID", "gender", "PAM50Call_RNAseq", "PAM50_mRNA_nature2012",
            "breast_carcinoma_estrogen_receptor_status", "tissue_source_site", "sample_type",
        ],
    )
    clinical.to_csv(dest / "clinical.tsv", sep="\t", index=False, lineterminator="\n")

    survival = pd.DataFrame(
        {
            "sample": _SURVIVAL,
            "_PATIENT": [s[:12] for s in _SURVIVAL],
            "OS": [i % 2 for i in range(len(_SURVIVAL))],
            "OS.time": [400 + 100 * i for i in range(len(_SURVIVAL))],
        }
    )
    survival.to_csv(dest / "survival.tsv", sep="\t", index=False, lineterminator="\n")

    _write_gz(dest / "mutation_gene_level.tsv.gz",
              _matrix("sample", ["TP53", "PIK3CA", "CDH1"], _MUTATION, [0, 1, 0]))
    _write_gz(dest / "copy_number_gistic.tsv.gz",
              _matrix("Gene Symbol", ["ERBB2", "MYC", "ESR1"], _COPY_NUMBER, [0, -1, 1, 2]))
    _write_gz(dest / "protein_rppa.tsv.gz",
              _matrix("Sample_description", ["ERALPHA", "HER2", "AKT"], _PROTEIN, [-0.5, 0.25, 1.5, -1.0]))
    return dest
