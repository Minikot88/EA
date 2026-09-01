"""Counterfactual dataset generation without committing broker data."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from ml.counterfactual_labels import (
    BUY,
    SELL,
    SKIP,
    CounterfactualOutcome,
    label_counterfactual,
    validate_class_gate,
)
from ml.feature_extraction import OHLCVBar, extract_multitimeframe_features
from ml.hybrid_data_contract import HYBRID_SPLITS
from ml.virtual_original_basket import OriginalConfig, Tick, simulate_original_basket


CLASS_TO_ID = {BUY: 0, SELL: 1, SKIP: 2}
LOCKED_MINIMUMS = {BUY: 5_000, SELL: 5_000, SKIP: 10_000}
PURGE_HOURS = 24


@dataclass(frozen=True)
class DatasetSample:
    timestamp: datetime
    source: str
    m5: np.ndarray
    m15: np.ndarray
    h1: np.ndarray
    label: str
    buy_outcome: CounterfactualOutcome
    sell_outcome: CounterfactualOutcome


def _label_outcome(profit: float, duration: float, drawdown: float, closed: bool) -> CounterfactualOutcome:
    return CounterfactualOutcome(
        net_profit=profit,
        duration_hours=duration,
        max_dd_percent=drawdown,
        closed=closed,
    )


def build_counterfactual_sample(
    *,
    timestamp: datetime,
    m5: Sequence[OHLCVBar],
    m15: Sequence[OHLCVBar],
    h1: Sequence[OHLCVBar],
    ticks: Sequence[Tick],
    original_config: OriginalConfig,
    source: str = "Dukascopy",
) -> DatasetSample:
    """Build one sample from already closed bars and a forward real-tick slice."""

    if timestamp.tzinfo is None:
        raise ValueError("candidate timestamp must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)
    for timeframe, bars in (("m5", m5), ("m15", m15), ("h1", h1)):
        previous_close: datetime | None = None
        for bar in bars:
            if not bar.closed:
                continue
            if not isinstance(bar.timestamp, datetime):
                raise ValueError(f"{timeframe} bar timestamp must be a datetime")
            if bar.timestamp.tzinfo is None:
                raise ValueError(f"{timeframe} bar timestamp must be timezone-aware")
            if bar.timestamp.astimezone(timezone.utc) > timestamp:
                raise ValueError(f"{timeframe} contains a closed bar after the candidate")
            close_time = bar.timestamp.astimezone(timezone.utc)
            if previous_close is not None and close_time <= previous_close:
                raise ValueError(
                    f"{timeframe} closed-bar timestamps must be strictly increasing and unique"
                )
            previous_close = close_time
    if not ticks:
        raise ValueError("candidate requires a forward real-tick slice")
    candidate_epoch = timestamp.timestamp()
    if abs(ticks[0].timestamp - candidate_epoch) > 1e-6:
        raise ValueError("candidate timestamp must equal the first forward tick")

    features = extract_multitimeframe_features(m5=m5, m15=m15, h1=h1)
    buy = simulate_original_basket("BUY", ticks, original_config)
    sell = simulate_original_basket("SELL", ticks, original_config)
    required_horizon = original_config.max_duration_hours * 3600
    has_full_horizon = ticks[-1].timestamp - ticks[0].timestamp >= required_horizon
    if not has_full_horizon and (buy.closed_by is None or sell.closed_by is None):
        raise ValueError("real-tick slice ended before both baskets closed or 24 hours elapsed")
    buy_label = _label_outcome(
        buy.profit, buy.duration_hours, buy.max_dd_percent, buy.closed_by is not None
    )
    sell_label = _label_outcome(
        sell.profit, sell.duration_hours, sell.max_dd_percent, sell.closed_by is not None
    )
    return DatasetSample(
        timestamp=timestamp,
        source=source,
        m5=features["m5"],
        m15=features["m15"],
        h1=features["h1"],
        label=label_counterfactual(buy_label, sell_label),
        buy_outcome=buy_label,
        sell_outcome=sell_label,
    )


_START = datetime(2021, 1, 1, tzinfo=timezone.utc)
_VALIDATION = datetime(2025, 1, 1, tzinfo=timezone.utc)
_XS_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
_OOS = datetime(2026, 3, 1, tzinfo=timezone.utc)
_HOLDOUT = datetime(2026, 7, 1, tzinfo=timezone.utc)
_END = datetime(2026, 9, 1, tzinfo=timezone.utc)


def locked_split(timestamp: datetime, source: str | None = None) -> str | None:
    """Assign a source-bound Hybrid split or exclude its exact purge edges."""

    if timestamp.tzinfo is None:
        raise ValueError("split timestamp must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)
    gap = timedelta(hours=PURGE_HOURS)
    if source is None:
        source = "Dukascopy" if timestamp < _XS_START else "XSFintech-REAL-2"
    if source == "Dukascopy":
        if timestamp < _START or timestamp >= _XS_START:
            return None
        if any(
            boundary - gap <= timestamp <= boundary + gap
            for boundary in (_VALIDATION, _XS_START)
        ):
            return None
        return "train" if timestamp < _VALIDATION else "validation"
    if source == "XSFintech-REAL-2":
        if timestamp < _XS_START or timestamp >= _END:
            return None
        if any(
            boundary - gap <= timestamp <= boundary + gap
            for boundary in (_XS_START, _OOS, _HOLDOUT, _END)
        ):
            return None
        if timestamp < _OOS:
            return "calibration"
        if timestamp < _HOLDOUT:
            return "locked_oos"
        return "final_holdout"
    raise ValueError("sample source must be Dukascopy or XSFintech-REAL-2")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_dataset_and_manifest(
    samples: Sequence[DatasetSample],
    *,
    dataset_path: Path,
    manifest_path: Path,
    source_files: Mapping[str, Path],
    broker_server: str,
    symbol: str,
    bar_coverage_from: str,
    bar_coverage_to: str,
    real_tick_coverage_from: str,
    real_tick_coverage_to: str,
    original_config: OriginalConfig,
    download_manifest_path: Path,
    enforce_gate: bool = True,
) -> dict[str, object]:
    """Write ignored NPZ data and a commit-safe reproducibility manifest."""

    retained = [
        (sample, locked_split(sample.timestamp, sample.source)) for sample in samples
    ]
    retained = [(sample, split) for sample, split in retained if split is not None]
    if not retained:
        raise ValueError("no samples remain after locked ranges and purge gaps")
    train_labels = [sample.label for sample, split in retained if split == "train"]
    if enforce_gate:
        validate_class_gate(train_labels, minimums=LOCKED_MINIMUMS)

    dataset_path = Path(dataset_path)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        dataset_path,
        m5=np.stack([sample.m5 for sample, _ in retained]).astype(np.float32),
        m15=np.stack([sample.m15 for sample, _ in retained]).astype(np.float32),
        h1=np.stack([sample.h1 for sample, _ in retained]).astype(np.float32),
        labels=np.asarray([CLASS_TO_ID[sample.label] for sample, _ in retained], dtype=np.int64),
        timestamps=np.asarray(
            [sample.timestamp.isoformat() for sample, _ in retained], dtype="U32"
        ),
        splits=np.asarray([split for _, split in retained], dtype="U16"),
        sources=np.asarray([sample.source for sample, _ in retained], dtype="U20"),
    )
    split_counts = Counter(split for _, split in retained)
    split_time_bounds = {
        split: {
            "first": min(
                sample.timestamp for sample, sample_split in retained if sample_split == split
            ).isoformat(),
            "last": max(
                sample.timestamp for sample, sample_split in retained if sample_split == split
            ).isoformat(),
        }
        for split in HYBRID_SPLITS
        if split_counts[split] > 0
    }
    label_counts = Counter(sample.label for sample, _ in retained)
    training_label_counts = Counter(
        sample.label for sample, split in retained if split == "train"
    )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "data_contract": "hybrid_dukascopy_xs_v1",
        "training_source": "Dukascopy",
        "source_symbol": "XAUUSD",
        "broker_server": broker_server,
        "symbol": symbol,
        "bar_coverage": {
            "from": bar_coverage_from,
            "to": bar_coverage_to,
        },
        "real_tick_coverage": {
            "from": real_tick_coverage_from,
            "to": real_tick_coverage_to,
        },
        "source_coverage": {
            "Dukascopy": {
                "source_symbol": "XAUUSD",
                "from": "2021-01-01",
                "to": "2025-12-31",
            },
            "XSFintech-REAL-2": {
                "target_symbol": "XAUUSDc",
                "calibration": "2026-01-01/2026-02-28",
                "locked_oos": "2026-03-01/2026-06-30",
                "final_holdout": "2026-07-01/2026-08-31",
            },
        },
        "dataset_path": str(dataset_path),
        "dataset_sha256": _sha256_file(dataset_path),
        "download_manifest_sha256": _sha256_file(Path(download_manifest_path)),
        "source_sha256": {
            name: _sha256_file(Path(path)) for name, path in sorted(source_files.items())
        },
        "source_files": {
            name: {"path": str(path), "sha256": _sha256_file(Path(path))}
            for name, path in sorted(source_files.items())
        },
        "sample_count": len(retained),
        "split_counts": dict(sorted(split_counts.items())),
        "split_time_bounds": split_time_bounds,
        "label_counts": {label: label_counts[label] for label in (BUY, SELL, SKIP)},
        "training_label_counts": {
            label: training_label_counts[label] for label in (BUY, SELL, SKIP)
        },
        "class_gate": LOCKED_MINIMUMS,
        "purge_hours": PURGE_HOURS,
        "splits": HYBRID_SPLITS,
        "ranges": {
            "train": "2021-01-01/2024-12-31",
            "validation": "2025-01-01/2025-12-31",
            "calibration": "2026-01-01/2026-02-28",
            "locked_oos": "2026-03-01/2026-06-30",
            "final_holdout": "2026-07-01/2026-08-31",
        },
        "original_config": asdict(original_config),
    }
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest
