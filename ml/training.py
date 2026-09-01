"""Locked and reproducible Kurama Temporal CNN training contract."""

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import platform
import random
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import torch
from torch import Tensor
from torch.nn import functional as functional
from torch.utils.data import DataLoader, TensorDataset

from ml.temporal_cnn import TemporalCNN, export_temporal_cnn_onnx
from ml.data_gate import DEFAULT_GATE, assert_training_allowed


TRAINING_SEEDS = (42, 43, 44)
CONFIDENCE_CANDIDATES = (0.55, 0.60, 0.65, 0.70)


@dataclass(frozen=True)
class TrainingConfig:
    optimizer: str = "AdamW"
    learning_rate: float = 0.001
    weight_decay: float = 0.0001
    batch_size: int = 128
    max_epochs: int = 50
    early_stopping_patience: int = 8
    dropout: float = 0.20
    minimum_improvement: float = 1e-7


@dataclass(frozen=True)
class TrainingResult:
    model: TemporalCNN
    seed: int
    epochs_completed: int
    best_validation_loss: float
    train_losses: tuple[float, ...]
    validation_losses: tuple[float, ...]


@dataclass(frozen=True)
class TradingWindowMetrics:
    profit: float
    original_profit: float
    profit_factor: float
    max_drawdown_percent: float
    stopout: bool = False
    timeout: bool = False

    def relative_profit_change(self) -> float:
        if self.original_profit == 0:
            if self.profit > 0:
                return float("inf")
            if self.profit < 0:
                return float("-inf")
            return 0.0
        return (self.profit - self.original_profit) / abs(self.original_profit)

    def passes_window_gate(self) -> bool:
        return (
            self.profit > 0
            and self.profit_factor >= 1.20
            and self.max_drawdown_percent <= 30.0
            and not self.stopout
            and not self.timeout
            and self.relative_profit_change() >= -0.10
        )


def set_training_seed(seed: int) -> None:
    """Seed every random stream used by the CPU-only training pipeline."""

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def weighted_cross_entropy(logits: Tensor, labels: Tensor, weights: Tensor) -> Tensor:
    return functional.cross_entropy(logits, labels, weight=weights)


def _weighted_loss_components(
    logits: Tensor, labels: Tensor, weights: Tensor
) -> tuple[float, float]:
    numerator = functional.cross_entropy(
        logits, labels, weight=weights, reduction="sum"
    )
    denominator = weights[labels].sum()
    return float(numerator.detach()), float(denominator.detach())


def _as_float_tensor(values: np.ndarray | Tensor) -> Tensor:
    return torch.as_tensor(values, dtype=torch.float32, device="cpu")


def _as_label_tensor(values: np.ndarray | Tensor) -> Tensor:
    return torch.as_tensor(values, dtype=torch.long, device="cpu")


def _validate_arrays(m5: Tensor, m15: Tensor, h1: Tensor, labels: Tensor) -> None:
    expected = ((96, 8), (96, 8), (48, 8))
    for name, tensor, shape in zip(("m5", "m15", "h1"), (m5, m15, h1), expected):
        if tensor.ndim != 3 or tuple(tensor.shape[1:]) != shape:
            raise ValueError(f"{name} must have shape [samples,{shape[0]},{shape[1]}]")
    sample_count = labels.shape[0]
    if labels.ndim != 1 or any(tensor.shape[0] != sample_count for tensor in (m5, m15, h1)):
        raise ValueError("all inputs and labels must contain the same sample count")
    if sample_count == 0 or labels.min().item() < 0 or labels.max().item() > 2:
        raise ValueError("labels must be a non-empty vector containing class ids 0..2")


def _balanced_class_weights(labels: Tensor) -> Tensor:
    counts = torch.bincount(labels, minlength=3).to(dtype=torch.float32)
    if torch.any(counts == 0):
        raise ValueError("training split must contain BUY, SELL and SKIP")
    return labels.numel() / (3.0 * counts)


def train_one_seed(
    *,
    train_m5: np.ndarray | Tensor,
    train_m15: np.ndarray | Tensor,
    train_h1: np.ndarray | Tensor,
    train_labels: np.ndarray | Tensor,
    validation_m5: np.ndarray | Tensor,
    validation_m15: np.ndarray | Tensor,
    validation_h1: np.ndarray | Tensor,
    validation_labels: np.ndarray | Tensor,
    seed: int,
    config: TrainingConfig | None = None,
) -> TrainingResult:
    """Train one locked seed and restore the lowest validation-loss checkpoint."""

    assert_training_allowed(DEFAULT_GATE)
    if seed not in TRAINING_SEEDS:
        raise ValueError(f"seed must be one of {TRAINING_SEEDS}")
    config = config or TrainingConfig()
    set_training_seed(seed)

    train_tensors = (
        _as_float_tensor(train_m5),
        _as_float_tensor(train_m15),
        _as_float_tensor(train_h1),
        _as_label_tensor(train_labels),
    )
    validation_tensors = (
        _as_float_tensor(validation_m5),
        _as_float_tensor(validation_m15),
        _as_float_tensor(validation_h1),
        _as_label_tensor(validation_labels),
    )
    _validate_arrays(*train_tensors)
    _validate_arrays(*validation_tensors)
    class_counts = torch.bincount(train_tensors[-1], minlength=3)
    required_counts = torch.tensor((5_000, 5_000, 10_000), dtype=torch.long)
    if torch.any(class_counts < required_counts):
        raise ValueError(
            "locked training class gate failed: "
            f"BUY={class_counts[0].item()}/5000, "
            f"SELL={class_counts[1].item()}/5000, "
            f"SKIP={class_counts[2].item()}/10000"
        )

    generator = torch.Generator(device="cpu").manual_seed(seed)
    loader = DataLoader(
        TensorDataset(*train_tensors),
        batch_size=config.batch_size,
        shuffle=True,
        generator=generator,
        num_workers=0,
    )
    validation_loader = DataLoader(
        TensorDataset(*validation_tensors),
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=0,
    )
    model = TemporalCNN().cpu()
    if config.optimizer != "AdamW":
        raise ValueError("the locked optimizer is AdamW")
    if config.dropout != 0.20:
        raise ValueError("the locked model dropout is 0.20")
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    class_weights = _balanced_class_weights(train_tensors[-1])
    train_history: list[float] = []
    validation_history: list[float] = []
    best_loss = float("inf")
    best_state = deepcopy(model.state_dict())
    stale_epochs = 0

    for _epoch in range(config.max_epochs):
        model.train()
        total_loss_numerator = 0.0
        total_loss_denominator = 0.0
        for batch_m5, batch_m15, batch_h1, batch_labels in loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model.forward_logits(batch_m5, batch_m15, batch_h1)
            loss = weighted_cross_entropy(logits, batch_labels, class_weights)
            loss.backward()
            optimizer.step()
            numerator, denominator = _weighted_loss_components(
                logits, batch_labels, class_weights
            )
            total_loss_numerator += numerator
            total_loss_denominator += denominator
        train_history.append(total_loss_numerator / total_loss_denominator)

        model.eval()
        validation_numerator = 0.0
        validation_denominator = 0.0
        with torch.no_grad():
            for batch_m5, batch_m15, batch_h1, batch_labels in validation_loader:
                logits = model.forward_logits(batch_m5, batch_m15, batch_h1)
                numerator, denominator = _weighted_loss_components(
                    logits, batch_labels, class_weights
                )
                validation_numerator += numerator
                validation_denominator += denominator
        validation_loss = validation_numerator / validation_denominator
        validation_history.append(validation_loss)
        if validation_loss < best_loss - config.minimum_improvement:
            best_loss = validation_loss
            best_state = deepcopy(model.state_dict())
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= config.early_stopping_patience:
                break

    model.load_state_dict(best_state)
    model.eval()
    return TrainingResult(
        model=model,
        seed=seed,
        epochs_completed=len(train_history),
        best_validation_loss=best_loss,
        train_losses=tuple(train_history),
        validation_losses=tuple(validation_history),
    )


def select_confidence_threshold(
    validation_scores: Mapping[float, Mapping[str, float]],
) -> float:
    """Maximize the weakest trading window; mean score only breaks exact ties."""

    missing = [value for value in CONFIDENCE_CANDIDATES if value not in validation_scores]
    if missing:
        raise ValueError(f"missing confidence candidates: {missing}")

    def robust_score(threshold: float) -> tuple[float, float, float]:
        windows = tuple(float(value) for value in validation_scores[threshold].values())
        if not windows:
            raise ValueError(f"confidence {threshold:.2f} has no trading windows")
        return (min(windows), sum(windows) / len(windows), -threshold)

    return max(CONFIDENCE_CANDIDATES, key=robust_score)


def select_active_trading_candidate(
    by_threshold: Mapping[float, Mapping[str, TradingWindowMetrics]],
) -> float:
    """Apply every ACTIVE validation gate, then maximize the weakest window."""

    missing = [value for value in CONFIDENCE_CANDIDATES if value not in by_threshold]
    if missing:
        raise ValueError(f"missing confidence candidates: {missing}")
    eligible: dict[float, tuple[float, float]] = {}
    for threshold in CONFIDENCE_CANDIDATES:
        windows = tuple(by_threshold[threshold].values())
        if not windows or not all(window.passes_window_gate() for window in windows):
            continue
        candidate_profit = sum(window.profit for window in windows)
        original_profit = sum(window.original_profit for window in windows)
        if original_profit == 0:
            aggregate_change = float("inf") if candidate_profit > 0 else 0.0
        else:
            aggregate_change = (candidate_profit - original_profit) / abs(
                original_profit
            )
        if aggregate_change < 0.10:
            continue
        eligible[threshold] = (
            min(window.relative_profit_change() for window in windows),
            aggregate_change,
        )
    if not eligible:
        raise ValueError("no confidence candidate passes all ACTIVE trading gates")
    return max(eligible, key=lambda value: (*eligible[value], -value))


def export_candidate_onnx(
    model: TemporalCNN, destination: Path
) -> Path:
    """Guarded product export; low-level exporter remains available only for probes/tests."""

    assert_training_allowed(DEFAULT_GATE)
    return export_temporal_cnn_onnx(model, destination)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_sha256(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        contiguous = tensor.detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(json.dumps(list(contiguous.shape)).encode("ascii"))
        buffer = io.BytesIO()
        np.save(buffer, contiguous.numpy(), allow_pickle=False)
        digest.update(buffer.getvalue())
    return digest.hexdigest()


def build_reproducibility_receipt(
    dataset_path: Path,
    model: torch.nn.Module,
    config: TrainingConfig,
    *,
    seed: int,
    selected_confidence: float,
) -> dict[str, object]:
    if seed not in TRAINING_SEEDS:
        raise ValueError(f"seed must be one of {TRAINING_SEEDS}")
    if selected_confidence not in CONFIDENCE_CANDIDATES:
        raise ValueError(f"confidence must be one of {CONFIDENCE_CANDIDATES}")
    canonical_config = json.dumps(
        asdict(config), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "dataset_sha256": _sha256_file(Path(dataset_path)),
        "model_sha256": _model_sha256(model),
        "config_sha256": hashlib.sha256(canonical_config).hexdigest(),
        "selected_seed": seed,
        "allowed_seeds": list(TRAINING_SEEDS),
        "selected_confidence": selected_confidence,
        "class_margin": 0.15,
        "confidence_candidates": list(CONFIDENCE_CANDIDATES),
        "environment": {
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
            "torch": importlib.metadata.version("torch"),
            "onnx": importlib.metadata.version("onnx"),
            "onnxruntime": importlib.metadata.version("onnxruntime"),
            "pandas": importlib.metadata.version("pandas"),
            "scikit_learn": importlib.metadata.version("scikit-learn"),
        },
    }
