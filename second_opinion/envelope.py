"""Open a judges' sealed envelope from the app, with the organizers' own envelopes/unseal.py.

At the Q&A a judge gives an envelope number and a four-word code. This runs the challenge repository's
unseal.py unchanged (it checks release A, the envelope's fingerprint and every rebuilt file), then reports
what it opened: the report for our product (claim_auditor_report.md), release A, and the envelope's own
release folder. The practice envelope has no report of its own; its report is the practice brief.

The challenge repository is found at SO_CHALLENGE_DIR, else next to this repository.
"""

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
SIBLING_CHALLENGE = _REPO_ROOT.parent / "oncosys-hackathon-challenge"
REPORT_FILE = "claim_auditor_report.md"
PRACTICE_BRIEF = Path("products") / "research-claim-auditor" / "practice_brief.md"
UNSEAL_TIMEOUT_SECONDS = 180  # unseal.py says 10 to 20 seconds; a slow laptop gets plenty of room

_NUMBER = re.compile(r"^(?:practice|e?\d{1,3})$", re.IGNORECASE)
_WORD = re.compile(r"^[a-z]{2,20}$")


class EnvelopeError(Exception):
    """The envelope could not be opened; the message says what happened and what to do."""


@dataclass
class OpenedEnvelope:
    envelope: str  # "E07" or "practice"
    opened_dir: Path
    report_name: str | None  # the file the report came from, None if the envelope has none for us
    report_text: str | None
    release_a_dir: Path
    envelope_release_dir: Path
    files: list[str]  # everything unseal.py wrote, relative to opened_dir
    checks: list[str]  # the checks unseal.py passed, in its own words
    seconds: float
    notes: list[str] = field(default_factory=list)


def challenge_repo() -> Path:
    env = os.environ.get("SO_CHALLENGE_DIR")
    folder = Path(env).expanduser() if env else SIBLING_CHALLENGE
    if not (folder / "envelopes" / "unseal.py").is_file():
        raise EnvelopeError(
            f"The challenge repository was not found at {folder}. Clone it next to SecondOpinion "
            "(see the README), or set SO_CHALLENGE_DIR to its folder"
        )
    return folder.resolve()


def envelope_name(number: str) -> str:
    """"7", "07", "E07" -> "E07"; "practice" stays "practice". Raises EnvelopeError for anything else."""
    raw = number.strip()
    if not _NUMBER.match(raw):
        raise EnvelopeError("Enter the envelope number from the card, for example 07")
    if raw.lower() == "practice":
        return "practice"
    return f"E{int(raw.lstrip('Ee')):02d}"


def code_words(code: str) -> list[str]:
    """The four words, lower-case; spaces or hyphens between them both work, as in unseal.py."""
    words = code.replace("-", " ").lower().split()
    if len(words) != 4 or not all(_WORD.match(w) for w in words):
        raise EnvelopeError("The code is four words, for example amber falcon river quartz")
    return words


def _failure(output: str) -> str:
    """unseal.py's own error line ("✗ That code doesn't open envelope E07 ..."), without the mark."""
    for line in output.splitlines():
        if line.strip().startswith("✗"):
            return line.strip().lstrip("✗").strip().rstrip(".")
    tail = [line.strip() for line in output.splitlines() if line.strip()]
    return tail[-1].rstrip(".") if tail else "unseal.py stopped without saying why"


def unseal(number: str, code: str) -> OpenedEnvelope:
    """Run envelopes/unseal.py for this envelope and code; raise EnvelopeError with its message on failure."""
    name = envelope_name(number)
    words = code_words(code)
    repo = challenge_repo()
    started = time.perf_counter()
    try:
        done = subprocess.run(
            [sys.executable, str(repo / "envelopes" / "unseal.py"), name, *words],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=UNSEAL_TIMEOUT_SECONDS,
            env={**os.environ, "PYTHONUTF8": "1"},  # unseal.py prints check marks; Windows consoles need UTF-8
        )
    except subprocess.TimeoutExpired as exc:
        raise EnvelopeError(f"Unsealing took longer than {UNSEAL_TIMEOUT_SECONDS} seconds and was stopped. Try again") from exc
    seconds = time.perf_counter() - started
    output = (done.stdout or "") + (done.stderr or "")
    if done.returncode != 0:
        if "No module named 'cryptography'" in output:
            python = r".venv\Scripts\python.exe" if os.name == "nt" else ".venv/bin/python"
            raise EnvelopeError(
                "Unsealing needs the cryptography package, which this install is missing. "
                f"Run: {python} -m pip install -r requirements.txt"
            )
        raise EnvelopeError(_failure(output))

    opened = repo / "envelopes" / "opened" / name
    checks = [line.strip().lstrip("✓").strip() for line in output.splitlines() if line.strip().startswith("✓")]
    files = sorted(p.relative_to(opened).as_posix() for p in opened.rglob("*") if p.is_file())
    notes: list[str] = []
    report_path = opened / REPORT_FILE
    if not report_path.is_file() and name == "practice" and (repo / PRACTICE_BRIEF).is_file():
        report_path = repo / PRACTICE_BRIEF
        notes.append("The practice envelope has no report of its own, so the practice brief was loaded.")
    report_text = report_path.read_text(encoding="utf-8") if report_path.is_file() else None
    if report_text is None:
        notes.append(f"This envelope has no {REPORT_FILE}. Ask the judges which file to audit.")
    return OpenedEnvelope(
        envelope=name, opened_dir=opened, report_name=report_path.name if report_text is not None else None,
        report_text=report_text, release_a_dir=repo / "data" / "tcga-brca" / "raw",
        envelope_release_dir=opened / "release", files=files, checks=checks, seconds=seconds, notes=notes,
    )
