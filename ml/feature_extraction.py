"""Leakage-safe feature extraction shared by dataset generation and parity tests."""

from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Hashable, Mapping, Sequence

import numpy as np


FEATURE_NAMES = (
    "close_log_return",
    "open_gap_atr",
    "high_atr",
    "low_atr",
    "body_atr",
    "range_atr",
    "tick_volume_zscore",
    "spread_atr",
)

WINDOWS = {"m5": 96, "m15": 96, "h1": 48}
VOLUME_ZSCORE_LOOKBACK = 20


@dataclass(frozen=True)
class OHLCVBar:
    """One broker bar.

    ``spread`` and ``atr`` must use the same price units.  Dataset adapters are
    responsible for converting MT5's integer spread points to price first.
    """

    timestamp: Hashable  # Bar close time in dataset/runtime adapters.
    open: float
    high: float
    low: float
    close: float
    tick_volume: float
    spread: float
    atr: float
    closed: bool = True


def _volume_zscore(history: Sequence[OHLCVBar], index: int) -> float:
    start = index - VOLUME_ZSCORE_LOOKBACK
    prior = np.asarray(
        [bar.tick_volume for bar in history[start:index]], dtype=np.float64
    )
    if start < 0 or prior.size != VOLUME_ZSCORE_LOOKBACK:
        raise ValueError("tick-volume z-score requires 20 prior closed bars")
    deviation = float(prior.std(ddof=0))
    if deviation == 0.0:
        return 0.0
    return (history[index].tick_volume - float(prior.mean())) / deviation


def _extract(history: Sequence[OHLCVBar], window: int) -> np.ndarray:
    closed = [bar for bar in history if bar.closed]
    for previous, current in zip(closed, closed[1:]):
        try:
            ordered = current.timestamp > previous.timestamp  # type: ignore[operator]
        except TypeError as error:
            raise ValueError("closed-bar timestamps must be comparable") from error
        if not ordered:
            raise ValueError("closed-bar timestamps must be strictly increasing and unique")
    required = window + VOLUME_ZSCORE_LOOKBACK
    if len(closed) < required:
        raise ValueError(
            f"need at least {required} closed bars for a {window}-bar tensor"
        )

    rows: list[list[float]] = []
    first = len(closed) - window
    for index in range(first, len(closed)):
        current = closed[index]
        previous = closed[index - 1]
        if current.atr <= 0 or current.close <= 0 or previous.close <= 0:
            raise ValueError("close and ATR must be positive for every selected bar")
        atr = current.atr
        rows.append(
            [
                log(current.close / previous.close),
                (current.open - previous.close) / atr,
                (current.high - current.open) / atr,
                (current.low - current.open) / atr,
                (current.close - current.open) / atr,
                (current.high - current.low) / atr,
                _volume_zscore(closed, index),
                current.spread / atr,
            ]
        )
    return np.asarray(rows, dtype=np.float64)


def extract_multitimeframe_features(
    *, m5: Sequence[OHLCVBar], m15: Sequence[OHLCVBar], h1: Sequence[OHLCVBar]
) -> Mapping[str, np.ndarray]:
    """Return fixed M5/M15/H1 tensors using closed bars only."""

    return {
        "m5": _extract(m5, WINDOWS["m5"]),
        "m15": _extract(m15, WINDOWS["m15"]),
        "h1": _extract(h1, WINDOWS["h1"]),
    }
