"""Counterfactual BUY/SELL/SKIP policy and leakage-safe temporal gates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Mapping, Sequence, TypeVar


BUY = "BUY"
SELL = "SELL"
SKIP = "SKIP"
CLASSES = (BUY, SELL, SKIP)


@dataclass(frozen=True)
class CounterfactualOutcome:
    net_profit: float
    duration_hours: float
    max_dd_percent: float
    closed: bool = True

    def succeeds(self) -> bool:
        return (
            self.closed
            and self.net_profit > 0
            and self.duration_hours <= 24
            and self.max_dd_percent <= 20
        )


def label_counterfactual(
    buy: CounterfactualOutcome, sell: CounterfactualOutcome
) -> str:
    """Apply the locked 24-hour/20%-DD label policy without discretionary scoring."""

    buy_ok = buy.succeeds()
    sell_ok = sell.succeeds()
    if buy_ok and not sell_ok:
        return BUY
    if sell_ok and not buy_ok:
        return SELL
    if not buy_ok and not sell_ok:
        return SKIP

    faster_label, faster, slower = (
        (BUY, buy, sell)
        if buy.duration_hours <= sell.duration_hours
        else (SELL, sell, buy)
    )
    duration_gap = slower.duration_hours - faster.duration_hours
    if duration_gap > faster.duration_hours * 0.10:
        return faster_label

    dd_gap = abs(buy.max_dd_percent - sell.max_dd_percent)
    if dd_gap <= 1.0:
        return SKIP
    return BUY if buy.max_dd_percent < sell.max_dd_percent else SELL


Row = TypeVar("Row", bound=Mapping[str, object])


def purged_temporal_split(
    rows: Sequence[Row], *, split_at: datetime, purge_hours: int = 24
) -> tuple[list[Row], list[Row]]:
    """Split chronologically and remove labels whose 24-hour horizon crosses the boundary."""

    gap = timedelta(hours=purge_hours)
    train_cutoff = split_at - gap
    test_cutoff = split_at + gap
    # Exact edges are excluded because a 24-hour label can consume the tick at
    # its horizon; retaining that sample would touch the adjacent split.
    train = [row for row in rows if row["timestamp"] < train_cutoff]
    test = [row for row in rows if row["timestamp"] > test_cutoff]
    return train, test


def validate_class_gate(
    labels: Iterable[str],
    *,
    minimum_per_class: int | None = None,
    minimums: Mapping[str, int] | None = None,
) -> None:
    """Reject weak datasets using either a common or class-specific minimum."""

    if (minimum_per_class is None) == (minimums is None):
        raise ValueError("provide exactly one of minimum_per_class or minimums")
    required = (
        {label: int(minimum_per_class) for label in CLASSES}
        if minimums is None
        else {label: int(minimums[label]) for label in CLASSES}
    )
    counts = Counter(labels)
    missing = [label for label in CLASSES if counts[label] < required[label]]
    if missing:
        details = ", ".join(
            f"{label}={counts[label]}/{required[label]}" for label in missing
        )
        raise ValueError(f"class gate failed; observed/required {details}")
