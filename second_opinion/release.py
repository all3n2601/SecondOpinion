"""Load a TCGA-BRCA release folder (release A, a practice release, or an envelope's release/)."""

import hashlib
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

import pandas as pd

RELEASE_FILES = {
    "clinical": "clinical.tsv",
    "survival": "survival.tsv",
    "mutation": "mutation_gene_level.tsv.gz",
    "copy_number": "copy_number_gistic.tsv.gz",
    "protein": "protein_rppa.tsv.gz",
}
RNA_FILE = "rna_hiseq.tsv.gz"  # optional: sealed envelopes ship without it

class ReleaseError(Exception):
    """A release file exists but cannot be read (empty, corrupt, or missing a required column)."""


T = TypeVar("T")
_LAYERS = ("survival", "mutation", "copy_number", "protein", "rna")


@dataclass
class Release:
    folder: Path
    clinical: pd.DataFrame  # as read from clinical.tsv
    survival_ids: set[str]
    mutation_ids: set[str]  # column headers of the mutation file
    copy_number_ids: set[str]
    protein_ids: set[str]
    protein: pd.DataFrame  # protein_rppa, index = protein name, columns = sample ids
    rna_ids: set[str] | None  # None when the folder has no rna_hiseq.tsv.gz
    checksums: dict[str, str]  # file name -> sha256 of every file present

    def primary_ids(self) -> list[str]:
        """Clinical sampleID where chars [13:15] == "01" (primary tumor), in clinical.tsv file order."""
        ids = self.clinical["sampleID"].dropna().astype(str)
        return ids[ids.str[13:15] == "01"].tolist()

    def layer_ids(self, layer: str) -> set[str]:
        """Sample ids present in a layer: survival, mutation, copy_number, protein or rna."""
        if layer not in _LAYERS:
            raise KeyError(f"unknown layer {layer!r}; expected one of {', '.join(_LAYERS)}")
        if layer == "rna":
            if self.rna_ids is None:
                raise KeyError("rna: no RNA file in this release")
            return self.rna_ids
        return getattr(self, f"{layer}_ids")


_READ_ERRORS = (
    OSError, ValueError, KeyError, EOFError, zlib.error,
    pd.errors.ParserError, pd.errors.EmptyDataError,
)


def _read(name: str, reader: Callable[[], T]) -> T:
    """Run `reader`; any way a file can be unreadable becomes a ReleaseError naming the file."""
    try:
        return reader()
    except _READ_ERRORS as exc:
        if isinstance(exc, pd.errors.EmptyDataError):
            why = "the file is empty"
        else:
            why = f"it could not be read ({str(exc).strip() or type(exc).__name__})"
        raise ReleaseError(f"Release file {name} is unusable: {why}") from exc


def _header_ids(path: Path) -> set[str]:
    """Sample ids = column headers after the first (gene/protein name) column; header row only."""
    return set(pd.read_csv(path, sep="\t", nrows=0).columns[1:])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_clinical(path: Path) -> pd.DataFrame:
    clinical = pd.read_csv(path, sep="\t", low_memory=False)
    if "sampleID" not in clinical.columns:
        raise ValueError("it has no sampleID column")
    return clinical


def load_release(folder: str | Path) -> Release:
    """Load a release folder. FileNotFoundError if files are missing; ReleaseError if one is unreadable."""
    folder = Path(folder)
    missing = [name for name in RELEASE_FILES.values() if not (folder / name).exists()]
    if missing:
        raise FileNotFoundError(f"{folder} is missing release files: {', '.join(missing)}")

    rna_path = folder / RNA_FILE
    has_rna = rna_path.exists()
    files = RELEASE_FILES
    protein = _read(files["protein"], lambda: pd.read_csv(folder / files["protein"], sep="\t", index_col=0))
    survival = _read(
        files["survival"], lambda: pd.read_csv(folder / files["survival"], sep="\t", usecols=["sample"])
    )
    names = [*files.values(), *([RNA_FILE] if has_rna else [])]

    return Release(
        folder=folder,
        clinical=_read(files["clinical"], lambda: _read_clinical(folder / files["clinical"])),
        survival_ids=set(survival["sample"].dropna().astype(str)),
        mutation_ids=_read(files["mutation"], lambda: _header_ids(folder / files["mutation"])),
        copy_number_ids=_read(files["copy_number"], lambda: _header_ids(folder / files["copy_number"])),
        protein_ids=set(protein.columns),
        protein=protein,
        rna_ids=_read(RNA_FILE, lambda: _header_ids(rna_path)) if has_rna else None,
        checksums={name: _read(name, lambda n=name: _sha256(folder / n)) for name in names},
    )
