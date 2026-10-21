"""Parse an eCFR part (versioner XML) into clause records.

A clause is a first-level paragraph such as 11.10(e); its nested paragraphs
((1), (i)) stay inside it, one per line, so Phase 2 can split oversize clauses
at subparagraph boundaries. Text before the first lettered paragraph becomes a
clause whose ID is the section number (e.g. the 11.10 intro, or all of 11.30).
"""

import re

from lxml import etree

from ingest.schema import Clause

LABEL = re.compile(r"^\(([a-z]+|\d+)\)")
ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
SECTION_HEAD = re.compile(r"^§\s*[\d.]+\s*")


def _text(el: etree._Element) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _level(label: str, current_level: int) -> int:
    """1 for (a), 2 for (1), 3 for (i). '(i)' is a letter unless we're inside a (1)."""
    if label.isdigit():
        return 2
    if label in ROMAN and current_level >= 2:
        return 3
    return 1


def parse_ecfr_part(
    xml: bytes, doc_id: str, version: str, effective_date: str | None
) -> list[Clause]:
    root = etree.fromstring(xml)
    clauses: list[Clause] = []

    for section in root.iter("DIV8"):
        number = section.get("N")
        head = section.find("HEAD")
        heading = _text(head) if head is not None else ""
        if not number or "[Reserved]" in heading:
            continue
        title = SECTION_HEAD.sub("", heading).rstrip(".")
        subpart = section.getparent()
        subpart_head = subpart.find("HEAD") if subpart is not None else None
        path = [_text(subpart_head)] if subpart_head is not None else []
        path.append(f"§ {number} {title}")

        current: Clause | None = None
        level = 0
        for p in section.iterfind("P"):
            text = _text(p)
            if not text:
                continue
            m = LABEL.match(text)
            if m:
                level = _level(m.group(1), level)
            if m and level == 1:
                current = Clause(
                    doc_id=doc_id,
                    version=version,
                    effective_date=effective_date,
                    section_path=path,
                    clause_id=f"{number}({m.group(1)})",
                    title=title,
                    text=text,
                )
                clauses.append(current)
            elif current is None:
                current = Clause(
                    doc_id=doc_id,
                    version=version,
                    effective_date=effective_date,
                    section_path=path,
                    clause_id=number,
                    title=title,
                    text=text,
                )
                clauses.append(current)
            else:
                current.text += "\n" + text
    return clauses
