"""Load a TCGA-BRCA release folder (release A, a practice release, or an envelope's release/)."""

from pathlib import Path

import pandas as pd

RELEASE_FILES = {
    "clinical": "clinical.tsv",
    "survival": "survival.tsv",
    "mutation": "mutation_gene_level.tsv.gz",
    "copy_number": "copy_number_gistic.tsv.gz",
    "protein": "protein_rppa.tsv.gz",
}


def load_release(folder: str | Path) -> dict[str, pd.DataFrame]:
    folder = Path(folder)
    missing = [name for name in RELEASE_FILES.values() if not (folder / name).exists()]
    if missing:
        raise FileNotFoundError(f"{folder} is missing release files: {', '.join(missing)}")
    return {
        key: pd.read_csv(folder / name, sep="\t", low_memory=False)
        for key, name in RELEASE_FILES.items()
    }
