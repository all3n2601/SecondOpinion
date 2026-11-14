"""Find or fetch a data folder for the practice run: TCGA-BRCA release A, the release practice_brief.md describes.

The data is not committed (redistribution terms are unconfirmed), so the practice run looks for it in this order:
  1. SO_RELEASE_DIR, if it names a complete release folder;
  2. the challenge repository next to this one (../oncosys-hackathon-challenge/data/tcga-brca/raw), where
     its fetch.py puts the files;
  3. a temporary folder, downloading release A from the public UCSC Xena hub on first use and checking
     every file against the event's frozen SHA-256 (same list as the challenge's sources.csv).
"""

import hashlib
import os
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .release import RNA_FILE

_XENA = "https://tcga-xena-hub.s3.us-east-1.amazonaws.com/download/"

# file -> (source URL, SHA-256), copied from the challenge's data/tcga-brca/sources.csv (retrieved 2026-11-10).
RELEASE_A_SOURCES: dict[str, tuple[str, str]] = {
    "clinical.tsv": (
        _XENA + "TCGA.BRCA.sampleMap%2FBRCA_clinicalMatrix",
        "39eb3be0fb86e6a577bd2cc01502a7fa5a271e1e1cba294e9dc644ad99580d7f",
    ),
    "survival.tsv": (
        _XENA + "survival%2FBRCA_survival.txt",
        "6c9e18ae9c2b8bacc48cd5a60cde97e8880ae2e84e48df437a0378b17e659b73",
    ),
    "mutation_gene_level.tsv.gz": (
        _XENA + "mc3_gene_level%2FBRCA_mc3_gene_level.txt.gz",
        "ceaf6a01fd983cefc7fca8b52f6c65121acc87b75f4d170b9fcdc07ee16a3813",
    ),
    "protein_rppa.tsv.gz": (
        _XENA + "TCGA.BRCA.sampleMap%2FRPPA_RBN.gz",
        "7823a7a375495f7e5f114d0c7ec8773e070cb9ac409785f98045d12ab71195e6",
    ),
    "copy_number_gistic.tsv.gz": (
        _XENA + "TCGA.BRCA.sampleMap%2FGistic2_CopyNumber_Gistic2_all_thresholded.by_genes.gz",
        "c45b1f8ea19c8dc20bd614d0863a40cccc633518d0ad05d2c7fff5f75781e980",
    ),
    # The practice report's first claim counts tumors with RNA data, so release A needs this file too.
    RNA_FILE: (
        _XENA + "TCGA.BRCA.sampleMap%2FHiSeqV2.gz",
        "263bf67245cc4b9062676583c0ff0306f08471a26aafd5504037e1da22133746",
    ),
}

_REPO_ROOT = Path(__file__).resolve().parents[1]
SIBLING_RAW = _REPO_ROOT.parent / "oncosys-hackathon-challenge" / "data" / "tcga-brca" / "raw"
TEMP_DIR_NAME = "secondopinion-practice-release-a"

Source = Literal["environment", "challenge_repo", "temporary"]


class PracticeReleaseError(Exception):
    """No local release A, and downloading one failed or did not match the frozen checksums."""


@dataclass
class PracticeRelease:
    folder: Path
    source: Source
    downloaded: list[str]  # files fetched in this call (empty when everything was already there)


def _complete(folder: Path) -> bool:
    """Every release-A file is present (the release loader checks the contents when it reads them)."""
    return folder.is_dir() and all((folder / name).is_file() for name in RELEASE_A_SOURCES)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def temporary_folder() -> Path:
    return Path(tempfile.gettempdir()) / TEMP_DIR_NAME


def _fetch_into(folder: Path) -> list[str]:
    """Make `folder` hold every file with its frozen checksum; download only what is missing or wrong."""
    folder.mkdir(parents=True, exist_ok=True)
    fetched: list[str] = []
    for name, (url, sha256) in RELEASE_A_SOURCES.items():
        dest = folder / name
        if dest.is_file() and _sha256(dest) == sha256:
            continue
        partial = dest.with_name(dest.name + ".part")
        try:
            urllib.request.urlretrieve(url, partial)
        except OSError as exc:
            partial.unlink(missing_ok=True)
            raise PracticeReleaseError(
                f"Could not download {name} for the practice data ({exc}). "
                "Check the internet connection, or enter a release folder yourself."
            ) from exc
        if _sha256(partial) != sha256:
            partial.unlink(missing_ok=True)
            raise PracticeReleaseError(
                f"The downloaded {name} does not match release A's frozen checksum, so it was not used. "
                "Enter a release folder yourself."
            )
        partial.replace(dest)
        fetched.append(name)
    return fetched


def practice_release() -> PracticeRelease:
    """Return a folder holding release A, downloading it into a temporary folder if there is no local copy."""
    env = os.environ.get("SO_RELEASE_DIR")
    if env and _complete(Path(env)):
        return PracticeRelease(Path(env).resolve(), "environment", [])
    if _complete(SIBLING_RAW):
        return PracticeRelease(SIBLING_RAW.resolve(), "challenge_repo", [])
    folder = temporary_folder()
    fetched = _fetch_into(folder)
    return PracticeRelease(folder.resolve(), "temporary", fetched)

