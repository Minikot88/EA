import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import numpy as np

import ml.data_gate as data_gate_module
from ml.data_gate import assert_training_allowed
from ml.hybrid_data_contract import HYBRID_SPLITS


ROOT = Path(__file__).resolve().parents[1]
GATE_TEMPLATE = ROOT / "ml" / "data" / "DATA_GATE.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def ready_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    monkeypatch.setattr(data_gate_module, "REPOSITORY_ROOT", tmp_path)
    lock = tmp_path / "ml" / "tools" / "dukascopy-node" / "package-lock.json"
    lock.parent.mkdir(parents=True)
    lock.write_text("locked", encoding="utf-8")

    monthly_hashes: dict[str, str] = {}
    monthly_audits: dict[str, dict] = {}
    current = datetime(2021, 1, 1, tzinfo=timezone.utc)
    for _ in range(60):
        month = current.strftime("%Y-%m")
        tick_file = tmp_path / "raw" / f"{month}.csv"
        tick_file.parent.mkdir(parents=True, exist_ok=True)
        tick_file.write_text(f"{month}\n", encoding="utf-8")
        digest = sha(tick_file)
        first = int(current.timestamp() * 1000) + 1
        monthly_hashes[month] = digest
        monthly_audits[month] = {
            "month": month,
            "status": "audited",
            "path": str(tick_file),
            "sha256": digest,
            "bytes": tick_file.stat().st_size,
            "quote_count": 2,
            "first_timestamp_ms": first,
            "last_timestamp_ms": first + 1,
            "minimum_bid": 100,
            "maximum_ask": 101,
            "maximum_spread": 1,
        }
        current = (
            current.replace(year=current.year + 1, month=1)
            if current.month == 12
            else current.replace(month=current.month + 1)
        )
    download_receipt = write_json(
        tmp_path / "receipts" / "download.json",
        {
            "schema_version": 1,
            "source": "Dukascopy",
            "source_symbol": "XAUUSD",
            "downloader": "dukascopy-node@1.50.0",
            "downloader_npm_integrity": "sha512-o2Co/asUD/TXFNhblJUYkRseHMt/uvFrnhzOKWezLuiFJqbl4Zn2oJGL4/W+PY1b2YsI11+9+TO40qNQBAj8/w==",
            "downloader_npm_shasum": "25ce461e28ae4ad37d74bcd2f2656e8266301062",
            "tool_lock_sha256": sha(lock),
            "utc_timestamp_unit": "milliseconds",
            "quote_fields": ["timestamp_ms", "bid", "ask"],
            "monthly_hashes": monthly_hashes,
            "monthly_audits": monthly_audits,
            "gap_receipt": {"missing_months": []},
            "failed_months": [],
            "files_complete": True,
        },
    )

    source_files: dict[str, dict[str, str]] = {}
    xs_contracts = {
        "xs_calibration_receipt": ("calibration", "2026-01-01/2026-02-28"),
        "xs_oos_receipt": ("locked_oos", "2026-03-01/2026-06-30"),
        "xs_holdout_receipt": ("final_holdout", "2026-07-01/2026-08-31"),
    }
    for name, (split, range_value) in xs_contracts.items():
        tick_file = tmp_path / "sources" / f"{split}.tkc"
        tick_file.parent.mkdir(parents=True, exist_ok=True)
        tick_file.write_text(split, encoding="utf-8")
        path = write_json(
            tmp_path / "sources" / f"{name}.json",
            {
                "schema_version": 1,
                "status": "audited",
                "broker_server": "XSFintech-REAL-2",
                "symbol": "XAUUSDc",
                "split": split,
                "range": range_value,
                "timezone": "UTC",
                "model": "every_tick_based_on_real_ticks",
                "gap_audit_status": "passed",
                "quote_count": 1,
                "tick_files": [{"path": str(tick_file), "sha256": sha(tick_file)}],
            },
        )
        source_files[name] = {"path": str(path), "sha256": sha(path)}
    source_files["dukascopy_download_manifest"] = {
        "path": str(download_receipt),
        "sha256": sha(download_receipt),
    }

    dataset_file = tmp_path / "dataset.npz"
    split_counts = {
        "train": 20_000,
        "validation": 100,
        "calibration": 100,
        "locked_oos": 100,
        "final_holdout": 100,
    }
    splits = np.concatenate(
        [np.full(count, name, dtype="U16") for name, count in split_counts.items()]
    )
    sources = np.concatenate(
        [
            np.full(count, HYBRID_SPLITS[name]["source"], dtype="U20")
            for name, count in split_counts.items()
        ]
    )
    labels = np.concatenate(
        [
            np.zeros(5_000, dtype=np.int64),
            np.ones(5_000, dtype=np.int64),
            np.full(10_000, 2, dtype=np.int64),
            np.full(400, 2, dtype=np.int64),
        ]
    )
    split_starts = {
        "train": datetime(2021, 2, 1, tzinfo=timezone.utc),
        "validation": datetime(2025, 1, 3, tzinfo=timezone.utc),
        "calibration": datetime(2026, 1, 3, tzinfo=timezone.utc),
        "locked_oos": datetime(2026, 3, 3, tzinfo=timezone.utc),
        "final_holdout": datetime(2026, 7, 3, tzinfo=timezone.utc),
    }
    timestamp_groups = [
        np.asarray(
            [
                (split_starts[name] + timedelta(seconds=index)).isoformat()
                for index in range(count)
            ],
            dtype="U32",
        )
        for name, count in split_counts.items()
    ]
    timestamps = np.concatenate(timestamp_groups)
    np.savez(
        dataset_file,
        labels=labels,
        timestamps=timestamps,
        splits=splits,
        sources=sources,
    )
    split_time_bounds = {
        name: {"first": group[0], "last": group[-1]}
        for (name, _count), group in zip(split_counts.items(), timestamp_groups)
    }
    dataset_receipt = write_json(
        tmp_path / "receipts" / "dataset.json",
        {
            "schema_version": 1,
            "data_contract": "hybrid_dukascopy_xs_v1",
            "training_source": "Dukascopy",
            "source_symbol": "XAUUSD",
            "broker_server": "XSFintech-REAL-2",
            "symbol": "XAUUSDc",
            "splits": HYBRID_SPLITS,
            "ranges": {name: row["range"] for name, row in HYBRID_SPLITS.items()},
            "purge_hours": 24,
            "bar_coverage": {"from": "2021-01-01", "to": "2025-12-31"},
            "real_tick_coverage": {"from": "2021-01-01", "to": "2025-12-31"},
            "source_coverage": {
                "Dukascopy": {"source_symbol": "XAUUSD", "from": "2021-01-01", "to": "2025-12-31"},
                "XSFintech-REAL-2": {
                    "target_symbol": "XAUUSDc",
                    "calibration": "2026-01-01/2026-02-28",
                    "locked_oos": "2026-03-01/2026-06-30",
                    "final_holdout": "2026-07-01/2026-08-31",
                },
            },
            "sample_count": 20_400,
            "split_counts": split_counts,
            "split_time_bounds": split_time_bounds,
            "label_counts": {"BUY": 5_000, "SELL": 5_000, "SKIP": 10_400},
            "training_label_counts": {"BUY": 5_000, "SELL": 5_000, "SKIP": 10_000},
            "dataset_path": str(dataset_file),
            "dataset_sha256": sha(dataset_file),
            "download_manifest_sha256": sha(download_receipt),
            "source_files": source_files,
        },
    )
    virtual_receipt = write_json(
        tmp_path / "receipts" / "virtual.json",
        {
            "schema_version": 1,
            "status": "passed",
            "broker_server": "XSFintech-REAL-2",
            "symbol": "XAUUSDc",
            "compile": {"errors": 0, "warnings": 0},
            "tested_behaviors": [
                "pending_fill",
                "dynamic_tp",
                "trailing",
                "money_close",
                "percent_close",
                "secure_profit",
                "sell_maxorder_asymmetry",
            ],
        },
    )
    onnx_receipt = write_json(
        tmp_path / "receipts" / "onnx.json",
        {
            "schema_version": 1,
            "status": "passed",
            "dataset_sha256": sha(dataset_file),
            "model_sha256": "a" * 64,
            "sample_count": 1_000,
            "max_abs_diff": 0.000001,
        },
    )

    gate = json.loads(GATE_TEMPLATE.read_text(encoding="utf-8"))
    gate["status"] = "ready"
    gate["training_allowed"] = True
    gate["observed"].update(
        {
            "dukascopy_download_status": "audited",
            "dukascopy_files_complete": True,
            "dukascopy_months_complete": 60,
            "dukascopy_coverage_from": "2021-01-01",
            "dukascopy_coverage_to": "2025-12-31",
            "buy_labels": 5_000,
            "sell_labels": 5_000,
            "skip_labels": 10_000,
            "virtual_original_mt5_parity_status": "passed",
            "python_onnx_mql_parity_status": "passed",
            "python_onnx_mql_samples": 1_000,
            "python_onnx_mql_max_abs_diff": 0.000001,
        }
    )
    gate["receipts"] = {
        "dukascopy_download_manifest": {"path": str(download_receipt), "sha256": sha(download_receipt)},
        "dataset_manifest": {"path": str(dataset_receipt), "sha256": sha(dataset_receipt)},
        "virtual_original_parity": {"path": str(virtual_receipt), "sha256": sha(virtual_receipt)},
        "onnx_parity": {"path": str(onnx_receipt), "sha256": sha(onnx_receipt)},
    }
    gate_path = write_json(tmp_path / "gate.json", gate)
    return gate_path, dataset_receipt


def test_fully_bound_hybrid_receipts_can_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate_path, _ = ready_bundle(tmp_path, monkeypatch)
    assert assert_training_allowed(gate_path)["training_allowed"] is True


def test_forged_ready_bundle_missing_calibration_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate_path, dataset_receipt = ready_bundle(tmp_path, monkeypatch)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_receipt.read_text(encoding="utf-8"))
    del dataset["split_counts"]["calibration"]
    write_json(dataset_receipt, dataset)
    gate["receipts"]["dataset_manifest"]["sha256"] = sha(dataset_receipt)
    write_json(gate_path, gate)
    with pytest.raises(RuntimeError, match="dataset receipt mismatch"):
        assert_training_allowed(gate_path)


def test_forged_xs_tick_hash_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate_path, dataset_receipt = ready_bundle(tmp_path, monkeypatch)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_receipt.read_text(encoding="utf-8"))
    pointer = dataset["source_files"]["xs_calibration_receipt"]
    xs_receipt_path = Path(pointer["path"])
    xs_receipt = json.loads(xs_receipt_path.read_text(encoding="utf-8"))
    xs_receipt["tick_files"][0]["sha256"] = "f" * 64
    write_json(xs_receipt_path, xs_receipt)
    pointer["sha256"] = sha(xs_receipt_path)
    write_json(dataset_receipt, dataset)
    gate["receipts"]["dataset_manifest"]["sha256"] = sha(dataset_receipt)
    write_json(gate_path, gate)
    with pytest.raises(RuntimeError, match="dataset receipt mismatch"):
        assert_training_allowed(gate_path)


def test_npz_source_substitution_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate_path, dataset_receipt = ready_bundle(tmp_path, monkeypatch)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_receipt.read_text(encoding="utf-8"))
    dataset_path = Path(dataset["dataset_path"])
    with np.load(dataset_path, allow_pickle=False) as arrays:
        labels = arrays["labels"]
        timestamps = arrays["timestamps"]
        splits = arrays["splits"]
        sources = arrays["sources"]
    sources[0] = "XSFintech-REAL-2"
    np.savez(
        dataset_path,
        labels=labels,
        timestamps=timestamps,
        splits=splits,
        sources=sources,
    )
    dataset["dataset_sha256"] = sha(dataset_path)
    write_json(dataset_receipt, dataset)
    gate["receipts"]["dataset_manifest"]["sha256"] = sha(dataset_receipt)
    write_json(gate_path, gate)
    with pytest.raises(RuntimeError, match="dataset receipt mismatch"):
        assert_training_allowed(gate_path)
