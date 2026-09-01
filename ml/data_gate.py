"""Fail-closed Hybrid gate used before any Kurama model training/export."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import numpy as np

from ml.hybrid_data_contract import HYBRID_SPLITS


DEFAULT_GATE = Path(__file__).resolve().parent / "data" / "DATA_GATE.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def read_data_gate(path: Path = DEFAULT_GATE) -> Mapping[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("training blocked by data gate: root must be an object")
    return value


def _number(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_local_file(path_value: object, sha_value: object) -> bool:
    if not isinstance(path_value, (str, Path)) or not isinstance(sha_value, str):
        return False
    path = Path(path_value)
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    path = path.resolve()
    try:
        path.relative_to(REPOSITORY_ROOT)
    except ValueError:
        return False
    return path.is_file() and _sha256_file(path).lower() == sha_value.lower()


def _resolved_local_file(path_value: object) -> Path | None:
    if not isinstance(path_value, str):
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    path = path.resolve()
    try:
        path.relative_to(REPOSITORY_ROOT)
    except ValueError:
        return None
    return path if path.is_file() else None


def _read_json_file(path: Path) -> Mapping[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _utc_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return int(parsed.astimezone(timezone.utc).timestamp() * 1000)


def _month_ms_bounds(month: str) -> tuple[int, int]:
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _expected_months() -> list[str]:
    result: list[str] = []
    current = datetime(2021, 1, 1)
    end = datetime(2025, 12, 1)
    while current <= end:
        result.append(current.strftime("%Y-%m"))
        current = (
            current.replace(year=current.year + 1, month=1)
            if current.month == 12
            else current.replace(month=current.month + 1)
        )
    return result


def _load_receipts(gate: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    receipts = gate.get("receipts")
    if not isinstance(receipts, dict):
        raise RuntimeError("training blocked by data gate: verified receipts are missing")
    parsed: dict[str, Mapping[str, object]] = {}
    names = (
        "dukascopy_download_manifest",
        "dataset_manifest",
        "virtual_original_parity",
        "onnx_parity",
    )
    for name in names:
        pointer = receipts.get(name)
        if not isinstance(pointer, dict):
            raise RuntimeError(f"training blocked by data gate: {name} receipt is missing")
        relative = pointer.get("path")
        expected_hash = pointer.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise RuntimeError(f"training blocked by data gate: invalid {name} pointer")
        path = (REPOSITORY_ROOT / relative).resolve()
        try:
            path.relative_to(REPOSITORY_ROOT)
        except ValueError as error:
            raise RuntimeError(
                f"training blocked by data gate: {name} escaped repository"
            ) from error
        if not path.is_file() or _sha256_file(path).lower() != expected_hash.lower():
            raise RuntimeError(f"training blocked by data gate: {name} hash mismatch")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"training blocked by data gate: invalid {name} receipt JSON"
            ) from error
        if not isinstance(document, dict) or document.get("schema_version") != 1:
            raise RuntimeError(
                f"training blocked by data gate: invalid {name} receipt schema"
            )
        parsed[name] = document
    return parsed


def _validate_xs_receipt(pointer: Mapping[str, object], split: str) -> bool:
    path = _resolved_local_file(pointer.get("path"))
    if path is None or not _verified_local_file(path, pointer.get("sha256")):
        return False
    receipt = _read_json_file(path)
    if receipt is None:
        return False
    expected_ranges = {
        "calibration": "2026-01-01/2026-02-28",
        "locked_oos": "2026-03-01/2026-06-30",
        "final_holdout": "2026-07-01/2026-08-31",
    }
    tick_files = receipt.get("tick_files")
    files_ok = isinstance(tick_files, list) and bool(tick_files)
    if files_ok:
        files_ok = all(
            isinstance(item, dict)
            and _verified_local_file(item.get("path"), item.get("sha256"))
            for item in tick_files
        )
    return (
        receipt.get("schema_version") == 1
        and receipt.get("status") == "audited"
        and receipt.get("broker_server") == "XSFintech-REAL-2"
        and receipt.get("symbol") == "XAUUSDc"
        and receipt.get("split") == split
        and receipt.get("range") == expected_ranges[split]
        and receipt.get("timezone") == "UTC"
        and receipt.get("model") == "every_tick_based_on_real_ticks"
        and receipt.get("gap_audit_status") == "passed"
        and _number(receipt.get("quote_count"), 0) > 0
        and files_ok
    )


def _validate_dataset_npz(dataset: Mapping[str, object]) -> bool:
    path = _resolved_local_file(dataset.get("dataset_path"))
    if path is None or not _verified_local_file(path, dataset.get("dataset_sha256")):
        return False
    try:
        with np.load(path, allow_pickle=False) as arrays:
            required = {"labels", "timestamps", "splits", "sources"}
            if not required.issubset(arrays.files):
                return False
            labels = arrays["labels"]
            timestamps = arrays["timestamps"]
            splits = arrays["splits"]
            sources = arrays["sources"]
    except (OSError, ValueError, KeyError):
        return False
    sample_count = int(_number(dataset.get("sample_count"), -1))
    if any(len(array) != sample_count for array in (labels, timestamps, splits, sources)):
        return False
    expected_class_counts = {
        "BUY": int(np.sum(labels == 0)),
        "SELL": int(np.sum(labels == 1)),
        "SKIP": int(np.sum(labels == 2)),
    }
    if expected_class_counts != dataset.get("label_counts"):
        return False
    split_counts = {
        name: int(np.sum(splits == name)) for name in HYBRID_SPLITS
    }
    if split_counts != dataset.get("split_counts"):
        return False
    training_mask = splits == "train"
    expected_training_counts = {
        "BUY": int(np.sum(labels[training_mask] == 0)),
        "SELL": int(np.sum(labels[training_mask] == 1)),
        "SKIP": int(np.sum(labels[training_mask] == 2)),
    }
    if expected_training_counts != dataset.get("training_label_counts"):
        return False
    for split, contract in HYBRID_SPLITS.items():
        mask = splits == split
        expected_source = contract["source"]
        if not np.all(sources[mask] == expected_source):
            return False
        try:
            split_times = np.asarray(
                [_utc_ms(str(value)) for value in timestamps[mask]], dtype=np.int64
            )
        except (TypeError, ValueError):
            return False
        if split_times.size == 0 or np.any(split_times[1:] <= split_times[:-1]):
            return False
        bounds = dataset.get("split_time_bounds")
        if not isinstance(bounds, dict) or not isinstance(bounds.get(split), dict):
            return False
        if (
            split_times[0] != _utc_ms(str(bounds[split].get("first")))
            or split_times[-1] != _utc_ms(str(bounds[split].get("last")))
        ):
            return False
    return True


def _validate_receipt_contracts(
    gate: Mapping[str, object], receipts: Mapping[str, Mapping[str, object]]
) -> None:
    download = receipts["dukascopy_download_manifest"]
    monthly_hashes = download.get("monthly_hashes")
    monthly_audits = download.get("monthly_audits")
    expected_months = _expected_months()
    audit_rows_ok = isinstance(monthly_audits, dict)
    if audit_rows_ok and isinstance(monthly_hashes, dict):
        for month in expected_months:
            audit = monthly_audits.get(month)
            if not isinstance(audit, dict):
                audit_rows_ok = False
                break
            try:
                start_ms, end_ms = _month_ms_bounds(month)
            except ValueError:
                audit_rows_ok = False
                break
            audit_rows_ok = (
                audit.get("month") == month
                and audit.get("status") == "audited"
                and audit.get("sha256") == monthly_hashes.get(month)
                and _number(audit.get("bytes"), 0) > 0
                and _number(audit.get("quote_count"), 0) > 0
                and start_ms <= _number(audit.get("first_timestamp_ms"), -1) < end_ms
                and start_ms < _number(audit.get("last_timestamp_ms"), -1) < end_ms
                and _number(audit.get("last_timestamp_ms"), -1)
                >= _number(audit.get("first_timestamp_ms"), 0)
                and _number(audit.get("minimum_bid"), 0) > 0
                and _number(audit.get("maximum_ask"), 0)
                >= _number(audit.get("minimum_bid"), float("inf"))
                and _number(audit.get("maximum_spread"), -1) >= 0
                and _verified_local_file(audit.get("path"), audit.get("sha256"))
            )
            if not audit_rows_ok:
                break
    download_ok = (
        download.get("source") == "Dukascopy"
        and download.get("source_symbol") == "XAUUSD"
        and download.get("utc_timestamp_unit") == "milliseconds"
        and download.get("quote_fields") == ["timestamp_ms", "bid", "ask"]
        and download.get("downloader") == "dukascopy-node@1.50.0"
        and download.get("downloader_npm_integrity")
        == "sha512-o2Co/asUD/TXFNhblJUYkRseHMt/uvFrnhzOKWezLuiFJqbl4Zn2oJGL4/W+PY1b2YsI11+9+TO40qNQBAj8/w=="
        and download.get("downloader_npm_shasum")
        == "25ce461e28ae4ad37d74bcd2f2656e8266301062"
        and download.get("tool_lock_sha256")
        == _sha256_file(REPOSITORY_ROOT / "ml/tools/dukascopy-node/package-lock.json")
        and isinstance(monthly_hashes, dict)
        and sorted(monthly_hashes) == expected_months
        and all(isinstance(value, str) and len(value) == 64 for value in monthly_hashes.values())
        and download.get("files_complete") is True
        and download.get("gap_receipt") == {"missing_months": []}
        and audit_rows_ok
    )
    if not download_ok:
        raise RuntimeError("training blocked by data gate: download receipt mismatch")

    dataset = receipts["dataset_manifest"]
    training_counts = dataset.get("training_label_counts")
    label_counts = dataset.get("label_counts")
    split_counts = dataset.get("split_counts")
    split_bounds = dataset.get("split_time_bounds")
    expected_ranges = {
        "train": "2021-01-01/2024-12-31",
        "validation": "2025-01-01/2025-12-31",
        "calibration": "2026-01-01/2026-02-28",
        "locked_oos": "2026-03-01/2026-06-30",
        "final_holdout": "2026-07-01/2026-08-31",
    }
    split_counts_ok = (
        isinstance(split_counts, dict)
        and set(split_counts) == set(HYBRID_SPLITS)
        and all(_number(split_counts.get(name), 0) > 0 for name in HYBRID_SPLITS)
        and sum(int(_number(split_counts.get(name), 0)) for name in HYBRID_SPLITS)
        == int(_number(dataset.get("sample_count"), -1))
    )
    label_counts_ok = (
        isinstance(label_counts, dict)
        and set(label_counts) == {"BUY", "SELL", "SKIP"}
        and sum(int(_number(label_counts.get(name), 0)) for name in label_counts)
        == int(_number(dataset.get("sample_count"), -1))
        and isinstance(training_counts, dict)
        and sum(int(_number(training_counts.get(name), 0)) for name in training_counts)
        == int(_number(split_counts.get("train"), -1))
    )
    bound_limits = {
        "train": ("2021-01-01T00:00:00+00:00", "2024-12-31T00:00:00+00:00"),
        "validation": ("2025-01-02T00:00:00.001+00:00", "2025-12-31T00:00:00+00:00"),
        "calibration": ("2026-01-02T00:00:00.001+00:00", "2026-02-28T00:00:00+00:00"),
        "locked_oos": ("2026-03-02T00:00:00.001+00:00", "2026-06-30T00:00:00+00:00"),
        "final_holdout": ("2026-07-02T00:00:00.001+00:00", "2026-08-31T00:00:00+00:00"),
    }
    split_bounds_ok = isinstance(split_bounds, dict) and set(split_bounds) == set(
        HYBRID_SPLITS
    )
    if split_bounds_ok:
        try:
            for name, (minimum, maximum) in bound_limits.items():
                row = split_bounds[name]
                if not isinstance(row, dict):
                    split_bounds_ok = False
                    break
                first = _utc_ms(str(row.get("first")))
                last = _utc_ms(str(row.get("last")))
                if not (_utc_ms(minimum) <= first <= last < _utc_ms(maximum)):
                    split_bounds_ok = False
                    break
        except (ValueError, TypeError):
            split_bounds_ok = False
    source_files = dataset.get("source_files")
    required_sources = {
        "dukascopy_download_manifest",
        "xs_calibration_receipt",
        "xs_oos_receipt",
        "xs_holdout_receipt",
    }
    source_files_ok = isinstance(source_files, dict) and set(source_files) == required_sources
    if source_files_ok:
        source_files_ok = all(
            isinstance(pointer, dict)
            and _verified_local_file(pointer.get("path"), pointer.get("sha256"))
            for pointer in source_files.values()
        )
    if source_files_ok:
        source_files_ok = (
            source_files["dukascopy_download_manifest"]
            == gate["receipts"]["dukascopy_download_manifest"]  # type: ignore[index]
            and _validate_xs_receipt(
                source_files["xs_calibration_receipt"], "calibration"
            )
            and _validate_xs_receipt(source_files["xs_oos_receipt"], "locked_oos")
            and _validate_xs_receipt(
                source_files["xs_holdout_receipt"], "final_holdout"
            )
        )
    expected_source_coverage = {
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
    }
    dataset_ok = (
        dataset.get("data_contract") == "hybrid_dukascopy_xs_v1"
        and dataset.get("training_source") == "Dukascopy"
        and dataset.get("source_symbol") == "XAUUSD"
        and dataset.get("broker_server") == "XSFintech-REAL-2"
        and dataset.get("symbol") == "XAUUSDc"
        and dataset.get("splits") == HYBRID_SPLITS
        and dataset.get("purge_hours") == 24
        and dataset.get("ranges") == expected_ranges
        and dataset.get("bar_coverage")
        == {"from": "2021-01-01", "to": "2025-12-31"}
        and dataset.get("real_tick_coverage")
        == {"from": "2021-01-01", "to": "2025-12-31"}
        and dataset.get("source_coverage") == expected_source_coverage
        and split_counts_ok
        and label_counts_ok
        and split_bounds_ok
        and source_files_ok
        and isinstance(training_counts, dict)
        and _number(training_counts.get("BUY"), 0) >= 5_000
        and _number(training_counts.get("SELL"), 0) >= 5_000
        and _number(training_counts.get("SKIP"), 0) >= 10_000
        and isinstance(dataset.get("dataset_sha256"), str)
        and len(str(dataset.get("dataset_sha256"))) == 64
        and _validate_dataset_npz(dataset)
        and dataset.get("download_manifest_sha256")
        == _sha256_file(
            (
                REPOSITORY_ROOT
                / str(gate["receipts"]["dukascopy_download_manifest"]["path"])  # type: ignore[index]
            ).resolve()
        )
    )
    if not dataset_ok:
        raise RuntimeError("training blocked by data gate: dataset receipt mismatch")

    virtual = receipts["virtual_original_parity"]
    required_behaviors = {
        "pending_fill",
        "dynamic_tp",
        "trailing",
        "money_close",
        "percent_close",
        "secure_profit",
        "sell_maxorder_asymmetry",
    }
    tested = virtual.get("tested_behaviors")
    virtual_ok = (
        virtual.get("status") == "passed"
        and virtual.get("broker_server") == "XSFintech-REAL-2"
        and virtual.get("symbol") == "XAUUSDc"
        and virtual.get("compile") == {"errors": 0, "warnings": 0}
        and isinstance(tested, list)
        and all(isinstance(item, str) for item in tested)
        and required_behaviors.issubset(set(tested))
    )
    if not virtual_ok:
        raise RuntimeError("training blocked by data gate: virtual parity receipt mismatch")

    onnx = receipts["onnx_parity"]
    observed = gate.get("observed")
    onnx_ok = (
        isinstance(observed, dict)
        and onnx.get("status") == "passed"
        and onnx.get("dataset_sha256") == dataset.get("dataset_sha256")
        and isinstance(onnx.get("model_sha256"), str)
        and len(str(onnx.get("model_sha256"))) == 64
        and _number(onnx.get("sample_count"), 0) >= 1_000
        and _number(onnx.get("max_abs_diff"), float("inf")) <= 0.00001
        and _number(onnx.get("sample_count"), -1)
        == _number(observed.get("python_onnx_mql_samples"), -2)
        and _number(onnx.get("max_abs_diff"), float("inf"))
        == _number(observed.get("python_onnx_mql_max_abs_diff"), float("-inf"))
    )
    if not onnx_ok:
        raise RuntimeError("training blocked by data gate: ONNX parity receipt mismatch")


def assert_training_allowed(path: Path = DEFAULT_GATE) -> Mapping[str, object]:
    gate = read_data_gate(path)
    sources = gate.get("sources")
    required = gate.get("required")
    observed = gate.get("observed")
    expected_sources = {
        "training_validation": {
            "provider": "Dukascopy",
            "source_symbol": "XAUUSD",
            "from": "2021-01-01",
            "to": "2025-12-31",
            "timezone": "UTC",
            "quote_fields": ["timestamp_ms", "bid", "ask"],
        },
        "execution_validation": {
            "broker_server": "XSFintech-REAL-2",
            "target_symbol": "XAUUSDc",
            "from": "2026-01-01",
            "to": "2026-08-31",
        },
    }
    expected_required = {
        "purge_hours": 24,
        "dukascopy_months": 60,
        "minimum_buy_labels": 5_000,
        "minimum_sell_labels": 5_000,
        "minimum_skip_labels": 10_000,
        "virtual_original_mt5_parity": True,
        "python_onnx_mql_samples": 1_000,
        "python_onnx_mql_max_abs_diff": 0.00001,
    }
    contract_ready = (
        gate.get("schema_version") == 2
        and gate.get("contract") == "hybrid_dukascopy_xs_v1"
        and sources == expected_sources
        and gate.get("splits") == HYBRID_SPLITS
        and required == expected_required
    )
    evidence_ready = isinstance(observed, dict) and (
        observed.get("dukascopy_download_status") == "audited"
        and observed.get("dukascopy_files_complete") is True
        and _number(observed.get("dukascopy_months_complete"), 0) == 60
        and observed.get("dukascopy_coverage_from") == "2021-01-01"
        and observed.get("dukascopy_coverage_to") == "2025-12-31"
        and observed.get("xs_real_tick_coverage_from") == "2026-01-01"
        and observed.get("xs_real_tick_coverage_to") == "2026-09-01"
        and _number(observed.get("buy_labels"), 0) >= 5_000
        and _number(observed.get("sell_labels"), 0) >= 5_000
        and _number(observed.get("skip_labels"), 0) >= 10_000
        and observed.get("virtual_original_mt5_parity_status") == "passed"
        and observed.get("python_onnx_mql_parity_status") == "passed"
        and _number(observed.get("python_onnx_mql_samples"), 0) >= 1_000
        and _number(observed.get("python_onnx_mql_max_abs_diff"), float("inf"))
        <= 0.00001
    )
    if (
        gate.get("status") != "ready"
        or gate.get("training_allowed") is not True
        or not contract_ready
        or not evidence_ready
    ):
        raise RuntimeError(f"training blocked by data gate: {gate.get('reason', 'not ready')}")
    receipts = _load_receipts(gate)
    _validate_receipt_contracts(gate, receipts)
    return gate
