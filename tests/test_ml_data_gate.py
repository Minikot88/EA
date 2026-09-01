import json
import hashlib
from pathlib import Path

import pytest

from ml.data_gate import assert_training_allowed


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "ml" / "data" / "DATA_GATE.json"
PROBE = ROOT / "results" / "v0.2.0-dev.1" / "data-gate" / "PROBE.json"


def test_current_data_gate_blocks_training_honestly() -> None:
    data = json.loads(GATE.read_text(encoding="utf-8"))
    assert data["status"] == "blocked"
    assert data["training_allowed"] is False
    assert data["contract"] == "hybrid_dukascopy_xs_v1"
    assert data["sources"]["training_validation"]["provider"] == "Dukascopy"
    assert data["sources"]["training_validation"]["from"] == "2021-01-01"
    assert data["sources"]["execution_validation"]["broker_server"] == "XSFintech-REAL-2"
    assert data["observed"]["xs_server_history_from"] == "2023-09-06"
    assert data["observed"]["dukascopy_files_complete"] is False
    assert data["observed"]["virtual_original_mt5_parity_status"] == "not_run"
    assert data["required"]["python_onnx_mql_samples"] == 1000


def test_no_model_is_committed_while_gate_is_blocked() -> None:
    assert not list((ROOT / "models").glob("**/*.onnx")) if (ROOT / "models").exists() else True


def test_2021_real_tick_probe_is_recorded() -> None:
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    assert probe["status"] == "blocked"
    assert probe["model"] == "every_tick_based_on_real_ticks"
    assert probe["tick_file_202101_created"] is False
    assert probe["server_history_from"] == "2023-09-06"
    assert "no history data" in probe["tester_message"]


def test_training_entry_guard_fails_closed_while_history_is_missing() -> None:
    with pytest.raises(RuntimeError, match="training blocked by data gate"):
        assert_training_allowed(GATE)


def test_ready_flag_alone_cannot_bypass_required_parity(tmp_path: Path) -> None:
    forged = tmp_path / "gate.json"
    forged.write_text(
        json.dumps(
            {
                "status": "ready",
                "training_allowed": True,
                "reason": "flags edited without receipts",
                "observed": {
                    "virtual_original_mt5_parity_status": "not_run",
                    "python_onnx_mql_parity_status": "not_run",
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="training blocked by data gate"):
        assert_training_allowed(forged)


def test_ready_evidence_still_requires_hashed_receipts(tmp_path: Path) -> None:
    data = json.loads(GATE.read_text(encoding="utf-8"))
    data["status"] = "ready"
    data["training_allowed"] = True
    data["observed"].update(
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
    forged = tmp_path / "ready-without-receipts.json"
    forged.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeError, match="verified receipts are missing"):
        assert_training_allowed(forged)


def test_hashed_arbitrary_repository_files_cannot_pose_as_receipts(tmp_path: Path) -> None:
    data = json.loads(GATE.read_text(encoding="utf-8"))
    data["status"] = "ready"
    data["training_allowed"] = True
    data["observed"].update(
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
    arbitrary = ROOT / "README.md"
    digest = hashlib.sha256(arbitrary.read_bytes()).hexdigest()
    data["receipts"] = {
        name: {"path": "README.md", "sha256": digest}
        for name in (
            "dukascopy_download_manifest",
            "dataset_manifest",
            "virtual_original_parity",
            "onnx_parity",
        )
    }
    forged = tmp_path / "ready-with-arbitrary-receipts.json"
    forged.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid dukascopy_download_manifest receipt JSON"):
        assert_training_allowed(forged)
