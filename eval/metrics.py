"""Retrieval and ops metrics. A ranked result is a list of clause-key sets, one per passage."""

from collections.abc import Sequence


def recall_at_k(ranked: Sequence[set[str]], gold: set[str], k: int) -> float:
    """Fraction of gold clauses covered by the top-k passages."""
    if not gold:
        raise ValueError("recall is undefined for a question without gold clauses")
    covered = set().union(*ranked[:k]) if ranked else set()
    return len(gold & covered) / len(gold)


def recall_at_budget(
    ranked: Sequence[set[str]], tokens: Sequence[int], gold: set[str], budget: int
) -> float:
    """Recall over the top passages that fit in `budget` tokens, taken in rank order.

    recall@k rewards bigger chunks (more clauses per passage), so it can't compare
    chunking strategies; a fixed token budget compares them on equal context.
    """
    used, k = 0, 0
    for n in tokens:
        if used + n > budget:
            break
        used += n
        k += 1
    return recall_at_k(ranked, gold, k)


def reciprocal_rank(ranked: Sequence[set[str]], gold: set[str], max_rank: int = 10) -> float:
    """1/rank of the first passage covering any gold clause; 0 if none in the top max_rank."""
    for rank, clauses in enumerate(ranked[:max_rank], start=1):
        if clauses & gold:
            return 1.0 / rank
    return 0.0


def percentile(values: Sequence[float], p: float) -> float:
    """Linear-interpolated percentile, p in [0, 100]."""
    if not values:
        raise ValueError("percentile of an empty list")
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p / 100
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)
