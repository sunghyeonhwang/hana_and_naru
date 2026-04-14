#!/usr/bin/env python3
"""Convert a story .md file (with inline HTML spans for blue/red terms) into a PDF.

Uses Chrome headless for rendering so Korean fonts, inline styles, and layout
all come out right. Expects Google Chrome at the standard macOS path.
"""

from __future__ import annotations

import argparse
import base64
import html as html_module
import mimetypes
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

HTML_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    @page {{
      size: A5;
      margin: 16mm 15mm 18mm 15mm;
      @bottom-center {{
        content: counter(page);
        font-family: "Apple SD Gothic Neo", sans-serif;
        font-size: 9pt;
        color: #888;
        padding-top: 6mm;
      }}
    }}
    html, body {{
      font-family: "Apple SD Gothic Neo", "Pretendard", "Nanum Gothic",
                   "맑은 고딕", "Malgun Gothic", "AppleGothic", sans-serif;
      color: #1a1a1a;
      line-height: 1.85;
      font-size: 11pt;
      letter-spacing: -0.005em;
      background: #ffffff;
      word-break: keep-all;
    }}
    body {{
      margin: 0;
    }}
    h1 {{
      font-family: "Apple SD Gothic Neo", "Pretendard", sans-serif;
      font-size: 19pt;
      font-weight: 800;
      text-align: center;
      margin: 0.2em 0 1.6em;
      letter-spacing: -0.02em;
      color: #111;
      line-height: 1.4;
    }}
    .cover {{
      page-break-after: always;
      break-after: page;
      width: 100%;
      height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0;
      padding: 0;
    }}
    .cover img {{
      max-width: 100%;
      max-height: 100vh;
      object-fit: contain;
      display: block;
    }}
    @page :first {{
      margin: 0;
      @bottom-center {{
        content: none;
      }}
    }}
    h2 {{
      font-size: 16pt;
      font-weight: 700;
      margin: 2em 0 0.7em;
      color: #222;
    }}
    h3 {{
      font-size: 14pt;
      font-weight: 700;
      margin: 1.4em 0 0.5em;
      color: #333;
    }}
    p {{
      margin: 0 0 1em;
      text-align: justify;
      text-justify: inter-character;
    }}
    .scene-break {{
      text-align: center;
      margin: 1.4em 0;
      color: #888;
      letter-spacing: 0.5em;
    }}
    /* Blue-term and red-star spans already carry inline styles from the
       source .md, so nothing extra needed — but we reinforce legibility. */
    span[style*="#1e6fd9"] {{
      color: #1e6fd9 !important;
      font-weight: 700 !important;
    }}
    span[style*="#dc2626"] {{
      color: #dc2626 !important;
      font-weight: 700 !important;
    }}
    /* Page break hint: start each first-level scene on its own chunk of page. */
    .scene {{
      break-inside: avoid-page;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def md_to_html(md: str) -> tuple[str, str]:
    """Very small subset markdown → HTML converter.

    Handles only what the skill's output format uses: `#`/`##`/`###` headings,
    `*` scene breaks, and plain paragraphs. Inline HTML spans already in the
    source are passed through untouched.
    """
    title = ""
    lines = md.splitlines()
    html_lines: list[str] = []
    paragraph_buffer: list[str] = []

    def flush_paragraph():
        if paragraph_buffer:
            joined = "<br>".join(paragraph_buffer)
            html_lines.append(f"<p>{joined}</p>")
            paragraph_buffer.clear()

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            continue

        if stripped == "*":
            flush_paragraph()
            html_lines.append('<p class="scene-break">* * *</p>')
            continue

        h = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if h:
            flush_paragraph()
            level = len(h.group(1))
            content = h.group(2).strip()
            if level == 1 and not title:
                title = re.sub(r"<[^>]+>", "", content)
            html_lines.append(f"<h{level}>{content}</h{level}>")
            continue

        paragraph_buffer.append(line)

    flush_paragraph()

    body = "\n".join(html_lines)
    return title or "소설", body


def render_pdf(md_path: Path, pdf_path: Path, cover: Path | None = None) -> None:
    md = md_path.read_text(encoding="utf-8")
    title, body = md_to_html(md)
    if cover is not None:
        mime, _ = mimetypes.guess_type(cover.name)
        mime = mime or "image/jpeg"
        b64 = base64.b64encode(cover.read_bytes()).decode("ascii")
        cover_html = (
            f'<div class="cover"><img src="data:{mime};base64,{b64}" alt="cover"></div>\n'
        )
        body = cover_html + body
    html = HTML_TEMPLATE.format(title=html_module.escape(title), body=body)

    with tempfile.TemporaryDirectory() as tmp:
        html_file = Path(tmp) / "story.html"
        html_file.write_text(html, encoding="utf-8")
        cmd = [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--default-background-color=FFFFFFFF",
            f"--print-to-pdf={pdf_path}",
            "--no-pdf-header-footer",
            "--virtual-time-budget=4000",
            html_file.as_uri(),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            raise SystemExit(f"Chrome failed (exit {result.returncode})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("md", type=Path, help="Source .md file")
    ap.add_argument("pdf", type=Path, help="Destination .pdf file")
    ap.add_argument("--cover", type=Path, default=None,
                    help="Optional cover image (jpg/png) for the first page")
    args = ap.parse_args()

    if not args.md.exists():
        raise SystemExit(f"Input not found: {args.md}")
    if args.cover is not None and not args.cover.exists():
        raise SystemExit(f"Cover image not found: {args.cover}")
    if not Path(CHROME).exists():
        raise SystemExit(f"Chrome not found at {CHROME}")

    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    render_pdf(args.md, args.pdf, cover=args.cover)
    print(f"→ {args.pdf}")


if __name__ == "__main__":
    main()
