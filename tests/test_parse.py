"""Parser tests against the real corpus (skipped until `python -m ingest.fetch` has run).

The spot checks were verified against the source text: the eCFR XML for Part 11
and PyMuPDF's raw page text for the PDFs, independently of this parser.
"""

import pytest

from core.settings import PROJECT_ROOT, get_settings
from ingest.fetch import load_manifest
from ingest.parse import parse_document
from ingest.schema import Clause

MANIFEST = load_manifest(get_settings().corpus_manifest_path)
HAVE_RAW = bool(MANIFEST["documents"]) and all(
    (PROJECT_ROOT / d["file"]).is_file() for d in MANIFEST["documents"]
)
pytestmark = pytest.mark.skipif(not HAVE_RAW, reason="raw corpus not fetched")


@pytest.fixture(scope="module")
def corpus() -> dict[str, dict[str, Clause]]:
    return {d["doc_id"]: {c.clause_id: c for c in parse_document(d)} for d in MANIFEST["documents"]}


EXPECTED_COUNTS = {"21CFR11": 47, "EUGMP-A11": 41, "ICH-Q9R1": 60, "ICH-Q10": 62}


@pytest.mark.parametrize("doc_id,count", EXPECTED_COUNTS.items())
def test_clause_counts(corpus: dict[str, dict[str, Clause]], doc_id: str, count: int) -> None:
    assert len(corpus[doc_id]) == count


# (doc_id, clause_id, title, snippet that must appear in the clause text)
SPOT_CHECKS = [
    ("21CFR11", "11.10", "Controls for closed systems", "Persons who use closed systems to create"),
    ("21CFR11", "11.10(e)", "Controls for closed systems", "(e) Use of secure, computer-generated, time-stamped audit trails"),
    ("21CFR11", "11.10(e)", "Controls for closed systems", "shall be available for agency review and copying."),
    ("21CFR11", "11.30", "Controls for open systems", "Persons who use open systems to create"),
    ("21CFR11", "11.50(a)", "Signature manifestations", "(a) Signed electronic records shall contain information associated with the signing"),
    ("21CFR11", "11.100(a)", "General requirements", "shall not be reused by, or reassigned to, anyone else."),
    ("21CFR11", "11.200(a)", "Electronic signature components and controls", "requires collaboration of two or more individuals."),
    ("EUGMP-A11", "Principle", "Principle", "There should be no increase in the overall risk of the process."),
    ("EUGMP-A11", "1", "Risk Management", "based on a justified and documented risk assessment of the computerised system."),
    ("EUGMP-A11", "4.8", None, "If data are transferred to another data format or system"),
    ("EUGMP-A11", "9", "Audit Trails", "convertible to a generally intelligible form and regularly reviewed."),
    ("EUGMP-A11", "12.4", None, "entering, changing, confirming or deleting data including date and time."),
    ("EUGMP-A11", "Glossary:System owner", "System owner", "The person responsible for the availability, and maintenance"),
    ("ICH-Q9R1", "4.4", "Risk Control", "1. Is the risk above an acceptable level?"),
    ("ICH-Q9R1", "4.4", "Risk Control", "Risk acceptance is a decision to accept risk."),
    ("ICH-Q9R1", "I.8", "Risk Ranking and Filtering", "Risk ranking and filtering is a tool for comparing and ranking risks."),
    ("ICH-Q9R1", "7:Harm", "Harm", "Damage to health, including the damage that can occur from loss of product quality or availability."),
    ("ICH-Q10", "1.6.2", "Quality Risk Management", "ICH Q9 provides principles and examples of tools for quality risk management"),
    ("ICH-Q10", "3.2.2", "Corrective Action and Preventive Action (CAPA) System", "The pharmaceutical company should have a system for implementing corrective actions"),
    ("ICH-Q10", "5:Quality Manual", "Quality Manual", "Document specifying the quality management system of an organisation."),
]  # fmt: skip


@pytest.mark.parametrize("doc_id,clause_id,title,snippet", SPOT_CHECKS)
def test_spot_check(
    corpus: dict[str, dict[str, Clause]],
    doc_id: str,
    clause_id: str,
    title: str | None,
    snippet: str,
) -> None:
    clause = corpus[doc_id][clause_id]
    assert clause.title == title
    assert snippet in clause.text.replace("\n", " ")


def test_wrapped_heading_titles_are_joined(corpus: dict[str, dict[str, Clause]]) -> None:
    assert corpus["ICH-Q10"]["1.3"].title == (
        "Relationship of ICH Q10 to Regional GMP Requirements, ISO Standards and ICH Q7"
    )


def test_section_paths(corpus: dict[str, dict[str, Clause]]) -> None:
    assert corpus["21CFR11"]["11.10(e)"].section_path == [
        "Subpart B—Electronic Records",
        "§ 11.10 Controls for closed systems",
    ]
    assert corpus["EUGMP-A11"]["4.8"].section_path == ["Project Phase", "4 Validation"]
    assert (
        corpus["ICH-Q10"]["3.2.2"].section_path[-1] == "3.2 Pharmaceutical Quality System Elements"
    )
    assert corpus["ICH-Q9R1"]["I.8"].section_path == [
        "Annex I: Quality Risk Management Methods and Tools"
    ]


def test_nested_paragraphs_stay_inside_first_level_clause(
    corpus: dict[str, dict[str, Clause]],
) -> None:
    text = corpus["21CFR11"]["11.200(a)"].text
    assert "\n(1) Employ at least two distinct identification components" in text
    assert "\n(ii) When an individual executes one or more signings" in text
    assert "11.10(i)" in corpus["21CFR11"]  # (i) after (h) is a letter, not a roman numeral


def test_cross_refs(corpus: dict[str, dict[str, Clause]]) -> None:
    assert "11.10" in corpus["21CFR11"]["11.30"].cross_refs
    assert corpus["21CFR11"]["11.50(b)"].cross_refs == ["11.50(a)"]  # "paragraphs (a)(1), ..."
    assert "ICH-Q9R1" in corpus["ICH-Q10"]["1.6.2"].cross_refs
    assert "Annex II" in corpus["ICH-Q9R1"]["6"].cross_refs


def test_tables_are_read_cell_by_cell(corpus: dict[str, dict[str, Clause]]) -> None:
    text = corpus["ICH-Q10"]["3.2.2"].text
    assert "\n• Technology Transfer: CAPA can be used as an effective system for feedback" in text
    assert (
        "\n• Product Discontinuation: CAPA should continue after the product is discontinued."
        in text
    )
    # no interleaved column text from the old row-merged extraction
    assert "CAPA can be used as CAPA should be used" not in text
    assert "• Scenario: 1. Comply with GMPs" in corpus["ICH-Q10"]["Annex 1"].text


def test_noise_is_dropped(corpus: dict[str, dict[str, Clause]]) -> None:
    texts = [c.text for doc in corpus.values() for c in doc.values()]
    assert not any("Commission Européenne" in t for t in texts)  # Annex 11 letterhead
    assert not any("ISBN" in t for t in texts)  # Q9(R1) reference list is skipped
    assert not any(t.endswith("Pharmaceutical Quality System") for t in texts)  # Q10 footer
    assert not any("" in t for t in texts)  # symbol-font bullets
    assert "8" not in corpus["ICH-Q9R1"]
    # Numbered list items inside a clause must not become clauses of their own.
    assert "1" in corpus["ICH-Q9R1"] and corpus["ICH-Q9R1"]["1"].title == "Introduction"


def test_clause_ids_unique_and_text_nonempty(corpus: dict[str, dict[str, Clause]]) -> None:
    for doc_id, clauses in corpus.items():
        assert len(clauses) == EXPECTED_COUNTS[doc_id]  # dict would hide duplicates
        assert all(c.text.strip() for c in clauses.values())
