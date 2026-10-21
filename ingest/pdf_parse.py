"""Parse numbered regulatory PDFs (EU GMP Annex 11, ICH Q9(R1), ICH Q10) into clauses.

A numbered line only opens a new clause when its number is a valid next step in
the outline (4.2 -> 4.3, 4.3 -> 4.3.1, 4.3 -> 5). That keeps numbered lists
inside the text ("1. What might go wrong?", reference lists) from being read
as sections. Annexes have their own numbering (I.1, II.3). Definition sections
are split into one clause per defined term, keyed "<section>:<term>".
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from ingest.pdf_lines import Line, visual_lines
from ingest.schema import Clause

NUMBER = re.compile(r"^(?P<num>(?:[IVX]+\s?\.\s?\d+)|(?:\d+\.)*\d+\.?)(?:\s+|$)(?P<rest>.*)$")
TERM = re.compile(r"^(?P<term>[^:]{2,80}?)\s*:\s*(?P<rest>.*)$")
BULLETS = re.compile(r"^[••▪◦-]\s*")
# (a) (iv) (12) a) a. 1. • -- but not a wrapped "(medicinal)"
LIST_START = re.compile(
    r"^(?:\((?:[a-z]|[ivx]{1,4}|\d{1,2})\)\s|[a-z]\)\s|[a-z]\.\s|\d{1,2}\.\s|•)"
)


@dataclass(frozen=True)
class PdfConfig:
    first_page: int
    numbered_must_be_bold: bool  # True when real section headings are always bold
    drop: re.Pattern[str] | None = None  # letterheads and similar noise
    group_headings: frozenset[str] = frozenset()  # unnumbered headings that only group sections
    clause_headings: frozenset[str] = frozenset()  # unnumbered headings that start a clause
    glossary_title: re.Pattern[str] = re.compile(r"^(GLOSSARY|DEFINITIONS)$", re.IGNORECASE)
    skip_sections: frozenset[str] = frozenset()
    annex: re.Pattern[str] | None = None  # "ANNEX I: ...", "Annex 1"


@dataclass
class _Open:
    clause_id: str
    title: str | None
    path: list[str]
    page: int
    parts: list[str] = field(default_factory=list)
    last: Line | None = None


def _parse_number(raw: str) -> tuple[str, tuple[int, ...], str | None]:
    """'4.3.' -> ('4.3', (4, 3), None); 'I .8' -> ('I.8', (8,), 'I')."""
    raw = re.sub(r"\s", "", raw).rstrip(".")
    parts = raw.split(".")
    if re.fullmatch(r"[IVX]+", parts[0]):
        return raw, tuple(int(p) for p in parts[1:]), parts[0]
    return raw, tuple(int(p) for p in parts), None


def _is_next(prev: tuple[int, ...] | None, cand: tuple[int, ...]) -> bool:
    """cand continues the outline from prev: a sibling/ancestor-sibling, or a first child."""
    if prev is None:
        return all(p == 1 for p in cand)
    if cand[: len(prev)] == prev and all(p == 1 for p in cand[len(prev) :]) and cand != prev:
        return True
    for k in range(1, len(prev) + 1):
        head = prev[: k - 1] + (prev[k - 1] + 1,)
        if cand[:k] == head and all(p == 1 for p in cand[k:]):
            return True
    return False


SMALL_WORDS = {"a", "an", "and", "as", "at", "for", "in", "into", "of", "on", "or", "the", "to"}


def _title_case(title: str) -> str:
    """'RISK MANAGEMENT METHODOLOGY' -> 'Risk Management Methodology'; mixed case is kept."""
    if not title.isupper():
        return title

    def fix(i: int, word: str) -> str:
        if re.fullmatch(r"[IVX]+:?", word):
            return word  # roman numerals: ANNEX II
        word = word.lower()
        return word if i and word in SMALL_WORDS else word[:1].upper() + word[1:]

    return " ".join(fix(i, w) for i, w in enumerate(title.split()))


class _Builder:
    def __init__(self, doc_id: str, version: str, effective_date: str | None) -> None:
        self.doc_id, self.version, self.effective_date = doc_id, version, effective_date
        self.clauses: list[Clause] = []
        self.open: _Open | None = None

    def start(self, clause_id: str, title: str | None, path: list[str], page: int) -> None:
        self.close()
        self.open = _Open(clause_id, title, list(path), page)

    def add(self, line: Line, text: str | None = None) -> None:
        if self.open is None:
            return
        text = BULLETS.sub("• ", text if text is not None else line.text)
        prev = self.open.last
        new_paragraph = prev is None or (
            line.page == prev.page and line.y - prev.y > 1.8 * line.size
        )
        if self.open.parts and not new_paragraph and not LIST_START.match(text):
            if self.open.parts[-1].endswith("-"):
                self.open.parts[-1] += text
            else:
                self.open.parts[-1] += " " + text
        else:
            self.open.parts.append(text)
        self.open.last = line

    def close(self) -> None:
        if self.open and self.open.parts:
            self.clauses.append(
                Clause(
                    doc_id=self.doc_id,
                    version=self.version,
                    effective_date=self.effective_date,
                    section_path=self.open.path,
                    clause_id=self.open.clause_id,
                    title=self.open.title,
                    text="\n".join(p.strip() for p in self.open.parts),
                    page=self.open.page,
                )
            )
        self.open = None


def parse_pdf(
    path: Path, config: PdfConfig, doc_id: str, version: str, effective_date: str | None
) -> list[Clause]:
    lines = [
        ln
        for ln in visual_lines(path, config.first_page)
        if not (config.drop and config.drop.search(ln.text))
    ]
    out = _Builder(doc_id, version, effective_date)
    stack: list[tuple[tuple[int, ...], str]] = []  # open numbered headings
    group: str | None = None  # Annex 11 "General" / Q9 "Annex I" style grouping
    annex: str | None = None  # roman prefix while inside a Q9-style annex
    prev_num: tuple[int, ...] | None = None
    section_id: str | None = None
    in_glossary = skipping = False
    heading: _Open | None = None  # heading still collecting wrapped title lines

    def section_path() -> list[str]:
        return ([group] if group else []) + [label for _, label in stack]

    i = 0
    while i < len(lines):
        ln = lines[i]
        text = ln.text
        i += 1

        # A bold line straight after a bold heading continues its title when it is
        # upper-case or short (long bold lines are lead-in sentences); annex titles
        # take any bold continuation.
        if heading is not None and heading.last is not None:
            is_annex = heading.clause_id.startswith("Annex")
            close_below = ln.page == heading.last.page and 0 < ln.y - heading.last.y < 1.8 * ln.size
            short = text.isupper() or len(text) < 60 or is_annex
            if ln.bold and close_below and short and not NUMBER.match(text):
                heading.title = f"{heading.title} {_title_case(text.rstrip(' *'))}".strip()
                heading.last = ln
                if is_annex:
                    group = heading.title
                elif stack and stack[-1][1].split(" ")[0] == heading.clause_id:
                    stack[-1] = (stack[-1][0], f"{heading.clause_id} {heading.title}")
                continue
            heading = None

        if config.annex and ln.bold and (m := config.annex.match(text)):
            out.close()
            stack.clear()
            annex = m.group("id")
            group = _title_case(text.rstrip(" *"))
            prev_num, section_id, in_glossary, skipping = None, None, False, False
            # Q10-style annexes have no numbered subsections: the annex is one clause.
            out.start(f"Annex {annex}", group, [], ln.page)
            heading = out.open
            if heading is not None:
                heading.last = ln
            continue

        if ln.bold and text in config.group_headings:
            out.close()
            group, stack, section_id, in_glossary = text, [], None, False
            continue

        if ln.bold and text in config.clause_headings:
            stack.clear()
            group = None
            in_glossary = bool(config.glossary_title.match(text))
            section_id = text
            out.start(text, text, [], ln.page)
            if in_glossary:
                out.close()
            continue

        m = NUMBER.match(text)
        if m and (ln.bold or not config.numbered_must_be_bold):
            num_id, num, prefix = _parse_number(m.group("num"))
            if prefix == annex and num and _is_next(prev_num, num):
                prev_num = num
                rest = m.group("rest").strip()
                while stack and len(stack[-1][0]) >= len(num):
                    stack.pop()
                section_id = num_id
                skipping = num_id.split(".")[0] in config.skip_sections
                title = rest if ln.bold and rest else None
                in_glossary = bool(title and config.glossary_title.match(title))
                out.start(num_id, _title_case(title) if title else None, section_path(), ln.page)
                stack.append((num, f"{num_id} {_title_case(title)}" if title else num_id))
                heading = out.open if title else None
                if heading is not None:
                    heading.last = ln
                if not title and rest:
                    out.add(ln, rest)
                if in_glossary:
                    out.close()
                continue

        if skipping:
            continue

        if in_glossary and ln.bold and (t := TERM.match(text)):
            term = t.group("term").strip()
            out.start(f"{section_id}:{term}", term, section_path(), ln.page)
            if t.group("rest").strip():
                out.add(ln, t.group("rest").strip())
            continue

        out.add(ln)

    out.close()
    return out.clauses


ANNEX11 = PdfConfig(
    first_page=2,
    numbered_must_be_bold=False,
    drop=re.compile(r"Commission Européenne|B-1049 Brussel|Telephone: \(32-2\)"),
    group_headings=frozenset({"General", "Project Phase", "Operational Phase"}),
    clause_headings=frozenset({"Principle", "Glossary"}),
)

ICH_Q9R1 = PdfConfig(
    first_page=5,
    numbered_must_be_bold=True,
    skip_sections=frozenset({"8"}),  # reference list
    annex=re.compile(r"^ANNEX\s+(?P<id>[IVX]+)\s*:"),
)

ICH_Q10 = PdfConfig(
    first_page=5,
    numbered_must_be_bold=True,
    annex=re.compile(r"^Annex\s+(?P<id>\d+)$"),
)
