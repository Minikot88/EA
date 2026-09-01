"""Temporal CNN used by Kurama's embedded ONNX first-entry classifier."""

from __future__ import annotations

from pathlib import Path

import torch
from torch import Tensor, nn


class _TimeframeBranch(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv1d(8, 32, kernel_size=5),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2),
            nn.Conv1d(32, 64, kernel_size=3),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )

    def forward(self, values: Tensor) -> Tensor:
        # Public tensors are [batch, bars, features]; Conv1d expects channels first.
        return self.layers(values.transpose(1, 2)).squeeze(-1)


class TemporalCNN(nn.Module):
    """Three-branch M5/M15/H1 classifier producing BUY/SELL/SKIP probabilities."""

    def __init__(self) -> None:
        super().__init__()
        self.m5_branch = _TimeframeBranch()
        self.m15_branch = _TimeframeBranch()
        self.h1_branch = _TimeframeBranch()
        self.head = nn.Sequential(
            nn.Linear(192, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 3),
        )

    def forward_logits(self, m5: Tensor, m15: Tensor, h1: Tensor) -> Tensor:
        encoded = torch.cat(
            (self.m5_branch(m5), self.m15_branch(m15), self.h1_branch(h1)), dim=1
        )
        return self.head(encoded)

    def forward(self, m5: Tensor, m15: Tensor, h1: Tensor) -> Tensor:
        return torch.softmax(self.forward_logits(m5, m15, h1), dim=1)


def export_temporal_cnn_onnx(model: TemporalCNN, destination: Path) -> Path:
    """Export the exact fixed-window model used by MQL5 and return its path."""

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    model = model.eval().cpu()
    samples = (
        torch.zeros(1, 96, 8, dtype=torch.float32),
        torch.zeros(1, 96, 8, dtype=torch.float32),
        torch.zeros(1, 48, 8, dtype=torch.float32),
    )
    torch.onnx.export(
        model,
        samples,
        destination,
        input_names=("m5", "m15", "h1"),
        output_names=("probabilities",),
        dynamic_axes={
            "m5": {0: "batch"},
            "m15": {0: "batch"},
            "h1": {0: "batch"},
            "probabilities": {0: "batch"},
        },
        opset_version=17,
        do_constant_folding=True,
        dynamo=False,
    )
    return destination
