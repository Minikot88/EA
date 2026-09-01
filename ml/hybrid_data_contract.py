"""Locked multi-source data contract for the Kurama Hybrid reboot."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


HYBRID_SPLITS = {
    "train": {"source": "Dukascopy", "range": "2021-01-01/2024-12-31"},
    "validation": {"source": "Dukascopy", "range": "2025-01-01/2025-12-31"},
    "calibration": {
        "source": "XSFintech-REAL-2",
        "range": "2026-01-01/2026-02-28",
    },
    "locked_oos": {
        "source": "XSFintech-REAL-2",
        "range": "2026-03-01/2026-06-30",
    },
    "final_holdout": {
        "source": "XSFintech-REAL-2",
        "range": "2026-07-01/2026-08-31",
    },
}


@dataclass(frozen=True)
class TickQuote:
    timestamp_ms: int
    bid: float
    ask: float


def _month_bounds(month: str) -> tuple[int, int]:
    try:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError("month must use YYYY-MM") from error
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def validate_month_quotes(month: str, quotes: Sequence[TickQuote]) -> dict[str, object]:
    """Audit decoded UTC Bid/Ask quotes without filling or reordering them."""

    if not quotes:
        raise ValueError(f"{month} contains no quotes")
    start_ms, end_ms = _month_bounds(month)
    digest = hashlib.sha256()
    previous = -1
    spreads: list[float] = []
    for quote in quotes:
        if not start_ms <= quote.timestamp_ms < end_ms:
            raise ValueError(f"quote timestamp is outside {month}")
        if quote.timestamp_ms <= previous:
            raise ValueError("timestamps must be strictly increasing and unique")
        if (
            not math.isfinite(quote.bid)
            or not math.isfinite(quote.ask)
            or quote.bid <= 0
            or quote.ask <= 0
            or quote.ask < quote.bid
        ):
            raise ValueError("quotes must be positive, finite and non-crossed")
        digest.update(
            f"{quote.timestamp_ms},{quote.bid:.9f},{quote.ask:.9f}\n".encode("ascii")
        )
        spreads.append(quote.ask - quote.bid)
        previous = quote.timestamp_ms
    return {
        "month": month,
        "quote_count": len(quotes),
        "first_timestamp_ms": quotes[0].timestamp_ms,
        "last_timestamp_ms": quotes[-1].timestamp_ms,
        "minimum_spread": min(spreads),
        "maximum_spread": max(spreads),
        "canonical_quotes_sha256": digest.hexdigest(),
        "timezone": "UTC",
    }


def validate_hybrid_manifest(manifest: Mapping[str, object]) -> None:
    if manifest.get("schema_version") != 1:
        raise ValueError("hybrid manifest schema_version must be 1")
    if manifest.get("symbol") != "XAUUSDc":
        raise ValueError("hybrid target symbol must be XAUUSDc")
    if manifest.get("purge_hours") != 24:
        raise ValueError("hybrid purge must be exactly 24 hours")
    splits = manifest.get("splits")
    if not isinstance(splits, dict):
        raise ValueError("hybrid splits are missing")
    if splits.get("train") != HYBRID_SPLITS["train"]:
        raise ValueError("train source/range must remain Dukascopy 2021-2024")
    if splits != HYBRID_SPLITS:
        raise ValueError("hybrid split sources or ranges changed")
    if not isinstance(manifest.get("records"), list):
        raise ValueError("hybrid manifest records must be a list")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _month_sequence(first: str, last: str) -> list[str]:
    current = datetime.strptime(first, "%Y-%m")
    end = datetime.strptime(last, "%Y-%m")
    result: list[str] = []
    while current <= end:
        result.append(current.strftime("%Y-%m"))
        current = (
            current.replace(year=current.year + 1, month=1)
            if current.month == 12
            else current.replace(month=current.month + 1)
        )
    return result


def build_download_manifest(
    *,
    source: str,
    symbol: str,
    monthly_files: Mapping[str, Path],
    expected_from: str | None = None,
    expected_to: str | None = None,
) -> dict[str, object]:
    if source != "Dukascopy":
        raise ValueError("training download source must be Dukascopy")
    if not monthly_files:
        raise ValueError("monthly files are required")
    months = sorted(monthly_files)
    expected = _month_sequence(expected_from or months[0], expected_to or months[-1])
    missing = [month for month in expected if month not in monthly_files]
    hashes = {
        month: _sha256_file(Path(monthly_files[month])) for month in months
    }
    sizes = {month: Path(monthly_files[month]).stat().st_size for month in months}
    return {
        "schema_version": 1,
        "source": source,
        "source_symbol": "XAUUSD",
        "symbol": symbol,
        "monthly_hashes": hashes,
        "monthly_sizes": sizes,
        "gap_receipt": {"missing_months": missing},
        "utc_timestamp_unit": "milliseconds",
        "quote_fields": ["timestamp_ms", "bid", "ask"],
    }


def assert_hybrid_data_gate(gate: Mapping[str, object]) -> None:
    if gate.get("status") != "ready":
        raise RuntimeError("hybrid data gate status is not ready")
    if gate.get("files_complete") is not True:
        raise RuntimeError("hybrid data gate files_complete is false")
    if gate.get("virtual_original_mt5_parity") != "passed":
        raise RuntimeError("hybrid data gate virtual parity has not passed")
    if gate.get("python_onnx_mql_parity") != "passed":
        raise RuntimeError("hybrid data gate ONNX parity has not passed")
