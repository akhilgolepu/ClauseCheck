"""The parsed clause record shared by every parser (PRD section 6.2)."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Clause:
    doc_id: str
    version: str
    effective_date: str | None
    section_path: list[str]  # ancestor headings, outermost first
    clause_id: str  # unique within the document, e.g. "11.10(e)", "4.3", "7:Harm"
    title: str | None
    text: str
    cross_refs: list[str] = field(default_factory=list)  # "11.50" same-doc, "ICH-Q9R1" other doc
    page: int | None = None  # first page, for PDFs

    @property
    def key(self) -> str:
        """Corpus-wide ID used in eval gold labels, e.g. "21CFR11:11.10(e)"."""
        return f"{self.doc_id}:{self.clause_id}"


def write_jsonl(clauses: list[Clause], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for clause in clauses:
            f.write(json.dumps(asdict(clause), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[Clause]:
    with path.open() as f:
        return [Clause(**json.loads(line)) for line in f if line.strip()]
