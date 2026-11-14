"""Reading report files: Markdown and text as before, PDFs through their text layer."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from apps.api.app.main import app
from second_opinion.extract import extract_claims
from second_opinion.report_file import ReportFileError, clean_pdf_text, read_report_file

ROOT = Path(__file__).resolve().parents[1]
PDFS = Path(__file__).resolve().parent / "pdf"
PRACTICE_BRIEF = ROOT / "docs/challenge/products/research-claim-auditor/practice_brief.md"
# Each fixture is its Markdown source printed by Chrome (tests/pdf/make_fixtures.py) on small pages
# with a running header and a "Page n of m" footer.
PDF_SOURCES = {
    "practice_brief.pdf": PRACTICE_BRIEF,
    "report_13.pdf": ROOT / "tests/reports/report_13.md",
}

client = TestClient(app)


def _claims(text: str) -> list[tuple[str, str]]:
    return [(c.type.value, c.text) for c in extract_claims(text).claims]


def _pdf_bytes(writer: PdfWriter) -> bytes:
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.mark.parametrize("name", PDF_SOURCES)
def test_a_pdf_gives_the_same_claims_as_its_markdown(name):
    read = read_report_file((PDFS / name).read_bytes(), name)
    assert read.kind == "pdf"
    assert _claims(read.text) == _claims(PDF_SOURCES[name].read_text(encoding="utf-8"))


def test_pdf_page_furniture_is_dropped():
    read = read_report_file((PDFS / "report_13.pdf").read_bytes(), "report_13.pdf")
    assert read.pages == 3
    assert "Draft report" not in read.text
    assert "Page 2 of 3" not in read.text
    assert "HER2-positive" in read.text  # "HER2-" at a line end joined back to "positive"


def test_a_sentence_broken_across_pages_is_joined():
    text = clean_pdf_text([
        "Running title\nThe 1,101 primary tumors came from 1,085 women and\n1",
        "Running title\n12 men, with sex missing for 4.\n2",
    ])
    assert "\n\n" not in text.strip()  # one paragraph, so the extractor reads one sentence
    assert " ".join(text.split()) == "The 1,101 primary tumors came from 1,085 women and 12 men, with sex missing for 4."


def test_running_lines_with_changing_page_numbers_are_dropped():
    body = ["Luminal A is the largest subtype.", "Basal-like is next.", "Normal-like is the smallest."]
    pages = [f"Claim audit - draft {n}\n{line}\nPage {n} of 3" for n, line in enumerate(body, start=1)]
    assert " ".join(clean_pdf_text(pages).split()) == " ".join(body)


def test_a_heading_is_kept_apart_from_the_next_sentence():
    text = clean_pdf_text([
        "Of the 1,101 primary tumors in the release, 535 have survival, mutation,\n"
        "copy number, RNA and protein data, which is the full set of layers.\n"
        "Subtypes\n"
        "Luminal A is the largest RNA subtype, accounting for about 62% of primary\n"
        "tumors with an RNA subtype call, and Basal-like is the second largest.\n"
    ])
    assert "\n\nSubtypes\n\n" in text
    assert [t for _, t in _claims(text)][-1].startswith("Luminal A is the largest RNA subtype")


def test_ligatures_and_soft_hyphens_are_undone():
    assert clean_pdf_text(["ﬁve ﬂagged tu­mors"]).strip() == "five flagged tumors"


def test_a_pdf_without_text_is_refused():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pytest.raises(ReportFileError, match="no text"):
        read_report_file(_pdf_bytes(writer), "scan.pdf")


def test_a_password_protected_pdf_is_refused():
    writer = PdfWriter(clone_from=PDFS / "practice_brief.pdf")
    writer.encrypt(user_password="secret", algorithm="RC4-128")
    with pytest.raises(ReportFileError, match="password"):
        read_report_file(_pdf_bytes(writer), "locked.pdf")


def test_a_broken_pdf_is_refused():
    with pytest.raises(ReportFileError, match="Could not read this PDF"):
        read_report_file(b"%PDF-1.7\nnot really a pdf", "broken.pdf")


def test_a_binary_file_is_refused():
    with pytest.raises(ReportFileError, match="not a Markdown, text or PDF"):
        read_report_file(b"PK\x03\x04\x00\x00binary", "report.docx")


def test_a_pdf_is_known_by_its_header_whatever_its_name():
    assert read_report_file((PDFS / "practice_brief.pdf").read_bytes(), "download").kind == "pdf"


def test_markdown_and_text_are_decoded_as_before():
    assert read_report_file("﻿# Title\nCafé".encode("utf-8"), "r.md").text == "# Title\nCafé"
    read = read_report_file("Caf\xe9".encode("cp1252"), "r.txt")
    assert (read.kind, read.text, read.pages) == ("text", "Café", None)


def test_api_reads_an_uploaded_pdf():
    data = (PDFS / "practice_brief.pdf").read_bytes()
    response = client.post("/report-file", files={"file": ("brief.pdf", data, "application/pdf")})
    assert response.status_code == 200
    body = response.json()
    assert (body["filename"], body["kind"], body["pages"]) == ("brief.pdf", "pdf", 1)
    extracted = client.post("/extract", json={"report_text": body["text"]}).json()
    assert [c["type"] for c in extracted["claims"]] == ["COUNT", "SHARE", "NOT_ANSWERABLE"]


def test_api_reads_an_uploaded_markdown_file():
    data = PRACTICE_BRIEF.read_bytes()
    body = client.post("/report-file", files={"file": ("brief.md", data, "text/markdown")}).json()
    assert body["kind"] == "markdown"
    assert body["text"] == PRACTICE_BRIEF.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("data", "detail"),
    [(b"", "empty"), (b"%PDF-1.7\nbroken", "Could not read this PDF")],
)
def test_api_refuses_unreadable_files_with_a_message(data, detail):
    response = client.post("/report-file", files={"file": ("r.pdf", data, "application/pdf")})
    assert response.status_code == 422
    assert detail in response.json()["detail"]


def test_cli_reads_a_pdf_report():
    from second_opinion.cli import read_report

    assert _claims(read_report(str(PDFS / "practice_brief.pdf"))) == _claims(PRACTICE_BRIEF.read_text(encoding="utf-8"))
