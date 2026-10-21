"""Find references from a clause to other clauses or corpus documents.

Same-document references are stored as clause or section IDs ("11.50", "4.3").
A section ID stands for all of its clauses. References to another corpus
document are stored as its doc ID ("ICH-Q9R1"). References to documents
outside the corpus (ICH Q8, ISO standards) are ignored.
"""

import re

from ingest.schema import Clause

DOC_MENTIONS = {
    "21CFR11": re.compile(r"\b(?:21\s+CFR\s+)?[Pp]art\s+11\b"),
    "EUGMP-A11": re.compile(r"\bAnnex\s+11\b"),
    "ICH-Q9R1": re.compile(r"\bQ9\b"),
    "ICH-Q10": re.compile(r"\bQ10\b"),
}
CFR_REF = re.compile(r"\b(11\.\d+)((?:\([a-z0-9]+\))*)")
# "paragraph (a)(2) of this section", "paragraphs (a)(1), (a)(2), and (a)(3) of this section"
PARAGRAPH_OF_SECTION = re.compile(
    r"paragraphs?\s+((?:\([a-z0-9]+\)|,|\s|and|or)+?)\s*of\s+this\s+section"
)
SECTION_REF = re.compile(r"\b[Ss]ections?\s+((?:[IVX]+\.)?\d+(?:\.\d+)*)")
ANNEX_REF = re.compile(r"\bAnnex\s+([IVX]+|\d+)\b")


def _resolve(ref: str, ids: set[str]) -> str | None:
    if ref in ids:
        return ref
    if any(i.startswith((ref + ".", ref + "(", ref + ":")) for i in ids):
        return ref
    return None


def _section_of(clause_id: str) -> str:
    return clause_id.split("(")[0]


def find_cross_refs(clause: Clause, ids: set[str]) -> list[str]:
    text = clause.text
    candidates: list[str] = []

    if clause.doc_id == "21CFR11":
        for m in CFR_REF.finditer(text):
            subs = re.findall(r"\([a-z0-9]+\)", m.group(2))
            # Clauses are first-level paragraphs, so cite 11.10(k), not 11.10(k)(2).
            candidates.append(m.group(1) + (subs[0] if subs else ""))
        for m in PARAGRAPH_OF_SECTION.finditer(text):
            for letter in re.findall(r"\(([a-z])\)", m.group(1)):
                candidates.append(f"{_section_of(clause.clause_id)}({letter})")
    else:
        candidates += [m.group(1) for m in SECTION_REF.finditer(text)]
        candidates += [f"Annex {m.group(1)}" for m in ANNEX_REF.finditer(text)]

    own = {clause.clause_id, _section_of(clause.clause_id)}
    refs: list[str] = []
    for cand in candidates:
        resolved = _resolve(cand, ids)
        if resolved is None and "(" in cand:
            resolved = _resolve(_section_of(cand), ids)
        if resolved and resolved not in own and resolved not in refs:
            refs.append(resolved)

    for doc_id, pattern in DOC_MENTIONS.items():
        if doc_id != clause.doc_id and pattern.search(text) and doc_id not in refs:
            refs.append(doc_id)
    return refs


def add_cross_refs(clauses: list[Clause]) -> None:
    ids = {c.clause_id for c in clauses}
    for clause in clauses:
        clause.cross_refs = find_cross_refs(clause, ids)
