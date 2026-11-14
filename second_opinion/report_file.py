"""Read an uploaded report file (Markdown, plain text or PDF) into the text the extractor reads.

PDF text comes from pypdf's text layer. A PDF puts a hard line break at the end of every printed
line, and the extractor already joins wrapped lines into paragraphs, so the work here is to keep
what a PDF adds out of the sentences: page numbers, running headers and footers, words split by a
hyphen at the end of a line, ligatures. Short lines (headings, table rows, a paragraph's last
line) are kept as their own blocks so a heading is not glued onto the sentence after it. Scanned
PDFs have no text layer and are refused with a plain message: there is no OCR here.
"""

from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MAX_PDF_PAGES = 300  # a long paper is ~40 pages; this only stops runaway uploads

ReportKind = Literal["markdown", "text", "pdf"]


class ReportFileError(ValueError):
    """The file cannot be read as a report; the message is shown to the user as written."""


@dataclass(frozen=True)
class ReportFile:
    text: str
    kind: ReportKind
    pages: int | None = None  # PDFs only


def read_report_file(data: bytes, filename: str) -> ReportFile:
    """The report's text from a file's bytes; `filename` decides the kind (a PDF is also known by its header)."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" or data[:1024].lstrip().startswith(b"%PDF-"):
        text, pages = pdf_text(data)
        return ReportFile(text=text, kind="pdf", pages=pages)
    if b"\x00" in data[:4096]:
        raise ReportFileError(f"“{Path(filename).name}” is not a Markdown, text or PDF file.")
    return ReportFile(text=decode_text(data), kind="text" if suffix == ".txt" else "markdown")


def decode_text(raw: bytes) -> str:
    """UTF-8 (a Windows byte-order mark is dropped), else Windows-1252; Windows line endings become \\n."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def pdf_text(data: bytes) -> tuple[str, int]:
    """The text of a PDF and its page count. Raises ReportFileError with a message for the user."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):  # an owner password alone still opens with ""
            raise ReportFileError("This PDF is password-protected. Save an unprotected copy, or paste the text.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ReportFileError(f"This PDF has {len(reader.pages)} pages; the limit is {MAX_PDF_PAGES}.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except ReportFileError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise ReportFileError(f"Could not read this PDF ({exc}). Paste the text instead.") from exc
    except Exception as exc:  # noqa: BLE001 - pypdf raises odd errors on broken files (DependencyError for some ciphers)
        raise ReportFileError(f"Could not read this PDF ({type(exc).__name__}). Paste the text instead.") from exc

    text = clean_pdf_text(pages)
    if not text.strip():
        raise ReportFileError(
            "This PDF has no text to read (it may be a scanned image). Paste the text, or run it through OCR first."
        )
    return text, len(pages)


_LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})
_PAGE_NUMBER = re.compile(r"(?i)^[\s\-–—|]*(?:page\s+)?\d{1,4}(?:\s*(?:/|of)\s*\d{1,4})?[\s\-–—|]*$")
_ENDS_SENTENCE = re.compile(r"[.!?:][\"'”’)\]]*$")
_SPACES = re.compile(r"[ \t ]+")
_LINE_END_HYPHEN = re.compile(r"[A-Za-z0-9]-$")


def clean_pdf_text(pages: list[str]) -> str:
    """Join the pages' text into Markdown-like paragraphs the sentence splitter reads correctly."""
    page_lines = [
        [_SPACES.sub(" ", line).strip() for line in page.translate(_LIGATURES).replace("­", "").splitlines()]
        for page in pages
    ]
    page_lines = [[line for line in lines if line] for lines in page_lines]
    running = _running_lines(page_lines)

    lines: list[str] = []
    for page in page_lines:
        for i, line in enumerate(page):
            at_edge = i < 2 or i >= len(page) - 2
            if at_edge and (_PAGE_NUMBER.match(line) or _edge_key(line) in running):
                continue
            lines.append(line)

    lengths = sorted(len(line) for line in lines)
    full = lengths[int(len(lengths) * 0.9)] if lengths else 0  # a typical full-width line
    out: list[str] = []
    after_sentence = True  # the previous line ended a sentence (or there is none)
    for i, line in enumerate(lines):
        if out and _LINE_END_HYPHEN.search(out[-1]) and line[:1].isalnum():
            out[-1] += line  # "HER2-" + "positive": keep the hyphen, drop the line break
            after_sentence = bool(_ENDS_SENTENCE.search(out[-1]))
            continue
        short = bool(full) and len(line) < 0.7 * full
        ends_sentence = bool(_ENDS_SENTENCE.search(line))
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if short and after_sentence and not ends_sentence and not next_line[:1].islower():
            # A short line with no closing punctuation, between a finished sentence and a line that
            # starts a new one: a heading or table row, kept apart from the sentence after it.
            if out and out[-1]:
                out.append("")
            out += [line, ""]
            after_sentence = True
            continue
        out.append(line)
        if short and ends_sentence:
            out.append("")  # a paragraph's short last line ends the paragraph
        after_sentence = ends_sentence
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def _edge_key(line: str) -> str:
    """A header or footer line with its page number blanked, so "Draft - 3" matches "Draft - 4"."""
    return re.sub(r"\d+", "#", line.casefold())


def _running_lines(page_lines: list[list[str]]) -> set[str]:
    """Lines repeated at the top or bottom of most pages: running headers and footers."""
    if len(page_lines) < 2:
        return set()
    counts: Counter[str] = Counter()
    for page in page_lines:
        counts.update({_edge_key(line) for line in page[:2] + page[-2:]})
    needed = max(2, (len(page_lines) + 1) // 2)
    return {key for key, count in counts.items() if count >= needed}
