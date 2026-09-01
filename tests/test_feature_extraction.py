import math

import numpy as np
import pytest

from ml.feature_extraction import FEATURE_NAMES, OHLCVBar, extract_multitimeframe_features


def bar(index: int, *, closed: bool = True) -> OHLCVBar:
    close = 100.0 + index
    return OHLCVBar(
        timestamp=index,
        open=close - 0.25,
        high=close + 0.75,
        low=close - 0.75,
        close=close,
        tick_volume=100 + index,
        spread=0.2,
        atr=2.0,
        closed=closed,
    )


def test_closed_bar_feature_tensors_have_required_shapes_and_order() -> None:
    features = extract_multitimeframe_features(
        m5=[bar(index) for index in range(116)],
        m15=[bar(index) for index in range(116)],
        h1=[bar(index) for index in range(68)],
    )
    assert FEATURE_NAMES == (
        "close_log_return",
        "open_gap_atr",
        "high_atr",
        "low_atr",
        "body_atr",
        "range_atr",
        "tick_volume_zscore",
        "spread_atr",
    )
    assert features["m5"].shape == (96, 8)
    assert features["m15"].shape == (96, 8)
    assert features["h1"].shape == (48, 8)


def test_eight_feature_formulae_are_hand_checked() -> None:
    bars = [bar(index) for index in range(116)]
    row = extract_multitimeframe_features(m5=bars, m15=bars, h1=[bar(index) for index in range(68)])["m5"][-1]
    current, previous = bars[-1], bars[-2]
    expected = np.array(
        [
            math.log(current.close / previous.close),
            (current.open - previous.close) / current.atr,
            (current.high - current.open) / current.atr,
            (current.low - current.open) / current.atr,
            (current.close - current.open) / current.atr,
            (current.high - current.low) / current.atr,
            (current.tick_volume - np.mean([item.tick_volume for item in bars[-21:-1]]))
            / np.std([item.tick_volume for item in bars[-21:-1]], ddof=0),
            current.spread / current.atr,
        ]
    )
    assert np.allclose(row, expected, atol=1e-12)


def test_unclosed_bar_cannot_change_feature_tensors_or_be_used_as_history() -> None:
    closed_m5 = [bar(index) for index in range(116)]
    reference = extract_multitimeframe_features(m5=closed_m5, m15=closed_m5, h1=[bar(index) for index in range(68)])
    with_unclosed = closed_m5 + [bar(9999, closed=False)]
    observed = extract_multitimeframe_features(m5=with_unclosed, m15=with_unclosed, h1=[bar(index) for index in range(68)] + [bar(9999, closed=False)])
    for timeframe in ("m5", "m15", "h1"):
        assert np.array_equal(observed[timeframe], reference[timeframe])


def test_incomplete_volume_warmup_blocks_inference() -> None:
    with pytest.raises(ValueError, match="116 closed bars"):
        extract_multitimeframe_features(
            m5=[bar(index) for index in range(115)],
            m15=[bar(index) for index in range(116)],
            h1=[bar(index) for index in range(68)],
        )


def test_duplicate_or_out_of_order_closed_bars_are_rejected() -> None:
    m5 = [bar(index) for index in range(116)]
    m5[-1] = bar(114)
    with pytest.raises(ValueError, match="strictly increasing and unique"):
        extract_multitimeframe_features(
            m5=m5,
            m15=[bar(index) for index in range(116)],
            h1=[bar(index) for index in range(68)],
        )
