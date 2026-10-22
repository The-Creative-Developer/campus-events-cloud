"""Rebuild the PDFs in submission/ from the Markdown docs.

    pip install markdown-it-py
    python3 scripts/build_pdfs.py

Converts Markdown to styled HTML (CommonMark, same rules as GitHub), then
prints it to PDF with headless Google Chrome.
"""

import shutil
import subprocess  # noqa: S404 (runs Chrome with fixed arguments)
import sys
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    ("docs/task1-architecture.md", "submission/Task1-Cloud-Architecture.pdf", "Task 1 Cloud Architecture"),
    ("docs/task3-devops-workflow.md", "submission/Task3-DevOps-Workflow.pdf", "Task 3 DevOps Workflow"),
    ("docs/INTERVIEW_GUIDE.md", "submission/Interview-Guide.pdf", "Interview Guide"),
]
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
]
CSS = """
@page { size: A4; margin: 16mm 15mm 18mm; }
body { font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; color:#16191f; font-size:10.4pt;
       line-height:1.5; }
h1 { font-size:21pt; margin:0 0 6px; border-bottom:3px solid #ff9900; padding-bottom:6px; }
h2 { font-size:14.5pt; margin-top:22px; color:#232f3e; border-bottom:1px solid #d5dbe1; padding-bottom:3px;
     break-after:avoid; }
h3 { font-size:12pt; margin-top:16px; color:#232f3e; break-after:avoid; }
table { border-collapse:collapse; width:100%; margin:8px 0 12px; font-size:9.2pt; }
th, td { border:1px solid #d5dbe1; padding:4px 7px; text-align:left; vertical-align:top; }
th { background:#f2f4f7; }
tr { break-inside:avoid; }
code { font-family:'SF Mono', Menlo, Consolas, monospace; font-size:8.8pt; background:#f2f4f7; padding:1px 4px;
       border-radius:3px; }
pre { background:#f6f8fa; border:1px solid #e1e4e8; border-radius:6px; padding:8px 10px; white-space:pre-wrap;
      break-inside:avoid; }
pre code { background:none; padding:0; }
blockquote { margin:8px 0; padding:6px 12px; border-left:4px solid #ff9900; background:#fff8ec; }
img { max-width:100%; border:1px solid #e1e4e8; border-radius:6px; margin:6px 0; }
hr { border:none; border-top:1px solid #e1e4e8; margin:18px 0; }
a { color:#0b62c4; text-decoration:none; word-break:break-all; }
"""


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    sys.exit("Google Chrome or Chromium is required to print PDFs.")


def main() -> None:
    chrome = find_chrome()
    md = MarkdownIt("commonmark").enable("table")
    for src_rel, out_rel, title in DOCS:
        src, out = ROOT / src_rel, ROOT / out_rel
        html = (
            f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>"
            f"<base href='{src.parent.as_uri()}/'><style>{CSS}</style></head>"
            f"<body>{md.render(src.read_text())}</body></html>"
        )
        tmp = out.with_suffix(".tmp.html")
        tmp.write_text(html)
        out.unlink(missing_ok=True)
        try:
            subprocess.run(  # noqa: S603
                [
                    chrome,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={out}",
                    tmp.as_uri(),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            # Headless Chrome occasionally writes the PDF and then fails to exit.
            if not out.exists():
                raise
        finally:
            tmp.unlink(missing_ok=True)
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
