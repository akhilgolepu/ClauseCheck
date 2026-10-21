"""Turn a PDF into reading-order visual lines, without running heads and page numbers.

PyMuPDF often emits a section number and its heading as separate lines (they
sit in different text blocks at the same height). Grouping spans by baseline
puts them back together, so "1.1" + "Introduction" becomes "1.1 Introduction".
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

HEADER_MARGIN = 60  # points from the top of the page: always dropped
FOOTER_MARGIN = 65  # points from the bottom: page numbers dropped
RUNNING_MARGIN = 0.12  # top/bottom fraction of the page where running heads live
RUNNING_MIN_PAGES = 3
BASELINE_TOLERANCE = 3.0
PAGE_NUMBER = re.compile(r"(?:page\s+)?\d+(?:\s*/\s*\d+)?|[ivxlc]+", re.IGNORECASE)
PRIVATE_USE = re.compile(r"[-]")  # symbol-font bullets


@dataclass(frozen=True)
class Line:
    page: int  # 1-based
    y: float
    x: float
    size: float
    bold: bool  # True when the first span that isn't a bare number is bold
    text: str
    in_margin: bool = False  # inside the running-head zone at top or bottom


def _is_bold(span: dict) -> bool:
    return "Bold" in span["font"] or bool(span["flags"] & 16)


def _page_lines(page: pymupdf.Page) -> list[Line]:
    height = page.rect.height
    spans = sorted(
        (
            (span["bbox"][3], span["bbox"][0], span)
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", [])
            for span in line["spans"]
            if span["text"].strip()
        ),
        key=lambda s: (s[0], s[1]),
    )
    rows: list[list[tuple[float, float, dict]]] = []
    for item in spans:
        if rows and abs(rows[-1][0][0] - item[0]) <= BASELINE_TOLERANCE:
            rows[-1].append(item)
        else:
            rows.append([item])

    tables = [t for t in page.find_tables().tables if t.row_count >= 2]
    lines = _table_lines(page, tables)
    for row in rows:
        row.sort(key=lambda s: s[1])
        text = " ".join(s[2]["text"].strip() for s in row)
        text = re.sub(r"\s+", " ", PRIVATE_USE.sub("•", text)).strip()
        y, x = row[0][0], row[0][1]
        if y < HEADER_MARGIN or (y > height - FOOTER_MARGIN and PAGE_NUMBER.fullmatch(text)):
            continue
        if any(t.bbox[1] <= y <= t.bbox[3] for t in tables):
            continue  # row-merged table text; replaced by _table_lines
        words = [s[2] for s in row if not re.fullmatch(r"[\d.IVX]+", s[2]["text"].strip())]
        lines.append(
            Line(
                page=page.number + 1,
                y=y,
                x=x,
                size=round(row[0][2]["size"], 1),
                bold=_is_bold(words[0]) if words else _is_bold(row[0][2]),
                text=text,
                in_margin=y < RUNNING_MARGIN * height or y > (1 - RUNNING_MARGIN) * height,
            )
        )
    return sorted(lines, key=lambda ln: ln.y)


def _cell_text(page: pymupdf.Page, bbox: tuple[float, float, float, float] | None) -> str:
    """A cell's words in reading order (PyMuPDF's own cell text drops spaces)."""
    if bbox is None:
        return ""
    words = sorted(
        page.get_text("words", clip=pymupdf.Rect(bbox)), key=lambda w: (round(w[3]), w[0])
    )
    return re.sub(r"\s+", " ", " ".join(w[4] for w in words)).strip()


def _table_lines(page: pymupdf.Page, tables: list) -> list[Line]:
    """One '• Header: cell' line per body cell, placed at the top of its table.

    Merging a table's text by baseline interleaves its columns; reading cell by
    cell keeps each column's text intact and labels it with its header.
    """
    lines = []
    for table in tables:
        header = [_cell_text(page, bbox) for bbox in table.rows[0].cells]
        n = 0
        for row in table.rows[1:]:
            for head, bbox in zip(header, row.cells, strict=False):
                cell = _cell_text(page, bbox)
                if not cell:
                    continue
                text = PRIVATE_USE.sub("•", f"• {head}: {cell}" if head else f"• {cell}")
                n += 1
                lines.append(
                    Line(
                        page=page.number + 1,
                        y=table.bbox[1] + n * 0.001,
                        x=table.bbox[0],
                        size=11.0,
                        bold=False,
                        text=re.sub(r"\s+", " ", text),
                    )
                )
    return lines


def visual_lines(path: Path, first_page: int = 1) -> list[Line]:
    """Lines from first_page (1-based) onward, top to bottom, left to right.

    Drops page numbers and running heads: text that recurs in the top or bottom
    margin of at least RUNNING_MIN_PAGES pages.
    """
    with pymupdf.open(path) as doc:
        lines = [ln for page in doc.pages(first_page - 1) for ln in _page_lines(page)]
    margin_pages: dict[str, set[int]] = {}
    for ln in lines:
        if ln.in_margin:
            margin_pages.setdefault(ln.text, set()).add(ln.page)
    running = {t for t, pages in margin_pages.items() if len(pages) >= RUNNING_MIN_PAGES}
    return [ln for ln in lines if not (ln.in_margin and ln.text in running)]
