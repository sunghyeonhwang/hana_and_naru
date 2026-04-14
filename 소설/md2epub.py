#!/usr/bin/env python3
"""Convert a story .md file (with inline HTML spans for blue/red terms)
into an EPUB 3 file. Uses only the Python standard library.

Usage:
    python md2epub.py <story.md> <out.epub> --cover <cover.jpg> --title "..." --author "..."
"""

from __future__ import annotations

import argparse
import mimetypes
import re
import uuid
import zipfile
from datetime import datetime, timezone
from html import escape as h
from pathlib import Path


# ---------- markdown → xhtml ----------

SCENE_BREAK = '<p class="scene-break">* * *</p>'


def md_to_xhtml(md: str) -> tuple[str, str]:
    """Return (title, body_xhtml).

    Handles only the subset that the skill outputs: ``#`` headings, blank-line
    paragraphs, and ``*`` scene breaks. Inline HTML spans are passed through.
    The body is wrapped in `<section>` so we can drop it into the main XHTML
    template later.
    """
    title = ""
    out: list[str] = []
    para: list[str] = []

    def flush():
        if para:
            joined = "<br/>".join(para)
            out.append(f"<p>{joined}</p>")
            para.clear()

    for raw in md.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush()
            continue

        if stripped == "*":
            flush()
            out.append(SCENE_BREAK)
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush()
            level = len(m.group(1))
            content = m.group(2).strip()
            if level == 1 and not title:
                title = re.sub(r"<[^>]+>", "", content)
            out.append(f"<h{level}>{content}</h{level}>")
            continue

        para.append(line)

    flush()
    return title or "소설", "\n".join(out)


# ---------- EPUB asset templates ----------

CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

STYLES_CSS = """@charset "utf-8";

@font-face {
  font-family: "AppleGothic";
  src: local("Apple SD Gothic Neo"), local("AppleSDGothicNeo"), local("AppleGothic");
}

html, body {
  margin: 0;
  padding: 0;
  font-family: "Apple SD Gothic Neo", "Pretendard", "Nanum Gothic",
               "맑은 고딕", "Malgun Gothic", "AppleGothic", sans-serif;
  color: #1a1a1a;
  line-height: 2.0;
  word-break: keep-all;
  -epub-hyphens: none;
  hyphens: none;
}

body {
  padding: 1em 1.2em;
}

h1 {
  font-size: 1.6em;
  font-weight: 800;
  text-align: center;
  margin: 1.4em 0 1.6em;
  letter-spacing: -0.02em;
  color: #111;
  line-height: 1.4;
}

h2 {
  font-size: 1.2em;
  font-weight: 700;
  margin: 1.6em 0 0.6em;
  color: #222;
}

h3 {
  font-size: 1.05em;
  font-weight: 700;
  margin: 1.3em 0 0.5em;
  color: #333;
}

p {
  margin: 0 0 0.9em;
  text-align: justify;
}

p.scene-break {
  text-align: center;
  margin: 1.4em 0;
  color: #888;
  letter-spacing: 0.5em;
}

/* The blue and red spans already carry inline color, but we reinforce
   them in case a reader app ignores the inline style. */
span[style*="#1e6fd9"] {
  color: #1e6fd9 !important;
  font-weight: 700 !important;
}
span[style*="#dc2626"] {
  color: #dc2626 !important;
  font-weight: 700 !important;
}

/* Cover */
section.cover {
  margin: 0;
  padding: 0;
  text-align: center;
  page-break-after: always;
  break-after: page;
}
section.cover img {
  width: 100%;
  max-width: 100%;
  height: auto;
}
"""

NAV_XHTML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ko">
<head>
<meta charset="utf-8"/>
<title>목차</title>
<link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
<nav epub:type="toc" id="toc">
<h1>목차</h1>
<ol>
{items}
</ol>
</nav>
</body>
</html>
"""

CHAPTER_XHTML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="ko">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
{body}
</body>
</html>
"""

COVER_XHTML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="ko">
<head>
<meta charset="utf-8"/>
<title>표지</title>
<link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
<section class="cover" epub:type="cover">
<img src="{cover_filename}" alt="표지"/>
</section>
</body>
</html>
"""

CONTENT_OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="ko">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{book_id}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>ko</dc:language>
    <meta property="dcterms:modified">{modified}</meta>
{cover_meta}
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="styles" href="styles.css" media-type="text/css"/>
{cover_manifest}
    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
{cover_spine}
    <itemref idref="chapter"/>
  </spine>
</package>
"""


# ---------- builder ----------

def build_epub(
    md_path: Path,
    epub_path: Path,
    cover_path: Path | None,
    title_override: str | None,
    author: str,
) -> None:
    md = md_path.read_text(encoding="utf-8")
    parsed_title, body = md_to_xhtml(md)
    title = title_override or parsed_title

    chapter = CHAPTER_XHTML.format(title=h(title), body=body)
    nav_items = f'        <li><a href="chapter.xhtml">{h(title)}</a></li>'
    nav = NAV_XHTML.format(items=nav_items)

    book_id = f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if cover_path is not None:
        ext = cover_path.suffix.lower().lstrip(".")
        if ext == "jpg":
            ext = "jpeg"
        cover_filename = f"cover.{ext}"
        cover_mime, _ = mimetypes.guess_type(cover_path.name)
        cover_mime = cover_mime or "image/jpeg"
        cover_meta = '    <meta name="cover" content="cover-image"/>'
        cover_manifest = (
            f'    <item id="cover-image" href="{cover_filename}" '
            f'media-type="{cover_mime}" properties="cover-image"/>\n'
            '    <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>'
        )
        cover_spine = '    <itemref idref="cover" linear="yes"/>'
    else:
        cover_filename = None
        cover_meta = ""
        cover_manifest = ""
        cover_spine = ""

    opf = CONTENT_OPF.format(
        book_id=book_id,
        title=h(title),
        author=h(author),
        modified=modified,
        cover_meta=cover_meta,
        cover_manifest=cover_manifest,
        cover_spine=cover_spine,
    )

    epub_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(epub_path, "w") as zf:
        # mimetype must be FIRST and STORED (uncompressed)
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr("META-INF/container.xml", CONTAINER_XML, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/nav.xhtml", nav, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/styles.css", STYLES_CSS, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/chapter.xhtml", chapter, zipfile.ZIP_DEFLATED)
        if cover_path is not None:
            cover_xhtml = COVER_XHTML.format(cover_filename=cover_filename)
            zf.writestr("OEBPS/cover.xhtml", cover_xhtml, zipfile.ZIP_DEFLATED)
            zf.writestr(f"OEBPS/{cover_filename}",
                        cover_path.read_bytes(),
                        zipfile.ZIP_STORED)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("md", type=Path, help="Source .md file")
    ap.add_argument("epub", type=Path, help="Destination .epub file")
    ap.add_argument("--cover", type=Path, default=None, help="Cover image (jpg/png)")
    ap.add_argument("--title", default=None, help="Override title")
    ap.add_argument("--author", default="림쌤의 필기노트 × 하나와 나루",
                    help="Author / creator")
    args = ap.parse_args()

    if not args.md.exists():
        raise SystemExit(f"Input not found: {args.md}")
    if args.cover is not None and not args.cover.exists():
        raise SystemExit(f"Cover not found: {args.cover}")

    build_epub(args.md, args.epub, args.cover, args.title, args.author)
    print(f"→ {args.epub}")


if __name__ == "__main__":
    main()
