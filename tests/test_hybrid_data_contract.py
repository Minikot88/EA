from datetime import datetime, timezone

import pytest

from ml.hybrid_data_contract import (
    HYBRID_SPLITS,
    TickQuote,
    assert_hybrid_data_gate,
    build_download_manifest,
    validate_hybrid_manifest,
    validate_month_quotes,
)


def quote(timestamp_ms: int, bid: float = 100.0, ask: float = 100.1) -> TickQuote:
    return TickQuote(timestamp_ms=timestamp_ms, bid=bid, ask=ask)


def test_hybrid_split_plan_locks_sources_ranges_and_exact_purge() -> None:
    assert HYBRID_SPLITS == {
        "train": {"source": "Dukascopy", "range": "2021-01-01/2024-12-31"},
        "validation": {"source": "Dukascopy", "range": "2025-01-01/2025-12-31"},
        "calibration": {"source": "XSFintech-REAL-2", "range": "2026-01-01/2026-02-28"},
        "locked_oos": {"source": "XSFintech-REAL-2", "range": "2026-03-01/2026-06-30"},
        "final_holdout": {"source": "XSFintech-REAL-2", "range": "2026-07-01/2026-08-31"},
    }
    manifest = {
        "schema_version": 1,
        "symbol": "XAUUSDc",
        "purge_hours": 24,
        "splits": HYBRID_SPLITS,
        "records": [],
    }
    validate_hybrid_manifest(manifest)


def test_hybrid_manifest_rejects_xs_calibration_leakage_into_training() -> None:
    manifest = {
        "schema_version": 1,
        "symbol": "XAUUSDc",
        "purge_hours": 24,
        "splits": {
            **HYBRID_SPLITS,
            "train": {"source": "XSFintech-REAL-2", "range": "2026-01-01/2026-02-28"},
        },
        "records": [],
    }
    with pytest.raises(ValueError, match="train.*Dukascopy"):
        validate_hybrid_manifest(manifest)


def test_monthly_tick_quotes_require_utc_ms_order_uniqueness_and_non_crossed_prices() -> None:
    valid = [quote(1_704_067_200_000), quote(1_704_067_200_001, 100.1, 100.2)]
    receipt = validate_month_quotes("2024-01", valid)
    assert receipt["month"] == "2024-01"
    assert receipt["quote_count"] == 2
    assert receipt["first_timestamp_ms"] == valid[0].timestamp_ms
    assert receipt["last_timestamp_ms"] == valid[-1].timestamp_ms
    for invalid in (
        [quote(2), quote(1)],
        [quote(1), quote(1)],
        [quote(1, 100.2, 100.1)],
    ):
        with pytest.raises(ValueError):
            validate_month_quotes("2024-01", invalid)


def test_download_manifest_hashes_each_month_and_records_gap_receipt(tmp_path) -> None:
    january = tmp_path / "2024-01.csv"
    february = tmp_path / "2024-02.csv"
    january.write_text("1704067200000,100.0,100.1\n", encoding="utf-8")
    february.write_text("1706745600000,100.1,100.2\n", encoding="utf-8")
    manifest = build_download_manifest(
        source="Dukascopy",
        symbol="XAUUSDc",
        monthly_files={"2024-01": january, "2024-02": february},
    )
    assert manifest["source"] == "Dukascopy"
    assert set(manifest["monthly_hashes"]) == {"2024-01", "2024-02"}
    assert all(len(value) == 64 for value in manifest["monthly_hashes"].values())
    assert manifest["gap_receipt"]["missing_months"] == []
    assert manifest["utc_timestamp_unit"] == "milliseconds"
    assert manifest["quote_fields"] == ["timestamp_ms", "bid", "ask"]


def test_hybrid_gate_remains_blocked_until_files_are_complete_and_parity_passes() -> None:
    incomplete = {
        "status": "ready",
        "files_complete": False,
        "virtual_original_mt5_parity": "passed",
        "python_onnx_mql_parity": "passed",
    }
    with pytest.raises(RuntimeError, match="files_complete"):
        assert_hybrid_data_gate(incomplete)
    incomplete["files_complete"] = True
    incomplete["virtual_original_mt5_parity"] = "not_run"
    with pytest.raises(RuntimeError, match="parity"):
        assert_hybrid_data_gate(incomplete)
