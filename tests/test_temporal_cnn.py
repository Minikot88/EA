from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
onnxruntime = pytest.importorskip("onnxruntime")

from ml.temporal_cnn import TemporalCNN, export_temporal_cnn_onnx


def sample_inputs() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    torch.manual_seed(7)
    return (
        torch.randn(1, 96, 8),
        torch.randn(1, 96, 8),
        torch.randn(1, 48, 8),
    )


def test_temporal_cnn_has_exact_three_branch_architecture_and_output_shape() -> None:
    model = TemporalCNN().eval()
    convolutions = [module for module in model.modules() if isinstance(module, torch.nn.Conv1d)]
    assert [(layer.in_channels, layer.out_channels, layer.kernel_size) for layer in convolutions] == [
        (8, 32, (5,)),
        (32, 64, (3,)),
    ] * 3
    assert len([module for module in model.modules() if isinstance(module, torch.nn.AdaptiveAvgPool1d)]) == 3
    linears = [module for module in model.modules() if isinstance(module, torch.nn.Linear)]
    assert [(layer.in_features, layer.out_features) for layer in linears] == [(192, 64), (64, 3)]
    dropouts = [module for module in model.modules() if isinstance(module, torch.nn.Dropout)]
    assert [layer.p for layer in dropouts] == [0.2]

    probabilities = model(*sample_inputs())
    assert probabilities.shape == (1, 3)
    assert torch.allclose(probabilities.sum(dim=1), torch.ones(1), atol=1e-6)


def test_temporal_cnn_eval_forward_and_onnx_probabilities_are_deterministic(tmp_path: Path) -> None:
    torch.manual_seed(11)
    model = TemporalCNN().eval()
    inputs = sample_inputs()
    first = model(*inputs)
    second = model(*inputs)
    assert torch.equal(first, second)

    artifact = tmp_path / "temporal_cnn.onnx"
    export_temporal_cnn_onnx(model, artifact)
    session = onnxruntime.InferenceSession(str(artifact), providers=["CPUExecutionProvider"])
    names = [item.name for item in session.get_inputs()]
    exported = session.run(None, {name: tensor.numpy() for name, tensor in zip(names, inputs)})[0]
    assert torch.allclose(first, torch.from_numpy(exported), atol=1e-5, rtol=1e-5)
