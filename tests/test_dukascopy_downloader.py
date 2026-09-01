import lzma
import struct
import json
from datetime import datetime, timezone

import pytest

from ml.dukascopy_downloader import (
    _load_completed,
    audit_payload,
    decode_bi5_quotes,
    dukascopy_hour_url,
)


def test_hour_url_uses_zero_based_month_and_locked_symbol() -> None:
    hour = datetime(2024, 1, 2, 3, tzinfo=timezone.utc)
    assert dukascopy_hour_url("XAUUSD", hour).endswith(
        "/XAUUSD/2024/00/02/03h_ticks.bi5"
    )
    with pytest.raises(ValueError):
        dukascopy_hour_url("EURUSD", hour)


def test_bi5_decode_uses_utc_milliseconds_ask_bid_and_xau_divisor() -> None:
    hour = datetime(2024, 1, 2, 3, tzinfo=timezone.utc)
    raw = b"".join(
        (
            struct.pack(">3I2f", 1, 2_050_200, 2_050_100, 1.0, 2.0),
            struct.pack(">3I2f", 2, 2_050_300, 2_050_200, 1.0, 2.0),
        )
    )
    payload = lzma.compress(raw)
    quotes = decode_bi5_quotes(payload, hour=hour)
    assert quotes[0].timestamp_ms == int(hour.timestamp() * 1000) + 1
    assert quotes[0].bid == 2050.1
    assert quotes[0].ask == 2050.2
    audit = audit_payload(payload, hour=hour, url="test")
    assert audit.tick_count == 2
    assert audit.status == "data"


def test_bi5_decode_rejects_crossed_or_duplicate_quotes() -> None:
    hour = datetime(2024, 1, 2, 3, tzinfo=timezone.utc)
    crossed = lzma.compress(struct.pack(">3I2f", 1, 2_000_000, 2_001_000, 1, 1))
    with pytest.raises(ValueError, match="crossed"):
        decode_bi5_quotes(crossed, hour=hour)
    duplicate = lzma.compress(
        struct.pack(">3I2f", 1, 2_001_000, 2_000_000, 1, 1)
        + struct.pack(">3I2f", 1, 2_001_000, 2_000_000, 1, 1)
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        decode_bi5_quotes(duplicate, hour=hour)


def test_hourly_resume_rechecks_file_hash_before_skipping(tmp_path) -> None:
    cached = tmp_path / "hour.bi5"
    cached.write_bytes(b"valid")
    state = tmp_path / "state.jsonl"
    state.write_text(
        json.dumps(
            {
                "hour_utc": "2024-01-01T00:00:00+00:00",
                "status": "data",
                "path": str(cached),
                "compressed_sha256": "f" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert _load_completed(state, retry_void=False) == set()
