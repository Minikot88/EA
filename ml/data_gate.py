"""Fail-closed guard used before any Kurama model training command."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping


DEFAULT_GATE = Path(__file__).resolve().parent / "data" / "DATA_GATE.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_receipts(
    gate: Mapping[str, object],
    required: Mapping[str, object],
    observed: Mapping[str, object],
) -> None:
    receipts = gate.get("receipts")
    if not isinstance(receipts, dict):
        raise RuntimeError("training blocked by data gate: verified receipts are missing")
    parsed: dict[str, Mapping[str, object]] = {}
    for name in ("dataset_manifest", "virtual_original_parity", "onnx_parity"):
        receipt = receipts.get(name)
        if not isinstance(receipt, dict):
            raise RuntimeError(f"training blocked by data gate: {name} receipt is missing")
        relative = receipt.get("path")
        expected_hash = receipt.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise RuntimeError(f"training blocked by data gate: invalid {name} receipt")
        path = (REPOSITORY_ROOT / relative).resolve()
        try:
            path.relative_to(REPOSITORY_ROOT)
        except ValueError as error:
            raise RuntimeError(
                f"training blocked by data gate: {name} escaped repository"
            ) from error
        if not path.is_file() or _sha256_file(path).lower() != expected_hash.lower():
            raise RuntimeError(
                f"training blocked by data gate: {name} receipt hash mismatch"
            )
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

    dataset = parsed["dataset_manifest"]
    expected_ranges = {
        "train": "2021-01-01/2024-12-31",
        "validation": "2025-01-01/2025-12-31",
        "locked_oos": "2026-01-01/2026-06-30",
        "final_holdout": "2026-07-01/2026-08-31",
    }
    training_counts = dataset.get("training_label_counts")
    dataset_bound = (
        dataset.get("broker_server") == gate.get("broker_server")
        and dataset.get("symbol") == gate.get("symbol")
        and dataset.get("bar_coverage")
        == {"from": required.get("bars_from"), "to": required.get("bars_to")}
        and dataset.get("real_tick_coverage")
        == {
            "from": required.get("real_ticks_from"),
            "to": required.get("real_ticks_to"),
        }
        and dataset.get("ranges") == expected_ranges
        and isinstance(training_counts, dict)
        and _number(training_counts.get("BUY"), 0) >= 5_000
        and _number(training_counts.get("SELL"), 0) >= 5_000
        and _number(training_counts.get("SKIP"), 0) >= 10_000
        and isinstance(dataset.get("dataset_sha256"), str)
        and len(str(dataset.get("dataset_sha256"))) == 64
    )
    if not dataset_bound:
        raise RuntimeError("training blocked by data gate: dataset receipt contract mismatch")

    virtual = parsed["virtual_original_parity"]
    required_behaviors = {
        "pending_fill",
        "dynamic_tp",
        "trailing",
        "money_close",
        "percent_close",
        "secure_profit",
        "sell_maxorder_asymmetry",
    }
    tested_behaviors = virtual.get("tested_behaviors")
    virtual_bound = (
        virtual.get("status") == "passed"
        and virtual.get("broker_server") == gate.get("broker_server")
        and virtual.get("symbol") == gate.get("symbol")
        and isinstance(tested_behaviors, list)
        and all(isinstance(item, str) for item in tested_behaviors)
        and required_behaviors.issubset(set(tested_behaviors))
        and virtual.get("compile") == {"errors": 0, "warnings": 0}
    )
    if not virtual_bound:
        raise RuntimeError(
            "training blocked by data gate: virtual Original parity receipt mismatch"
        )

    onnx = parsed["onnx_parity"]
    onnx_bound = (
        onnx.get("status") == "passed"
        and _number(onnx.get("sample_count"), 0)
        >= _number(required.get("python_onnx_mql_samples"), float("inf"))
        and _number(onnx.get("max_abs_diff"), float("inf"))
        <= _number(required.get("python_onnx_mql_max_abs_diff"), -1)
        and onnx.get("dataset_sha256") == dataset.get("dataset_sha256")
        and isinstance(onnx.get("model_sha256"), str)
        and len(str(onnx.get("model_sha256"))) == 64
        and _number(onnx.get("sample_count"), -1)
        == _number(observed.get("python_onnx_mql_samples"), -2)
        and _number(onnx.get("max_abs_diff"), float("inf"))
        == _number(observed.get("python_onnx_mql_max_abs_diff"), float("-inf"))
    )
    if not onnx_bound:
        raise RuntimeError("training blocked by data gate: ONNX parity receipt mismatch")


def read_data_gate(path: Path = DEFAULT_GATE) -> Mapping[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _number(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def assert_training_allowed(path: Path = DEFAULT_GATE) -> Mapping[str, object]:
    gate = read_data_gate(path)
    required = gate.get("required")
    observed = gate.get("observed")
    contract_ready = isinstance(required, dict) and (
        gate.get("broker_server") == "XSFintech-REAL-2"
        and gate.get("symbol") == "XAUUSDc"
        and required.get("bars_from") == "2021-01-01"
        and required.get("bars_to") == "2026-08-31"
        and required.get("real_ticks_from") == "2021-01-01"
        and required.get("real_ticks_to") == "2026-08-31"
        and required.get("minimum_buy_labels") == 5_000
        and required.get("minimum_sell_labels") == 5_000
        and required.get("minimum_skip_labels") == 10_000
        and required.get("python_onnx_mql_samples") == 1_000
        and required.get("python_onnx_mql_max_abs_diff") == 0.00001
        and required.get("virtual_original_mt5_parity") is True
    )
    evidence_ready = isinstance(observed, dict) and (
        observed.get("bar_coverage_from") == "2021-01-01"
        and observed.get("bar_coverage_to") == "2026-08-31"
        and observed.get("real_tick_coverage_from") == "2021-01-01"
        and observed.get("real_tick_coverage_to") == "2026-08-31"
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
    assert isinstance(required, dict)
    assert isinstance(observed, dict)
    _require_receipts(gate, required, observed)
    return gate
