import pytest

from eval.metrics import percentile, recall_at_budget, recall_at_k, reciprocal_rank


def test_recall_counts_gold_clauses_covered_by_top_k() -> None:
    ranked = [{"A:1"}, {"A:2", "A:3"}, {"B:9"}]
    gold = {"A:3", "B:9"}
    assert recall_at_k(ranked, gold, 1) == 0.0
    assert recall_at_k(ranked, gold, 2) == 0.5
    assert recall_at_k(ranked, gold, 3) == 1.0
    assert recall_at_k(ranked, gold, 10) == 1.0  # k beyond the list is fine


def test_reciprocal_rank_uses_first_hit_within_cutoff() -> None:
    ranked = [{"A:1"}, {"A:2"}, {"A:3"}]
    assert reciprocal_rank(ranked, {"A:2"}) == 0.5
    assert reciprocal_rank(ranked, {"A:9"}) == 0.0
    assert reciprocal_rank(ranked, {"A:3"}, max_rank=2) == 0.0


def test_empty_gold_is_rejected() -> None:
    with pytest.raises(ValueError):
        recall_at_k([{"A:1"}], set(), 5)


def test_recall_at_budget_takes_passages_in_rank_order_until_tokens_run_out() -> None:
    ranked = [{"A:1"}, {"A:2"}, {"A:3"}]
    tokens = [100, 300, 100]
    gold = {"A:1", "A:3"}
    assert recall_at_budget(ranked, tokens, gold, 99) == 0.0  # first passage doesn't fit
    assert recall_at_budget(ranked, tokens, gold, 100) == 0.5
    assert recall_at_budget(ranked, tokens, gold, 450) == 0.5  # stops at the 300-token one
    assert recall_at_budget(ranked, tokens, gold, 500) == 1.0


def test_percentile_interpolates() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    assert percentile([5.0], 95) == 5.0
