import json
import inspect
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ml.training import (
    CONFIDENCE_CANDIDATES,
    TRAINING_SEEDS,
    TrainingConfig,
    TradingWindowMetrics,
    build_reproducibility_receipt,
    export_candidate_onnx,
    select_confidence_threshold,
    select_active_trading_candidate,
    set_training_seed,
    train_one_seed,
    weighted_cross_entropy,
)


def test_training_config_has_locked_optimizer_batch_epoch_and_early_stop_contract() -> None:
    config = TrainingConfig()
    assert TRAINING_SEEDS == (42, 43, 44)
    assert config.optimizer == "AdamW"
    assert config.learning_rate == 0.001
    assert config.weight_decay == 0.0001
    assert config.batch_size == 128
    assert config.max_epochs == 50
    assert config.early_stopping_patience == 8
    assert CONFIDENCE_CANDIDATES == (0.55, 0.60, 0.65, 0.70)


@pytest.mark.parametrize("seed", TRAINING_SEEDS)
def test_each_locked_seed_reproduces_python_numpy_and_torch_streams(seed: int) -> None:
    set_training_seed(seed)
    first = (np.random.rand(4), torch.rand(4))
    set_training_seed(seed)
    second = (np.random.rand(4), torch.rand(4))
    assert np.array_equal(first[0], second[0])
    assert torch.equal(first[1], second[1])


def test_weighted_cross_entropy_matches_pytorch_reference() -> None:
    logits = torch.tensor([[2.0, 0.0, -1.0], [0.0, 1.0, 2.0]], dtype=torch.float32)
    labels = torch.tensor([0, 2], dtype=torch.long)
    weights = torch.tensor([1.0, 2.0, 4.0], dtype=torch.float32)
    expected = torch.nn.functional.cross_entropy(logits, labels, weight=weights)
    assert torch.allclose(weighted_cross_entropy(logits, labels, weights), expected, atol=1e-7)


def test_confidence_selector_uses_worst_validation_window_not_accuracy_or_single_peak() -> None:
    by_threshold = {
        0.55: {"2025_q1": 0.10, "2025_q2": 0.10},
        0.60: {"2025_q1": 0.20, "2025_q2": 0.20},
        0.65: {"2025_q1": 0.90, "2025_q2": -0.10},
        0.70: {"2025_q1": 0.99, "2025_q2": -0.20},
    }
    assert select_confidence_threshold(by_threshold) == 0.60


def test_reproducibility_receipt_hashes_dataset_model_and_canonical_config(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.npz"
    np.savez(dataset, values=np.array([1, 2, 3]))
    model = torch.nn.Linear(2, 3)
    config = TrainingConfig()
    first = build_reproducibility_receipt(
        dataset, model, config, seed=42, selected_confidence=0.60
    )
    second = build_reproducibility_receipt(
        dataset, model, config, seed=42, selected_confidence=0.60
    )
    assert first == second
    assert set(first) >= {
        "dataset_sha256",
        "model_sha256",
        "config_sha256",
        "selected_seed",
        "selected_confidence",
        "environment",
    }
    assert first["selected_seed"] == 42
    assert first["allowed_seeds"] == [42, 43, 44]
    assert first["selected_confidence"] == 0.60
    assert all(len(first[field]) == 64 for field in ("dataset_sha256", "model_sha256", "config_sha256"))
    changed = TrainingConfig(learning_rate=0.002)
    assert (
        build_reproducibility_receipt(
            dataset, model, changed, seed=42, selected_confidence=0.60
        )["config_sha256"]
        != first["config_sha256"]
    )
    json.dumps(first, sort_keys=True)


def test_active_selector_enforces_window_and_aggregate_trading_gates() -> None:
    def window(profit: float, original: float = 100) -> TradingWindowMetrics:
        return TradingWindowMetrics(profit, original, 1.3, 20)

    scores = {
        0.55: {"w1": window(112), "w2": window(111)},
        0.60: {"w1": window(120), "w2": window(115)},
        0.65: {"w1": window(160), "w2": TradingWindowMetrics(80, 100, 1.3, 20)},
        0.70: {"w1": window(170), "w2": TradingWindowMetrics(120, 100, 1.1, 20)},
    }
    assert select_active_trading_candidate(scores) == 0.60


def test_zero_original_profit_is_not_treated_as_a_currency_ratio() -> None:
    metric = TradingWindowMetrics(0.01, 0.0, 1.3, 10)
    assert metric.relative_profit_change() == float("inf")
    assert metric.passes_window_gate()


def test_public_training_function_cannot_bypass_committed_data_gate() -> None:
    empty96 = np.empty((0, 96, 8), dtype=np.float32)
    empty48 = np.empty((0, 48, 8), dtype=np.float32)
    labels = np.empty((0,), dtype=np.int64)
    with pytest.raises(RuntimeError, match="training blocked by data gate"):
        train_one_seed(
            train_m5=empty96,
            train_m15=empty96,
            train_h1=empty48,
            train_labels=labels,
            validation_m5=empty96,
            validation_m15=empty96,
            validation_h1=empty48,
            validation_labels=labels,
            seed=42,
        )


def test_product_onnx_export_cannot_bypass_committed_data_gate(tmp_path: Path) -> None:
    from ml.temporal_cnn import TemporalCNN

    with pytest.raises(RuntimeError, match="training blocked by data gate"):
        export_candidate_onnx(TemporalCNN(), tmp_path / "blocked.onnx")
    assert not (tmp_path / "blocked.onnx").exists()


def test_public_training_and_export_cannot_substitute_another_gate() -> None:
    assert "gate_path" not in inspect.signature(train_one_seed).parameters
    assert "gate_path" not in inspect.signature(export_candidate_onnx).parameters
