"""Resumable, audited Dukascopy hourly BI5 downloader for XAUUSD.

Raw files and state live under ``ml/data/raw`` and are ignored by Git.  No
forward filling or quote repair is performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import struct
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

from ml.hybrid_data_contract import TickQuote


BASE_URL = "https://datafeed.dukascopy.com/datafeed"
TICK_STRUCT = struct.Struct(">3I2f")
XAUUSD_PRICE_DIVISOR = 1_000.0
DEFAULT_RAW_ROOT = Path(__file__).resolve().parent / "data" / "raw" / "dukascopy"
_REQUEST_LOCK = threading.Lock()
_NEXT_REQUEST_AT = 0.0


@dataclass(frozen=True)
class HourAudit:
    hour_utc: str
    status: str
    url: str
    http_status: int
    compressed_bytes: int = 0
    compressed_sha256: str = ""
    tick_count: int = 0
    first_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None
    minimum_bid: float | None = None
    maximum_ask: float | None = None
    maximum_spread: float | None = None
    path: str | None = None
    error: str | None = None


def _utc_hour(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    value = value.astimezone(timezone.utc)
    if value.minute or value.second or value.microsecond:
        raise ValueError("datetime must be aligned to an exact UTC hour")
    return value


def dukascopy_hour_url(symbol: str, hour: datetime) -> str:
    hour = _utc_hour(hour)
    symbol = symbol.upper()
    if symbol != "XAUUSD":
        raise ValueError("this locked downloader only permits XAUUSD")
    # Dukascopy's legacy datafeed path numbers January as 00.
    return (
        f"{BASE_URL}/{symbol}/{hour.year:04d}/{hour.month - 1:02d}/"
        f"{hour.day:02d}/{hour.hour:02d}h_ticks.bi5"
    )


def raw_hour_path(root: Path, symbol: str, hour: datetime) -> Path:
    hour = _utc_hour(hour)
    return (
        Path(root)
        / symbol.upper()
        / f"{hour.year:04d}"
        / f"{hour.month:02d}"
        / f"{hour.day:02d}"
        / f"{hour.hour:02d}h_ticks.bi5"
    )


def decode_bi5_quotes(
    payload: bytes,
    *,
    hour: datetime,
    price_divisor: float = XAUUSD_PRICE_DIVISOR,
) -> list[TickQuote]:
    hour = _utc_hour(hour)
    if not payload:
        return []
    try:
        decoded = lzma.decompress(payload)
    except lzma.LZMAError as error:
        raise ValueError("BI5 LZMA decode failed") from error
    if len(decoded) % TICK_STRUCT.size:
        raise ValueError("decoded BI5 length is not divisible by 20 bytes")
    base_ms = int(hour.timestamp() * 1000)
    quotes: list[TickQuote] = []
    previous = -1
    for offset_ms, ask_raw, bid_raw, _ask_volume, _bid_volume in TICK_STRUCT.iter_unpack(
        decoded
    ):
        if offset_ms >= 3_600_000:
            raise ValueError("tick millisecond offset escaped its UTC hour")
        timestamp_ms = base_ms + offset_ms
        if timestamp_ms <= previous:
            raise ValueError("BI5 timestamps are not strictly increasing and unique")
        ask = ask_raw / price_divisor
        bid = bid_raw / price_divisor
        if bid <= 0 or ask <= 0 or ask < bid:
            raise ValueError("BI5 contains invalid or crossed Bid/Ask quotes")
        quotes.append(TickQuote(timestamp_ms, bid, ask))
        previous = timestamp_ms
    return quotes


def audit_payload(payload: bytes, *, hour: datetime, url: str) -> HourAudit:
    quotes = decode_bi5_quotes(payload, hour=hour)
    if not quotes:
        return HourAudit(
            hour_utc=hour.isoformat(), status="void", url=url, http_status=200
        )
    bids = [quote.bid for quote in quotes]
    asks = [quote.ask for quote in quotes]
    spreads = [quote.ask - quote.bid for quote in quotes]
    if min(bids) < 100 or max(asks) > 20_000:
        raise ValueError("decoded XAUUSD prices are implausible; point divisor is unverified")
    return HourAudit(
        hour_utc=hour.isoformat(),
        status="data",
        url=url,
        http_status=200,
        compressed_bytes=len(payload),
        compressed_sha256=hashlib.sha256(payload).hexdigest(),
        tick_count=len(quotes),
        first_timestamp_ms=quotes[0].timestamp_ms,
        last_timestamp_ms=quotes[-1].timestamp_ms,
        minimum_bid=min(bids),
        maximum_ask=max(asks),
        maximum_spread=max(spreads),
    )


def _pace_requests(interval: float) -> None:
    global _NEXT_REQUEST_AT
    with _REQUEST_LOCK:
        now = time.monotonic()
        delay = max(0.0, _NEXT_REQUEST_AT - now)
        if delay:
            time.sleep(delay)
        _NEXT_REQUEST_AT = max(now, _NEXT_REQUEST_AT) + interval


def _fetch(
    hour: datetime, *, timeout: float, retries: int, request_interval: float
) -> tuple[bytes, int, str]:
    url = dukascopy_hour_url("XAUUSD", hour)
    request = urllib.request.Request(
        url, headers={"User-Agent": "Kurama-Research/0.2 (+audited-hourly-download)"}
    )
    for attempt in range(retries + 1):
        _pace_requests(request_interval)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(), int(response.status), url
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return b"", 404, url
            if error.code < 500 or attempt == retries:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == retries:
                raise
        time.sleep(min(2**attempt, 8))
    raise RuntimeError("unreachable retry state")


def download_one_hour(
    hour: datetime,
    *,
    raw_root: Path = DEFAULT_RAW_ROOT,
    timeout: float = 30.0,
    retries: int = 3,
    request_interval: float = 0.4,
) -> HourAudit:
    hour = _utc_hour(hour)
    url = dukascopy_hour_url("XAUUSD", hour)
    destination = raw_hour_path(raw_root, "XAUUSD", hour)
    try:
        payload, http_status, _ = _fetch(
            hour,
            timeout=timeout,
            retries=retries,
            request_interval=request_interval,
        )
        if http_status == 404 or not payload:
            return HourAudit(
                hour_utc=hour.isoformat(),
                status="void",
                url=url,
                http_status=http_status,
            )
        audit = audit_payload(payload, hour=hour, url=url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
        return HourAudit(**{**asdict(audit), "path": str(destination)})
    except Exception as error:  # state captures exact failed hour for a safe resume
        return HourAudit(
            hour_utc=hour.isoformat(),
            status="error",
            url=url,
            http_status=getattr(error, "code", 0) or 0,
            error=f"{type(error).__name__}: {error}",
        )


def iter_hours(start: datetime, end: datetime) -> Iterable[datetime]:
    current = _utc_hour(start)
    end = _utc_hour(end)
    if end <= current:
        raise ValueError("end must be later than start")
    while current < end:
        yield current
        current += timedelta(hours=1)


def _load_completed(state_path: Path, *, retry_void: bool) -> set[str]:
    completed: set[str] = set()
    if not state_path.exists():
        return completed
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") == "data":
            path_value = record.get("path")
            expected_hash = record.get("compressed_sha256")
            if not isinstance(path_value, str) or not isinstance(expected_hash, str):
                continue
            path = Path(path_value)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                continue
            completed.add(str(record["hour_utc"]))
        elif record.get("status") == "void" and not retry_void:
            completed.add(str(record["hour_utc"]))
    return completed


def download_range(
    *,
    start: datetime,
    end: datetime,
    raw_root: Path = DEFAULT_RAW_ROOT,
    workers: int = 6,
    timeout: float = 30.0,
    retries: int = 3,
    request_interval: float = 0.4,
    retry_void: bool = False,
    max_hours: int | None = None,
) -> dict[str, int]:
    if not 1 <= workers <= 12:
        raise ValueError("workers must be between 1 and 12")
    state_path = Path(raw_root) / "XAUUSD" / "download_state.jsonl"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    completed = _load_completed(state_path, retry_void=retry_void)
    hours = [hour for hour in iter_hours(start, end) if hour.isoformat() not in completed]
    if max_hours is not None:
        hours = hours[:max_hours]
    summary = {"requested": len(hours), "data": 0, "void": 0, "error": 0}
    with state_path.open("a", encoding="utf-8", buffering=1) as state:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    download_one_hour,
                    hour,
                    raw_root=raw_root,
                    timeout=timeout,
                    retries=retries,
                    request_interval=request_interval,
                ): hour
                for hour in hours
            }
            for future in as_completed(futures):
                audit = future.result()
                summary[audit.status] += 1
                state.write(json.dumps(asdict(audit), sort_keys=True) + "\n")
    return summary


def _parse_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--request-interval", type=float, default=0.4)
    parser.add_argument("--retry-void", action="store_true")
    parser.add_argument("--max-hours", type=int)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    args = parser.parse_args(argv)
    summary = download_range(
        start=_parse_utc(args.date_from),
        end=_parse_utc(args.date_to),
        raw_root=args.raw_root,
        workers=args.workers,
        timeout=args.timeout,
        retries=args.retries,
        request_interval=args.request_interval,
        retry_void=args.retry_void,
        max_hours=args.max_hours,
    )
    print(json.dumps(summary, sort_keys=True))
    return 1 if summary["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
