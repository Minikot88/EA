from datetime import datetime, timedelta, timezone

import pytest

from ml.dataset_pipeline import build_counterfactual_sample, locked_split
from ml.feature_extraction import OHLCVBar
from ml.virtual_original_basket import OriginalConfig, Tick


def test_locked_time_splits_and_twenty_four_hour_purge_are_immutable() -> None:
    utc = timezone.utc
    assert locked_split(datetime(2024, 6, 1, tzinfo=utc)) == "train"
    assert locked_split(datetime(2025, 6, 1, tzinfo=utc)) == "validation"
    assert locked_split(datetime(2026, 3, 1, tzinfo=utc)) == "locked_oos"
    assert locked_split(datetime(2026, 8, 1, tzinfo=utc)) == "final_holdout"
    boundary = datetime(2026, 1, 1, tzinfo=utc)
    assert locked_split(boundary - timedelta(hours=23)) is None
    assert locked_split(boundary + timedelta(hours=23)) is None
    assert locked_split(boundary - timedelta(hours=24)) is None
    assert locked_split(boundary + timedelta(hours=24)) is None
    assert locked_split(boundary - timedelta(hours=24, seconds=1)) == "validation"
    assert locked_split(boundary + timedelta(hours=24, seconds=1)) == "locked_oos"


def test_dataset_builder_rejects_future_bar_even_if_marked_closed() -> None:
    candidate = datetime(2025, 6, 1, tzinfo=timezone.utc)

    def bars(count: int, minutes: int) -> list[OHLCVBar]:
        return [
            OHLCVBar(
                timestamp=candidate - timedelta(minutes=(count - index) * minutes),
                open=100,
                high=101,
                low=99,
                close=100,
                tick_volume=100 + index,
                spread=0.2,
                atr=2,
            )
            for index in range(count)
        ]

    m5 = bars(116, 5)
    m5[-1] = OHLCVBar(
        timestamp=candidate + timedelta(minutes=5),
        open=100,
        high=101,
        low=99,
        close=100,
        tick_volume=999,
        spread=0.2,
        atr=2,
    )
    forward_ticks = [
        Tick(candidate.timestamp(), 99.9, 100.1),
        Tick((candidate + timedelta(hours=24)).timestamp(), 99.9, 100.1),
    ]
    with pytest.raises(ValueError, match="after the candidate"):
        build_counterfactual_sample(
            timestamp=candidate,
            m5=m5,
            m15=bars(116, 15),
            h1=bars(68, 60),
            ticks=forward_ticks,
            original_config=OriginalConfig(),
        )


def test_candidate_timestamp_must_equal_first_forward_tick() -> None:
    candidate = datetime(2025, 6, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="must equal the first forward tick"):
        build_counterfactual_sample(
            timestamp=candidate,
            m5=[],
            m15=[],
            h1=[],
            ticks=[Tick(candidate.timestamp() + 1, 99.9, 100.1)],
            original_config=OriginalConfig(),
        )
