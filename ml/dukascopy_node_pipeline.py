"""Pinned monthly Dukascopy JSON-API acquisition with streaming audits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


DUKASCOPY_NODE_VERSION = "1.50.0"
DUKASCOPY_NODE_NPM_INTEGRITY = (
    "sha512-o2Co/asUD/TXFNhblJUYkRseHMt/uvFrnhzOKWezLuiFJqbl4Zn2oJGL4/W+PY1b2YsI11+9+TO40qNQBAj8/w=="
)
DUKASCOPY_NODE_NPM_SHASUM = "25ce461e28ae4ad37d74bcd2f2656e8266301062"
TOOL_ROOT = Path(__file__).resolve().parent / "tools" / "dukascopy-node"
PACKAGE_LOCK_PATH = TOOL_ROOT / "package-lock.json"
DUKASCOPY_CLI = TOOL_ROOT / "node_modules" / ".bin" / "dukascopy-node.cmd"
DEFAULT_ROOT = (
    Path(__file__).resolve().parent / "data" / "raw" / "dukascopy_node" / "XAUUSD"
)
EXPECTED_HEADER = ["timestamp", "askPrice", "bidPrice"]


@dataclass(frozen=True)
class MonthJob:
    month: str
    date_from: str
    date_to: str


@dataclass(frozen=True)
class MonthAudit:
    month: str
    status: str
    path: str | None = None
    sha256: str | None = None
    bytes: int = 0
    quote_count: int = 0
    first_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None
    minimum_bid: float | None = None
    maximum_ask: float | None = None
    maximum_spread: float | None = None
    error: str | None = None


def month_jobs(date_from: str = "2021-01", date_to: str = "2025-12") -> list[MonthJob]:
    current = datetime.strptime(date_from, "%Y-%m")
    end = datetime.strptime(date_to, "%Y-%m")
    if end < current:
        raise ValueError("end month must not precede start month")
    jobs: list[MonthJob] = []
    while current <= end:
        next_month = (
            current.replace(year=current.year + 1, month=1)
            if current.month == 12
            else current.replace(month=current.month + 1)
        )
        jobs.append(
            MonthJob(
                month=current.strftime("%Y-%m"),
                date_from=current.strftime("%Y-%m-%d"),
                date_to=next_month.strftime("%Y-%m-%d"),
            )
        )
        current = next_month
    return jobs


def expected_filename(job: MonthJob) -> str:
    return f"xauusd-tick-{job.date_from}-{job.date_to}.csv"


def verify_tool_lock(lock_path: Path = PACKAGE_LOCK_PATH) -> None:
    try:
        lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
        package = lock["packages"]["node_modules/dukascopy-node"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("verified dukascopy-node package-lock is missing") from error
    if (
        package.get("version") != DUKASCOPY_NODE_VERSION
        or package.get("integrity") != DUKASCOPY_NODE_NPM_INTEGRITY
    ):
        raise RuntimeError("dukascopy-node package-lock integrity mismatch")


def build_npx_command(
    job: MonthJob, output_directory: Path, cache_directory: Path | None = None
) -> list[str]:
    cache_directory = cache_directory or output_directory.parent / ".dukascopy-cache"
    return [
        str(DUKASCOPY_CLI),
        "-i",
        "xauusd",
        "-from",
        job.date_from,
        "-to",
        job.date_to,
        "-t",
        "tick",
        "-f",
        "csv",
        "-dir",
        str(output_directory),
        "-bs",
        "5",
        "-bp",
        "1500",
        "-r",
        "5",
        "-rp",
        "2000",
        "-ch",
        "-chpath",
        str(cache_directory),
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_tick_csv(path: Path, month: str) -> MonthAudit:
    path = Path(path)
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    previous = -1
    count = 0
    first: int | None = None
    last: int | None = None
    minimum_bid = math.inf
    maximum_ask = -math.inf
    maximum_spread = 0.0
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        try:
            header = next(reader)
        except StopIteration as error:
            raise ValueError(f"{month} CSV is empty") from error
        if header != EXPECTED_HEADER:
            raise ValueError(f"{month} CSV header changed: {header}")
        for line_number, row in enumerate(reader, start=2):
            if len(row) != 3:
                raise ValueError(f"{month}:{line_number} must contain 3 columns")
            try:
                timestamp_ms = int(row[0])
                ask = float(row[1])
                bid = float(row[2])
            except ValueError as error:
                raise ValueError(f"{month}:{line_number} contains invalid numbers") from error
            if not start_ms <= timestamp_ms < end_ms:
                raise ValueError(f"{month}:{line_number} timestamp escaped its month")
            if timestamp_ms <= previous:
                raise ValueError(
                    f"{month}:{line_number} timestamp is duplicate or out of order"
                )
            if (
                not math.isfinite(bid)
                or not math.isfinite(ask)
                or bid <= 0
                or ask <= 0
                or ask < bid
            ):
                raise ValueError(f"{month}:{line_number} quote is invalid or crossed")
            first = timestamp_ms if first is None else first
            last = timestamp_ms
            previous = timestamp_ms
            count += 1
            minimum_bid = min(minimum_bid, bid)
            maximum_ask = max(maximum_ask, ask)
            maximum_spread = max(maximum_spread, ask - bid)
    if count == 0:
        raise ValueError(f"{month} contains no quotes")
    return MonthAudit(
        month=month,
        status="audited",
        path=str(path),
        sha256=_sha256_file(path),
        bytes=path.stat().st_size,
        quote_count=count,
        first_timestamp_ms=first,
        last_timestamp_ms=last,
        minimum_bid=minimum_bid,
        maximum_ask=maximum_ask,
        maximum_spread=maximum_spread,
    )


def quarantine_invalid_file(path: Path) -> Path:
    path = Path(path)
    candidate = path.with_suffix(path.suffix + ".invalid")
    counter = 1
    while candidate.exists():
        candidate = path.with_suffix(path.suffix + f".invalid.{counter}")
        counter += 1
    path.rename(candidate)
    return candidate


def acquire_month(
    job: MonthJob,
    *,
    root: Path = DEFAULT_ROOT,
    timeout_seconds: int = 1800,
) -> MonthAudit:
    root = Path(root)
    verify_tool_lock()
    if not DUKASCOPY_CLI.is_file():
        raise RuntimeError(
            "dukascopy-node install is missing; run npm ci in ml/tools/dukascopy-node"
        )
    destination = root / job.date_from[:4] / expected_filename(job)
    if destination.exists():
        try:
            return audit_tick_csv(destination, job.month)
        except ValueError:
            quarantine_invalid_file(destination)

    staging = root / ".staging" / job.month
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    command = build_npx_command(job, staging, root / ".dukascopy-cache")
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"dukascopy-node exit {completed.returncode}: "
                f"{completed.stderr[-1000:] or completed.stdout[-1000:]}"
            )
        staged_file = staging / expected_filename(job)
        audit_tick_csv(staged_file, job.month)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_file, destination)
        shutil.rmtree(staging)
        return audit_tick_csv(destination, job.month)
    except Exception as error:
        return MonthAudit(
            month=job.month,
            status="error",
            error=f"{type(error).__name__}: {error}",
        )


def _read_latest_state(state_path: Path) -> dict[str, MonthAudit]:
    result: dict[str, MonthAudit] = {}
    if not state_path.exists():
        return result
    lines = state_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            audit = MonthAudit(**json.loads(line))
        except (json.JSONDecodeError, TypeError) as error:
            if index == len(lines) - 1:
                continue
            raise RuntimeError(f"monthly state is corrupt at line {index + 1}") from error
        result[audit.month] = audit
    return result


def build_partial_manifest(audits: Iterable[MonthAudit]) -> dict[str, object]:
    latest = {audit.month: audit for audit in audits}
    expected = [job.month for job in month_jobs()]
    audited = sorted(
        month for month, audit in latest.items() if audit.status == "audited"
    )
    failed = sorted(month for month, audit in latest.items() if audit.status == "error")
    return {
        "schema_version": 1,
        "source": "Dukascopy",
        "source_symbol": "XAUUSD",
        "downloader": f"dukascopy-node@{DUKASCOPY_NODE_VERSION}",
        "downloader_npm_integrity": DUKASCOPY_NODE_NPM_INTEGRITY,
        "downloader_npm_shasum": DUKASCOPY_NODE_NPM_SHASUM,
        "tool_lock_sha256": _sha256_file(PACKAGE_LOCK_PATH),
        "utc_timestamp_unit": "milliseconds",
        "quote_fields": ["timestamp_ms", "bid", "ask"],
        "expected_months": expected,
        "monthly_hashes": {
            month: latest[month].sha256 for month in audited
        },
        "monthly_audits": {month: asdict(latest[month]) for month in audited},
        "gap_receipt": {
            "missing_months": [month for month in expected if month not in audited]
        },
        "failed_months": failed,
        "files_complete": len(audited) == len(expected),
    }


def acquire_all_months(
    *, root: Path = DEFAULT_ROOT, limit: int | None = None
) -> dict[str, object]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "monthly_state.jsonl"
    jobs = month_jobs()
    if limit is not None:
        jobs = jobs[:limit]
    latest = _read_latest_state(state_path)
    with state_path.open("a", encoding="utf-8", buffering=1) as state:
        for index, job in enumerate(jobs, start=1):
            prior = latest.get(job.month)
            if prior is not None and prior.status == "audited" and prior.path:
                try:
                    audit = audit_tick_csv(Path(prior.path), job.month)
                except (OSError, ValueError):
                    audit = acquire_month(job, root=root)
            else:
                audit = acquire_month(job, root=root)
            latest[job.month] = audit
            state.write(json.dumps(asdict(audit), sort_keys=True) + "\n")
            print(
                f"[{index}/{len(jobs)}] {job.month} {audit.status} "
                f"quotes={audit.quote_count} bytes={audit.bytes}",
                flush=True,
            )
            if audit.status == "error":
                print(audit.error, flush=True)
                break
    manifest = build_partial_manifest(latest.values())
    (root / "partial_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    manifest = acquire_all_months(root=args.root, limit=args.limit)
    print(
        json.dumps(
            {
                "files_complete": manifest["files_complete"],
                "missing_months": len(manifest["gap_receipt"]["missing_months"]),
            },
            sort_keys=True,
        )
    )
    if manifest["failed_months"]:
        return 1
    if args.limit is None and not manifest["files_complete"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
