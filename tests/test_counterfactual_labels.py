from datetime import datetime, timedelta, timezone

import pytest

from ml.counterfactual_labels import (
    BUY,
    SELL,
    SKIP,
    CounterfactualOutcome,
    label_counterfactual,
    purged_temporal_split,
    validate_class_gate,
)


def outcome(profit: float, duration_hours: float, max_dd_percent: float) -> CounterfactualOutcome:
    return CounterfactualOutcome(profit, duration_hours, max_dd_percent)


@pytest.mark.parametrize(
    ("buy", "sell", "expected"),
    [
        (outcome(10, 12, 5), outcome(-1, 1, 1), BUY),
        (outcome(-1, 1, 1), outcome(10, 12, 5), SELL),
        (outcome(10, 25, 5), outcome(10, 12, 5), SELL),
        (outcome(10, 12, 21), outcome(10, 12, 5), SELL),
        (outcome(-1, 1, 1), outcome(0, 1, 1), SKIP),
        (outcome(10, 10, 5), outcome(10, 14, 5), BUY),
        (outcome(10, 10, 8), outcome(10, 10.5, 4), SELL),
        (outcome(10, 10, 5), outcome(10, 10.5, 5.9), SKIP),
    ],
)
def test_counterfactual_label_policy(buy: CounterfactualOutcome, sell: CounterfactualOutcome, expected: str) -> None:
    assert label_counterfactual(buy, sell) == expected


def test_purged_temporal_split_removes_windows_crossing_the_boundary() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"timestamp": start + timedelta(hours=offset), "label": BUY}
        for offset in (0, 12, 24, 36, 48, 60, 61)
    ]
    train, test = purged_temporal_split(rows, split_at=start + timedelta(hours=36), purge_hours=24)
    assert [row["timestamp"] for row in train] == [start]
    assert [row["timestamp"] for row in test] == [start + timedelta(hours=61)]


def test_class_gate_requires_every_decision_class() -> None:
    validate_class_gate([BUY, SELL, SKIP], minimum_per_class=1)
    with pytest.raises(ValueError, match="SELL"):
        validate_class_gate([BUY, SKIP, SKIP], minimum_per_class=1)


def test_locked_class_gate_requires_twice_as_many_skip_labels() -> None:
    minimums = {BUY: 5_000, SELL: 5_000, SKIP: 10_000}
    with pytest.raises(ValueError, match="SKIP=9999/10000"):
        validate_class_gate(
            [BUY] * 5_000 + [SELL] * 5_000 + [SKIP] * 9_999,
            minimums=minimums,
        )


def test_open_basket_is_not_a_success_even_when_marked_to_market_positive() -> None:
    open_profit = CounterfactualOutcome(10, 2, 1, closed=False)
    failed = CounterfactualOutcome(-1, 2, 1)
    assert label_counterfactual(open_profit, failed) == SKIP
