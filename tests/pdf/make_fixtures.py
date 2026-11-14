"""Rebuild the PDF test fixtures from Markdown reports, printed by headless Chrome or Edge.

Run by hand when a source report changes (the tests only read the committed PDFs):
  python tests/pdf/make_fixtures.py [path/to/chrome-or-msedge]

Each report is printed on small pages, justified and hyphenated, with a running header and a
"Page n of m" footer, so the fixtures carry what real PDFs add: sentences broken across pages,
words split at line ends, and lines repeated on every page.
"""

import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = {
    "practice_brief.pdf": ROOT / "docs/challenge/products/research-claim-auditor/practice_brief.md",
    "report_13.pdf": ROOT / "tests/reports/report_13.md",
}
BROWSERS = [
    "chrome", "google-chrome", "chromium", "msedge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
CSS = """
@page {
  size: 105mm 148mm; margin: 16mm 10mm;
  @top-center { content: "Draft report - not for circulation"; font: 8pt sans-serif; }
  @bottom-center { content: "Page " counter(page) " of " counter(pages); font: 8pt sans-serif; }
}
body { font: 10pt/1.35 Georgia, serif; text-align: justify; hyphens: auto; }
h1 { font-size: 13pt; } h2 { font-size: 11pt; }
"""


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)


def to_html(markdown: str) -> str:
    """Enough Markdown for our reports: headings and paragraphs."""
    parts = []
    for block in re.split(r"\n\s*\n", markdown.strip()):
        heading = re.match(r"(#{1,6})\s+(.*)", block)
        if heading:
            level = len(heading.group(1))
            parts.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        else:
            parts.append(f"<p>{inline(' '.join(block.split()))}</p>")
    body = "\n".join(parts)
    return f'<!doctype html><html lang="en"><meta charset="utf-8"><style>{CSS}</style><body>{body}</body></html>'


def main() -> None:
    browser = sys.argv[1] if len(sys.argv) > 1 else next(
        (b for b in BROWSERS if shutil.which(b) or Path(b).is_file()), None
    )
    if browser is None:
        raise SystemExit("No Chrome or Edge found; pass its path as the first argument.")
    with tempfile.TemporaryDirectory() as tmp:
        for name, source in SOURCES.items():
            page = Path(tmp) / "report.html"
            page.write_text(to_html(source.read_text(encoding="utf-8")), encoding="utf-8")
            subprocess.run(
                [browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                 f"--user-data-dir={Path(tmp) / 'profile'}", f"--print-to-pdf={HERE / name}", page.as_uri()],
                check=True, capture_output=True, timeout=120,
            )
            print(f"wrote {HERE / name}")


if __name__ == "__main__":
    main()
