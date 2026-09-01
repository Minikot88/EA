import json
from pathlib import Path

import pytest

from ml.dukascopy_node_pipeline import (
    DUKASCOPY_NODE_NPM_SHASUM,
    DUKASCOPY_NODE_VERSION,
    MonthAudit,
    _read_latest_state,
    audit_tick_csv,
    build_npx_command,
    month_jobs,
    main,
    quarantine_invalid_file,
    verify_tool_lock,
)


def test_locked_month_jobs_cover_exactly_2021_through_2025() -> None:
    jobs = month_jobs()
    assert len(jobs) == 60
    assert (jobs[0].month, jobs[0].date_from, jobs[0].date_to) == (
        "2021-01",
        "2021-01-01",
        "2021-02-01",
    )
    assert (jobs[-1].month, jobs[-1].date_to) == ("2025-12", "2026-01-01")


def test_npx_command_pins_downloader_version(tmp_path: Path) -> None:
    command = build_npx_command(month_jobs()[0], tmp_path)
    assert command[0].endswith("dukascopy-node.cmd")
    assert command[command.index("-i") + 1] == "xauusd"
    assert command[command.index("-bs") + 1] == "5"
    assert "-ch" in command
    assert len(DUKASCOPY_NODE_NPM_SHASUM) == 40


def test_package_lock_enforces_exact_npm_integrity(tmp_path: Path) -> None:
    lock = tmp_path / "package-lock.json"
    lock.write_text(
        '{"packages":{"node_modules/dukascopy-node":'
        '{"version":"1.50.0","integrity":"wrong"}}}',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="integrity mismatch"):
        verify_tool_lock(lock)


def test_monthly_csv_audit_is_streaming_strict_and_hashed(tmp_path: Path) -> None:
    csv_file = tmp_path / "month.csv"
    csv_file.write_text(
        "timestamp,askPrice,bidPrice\n"
        "1704067200000,2060.2,2060.1\n"
        "1704067200001,2060.3,2060.2\n",
        encoding="utf-8",
    )
    audit = audit_tick_csv(csv_file, "2024-01")
    assert audit.status == "audited"
    assert audit.quote_count == 2
    assert len(audit.sha256 or "") == 64

    csv_file.write_text(
        "timestamp,askPrice,bidPrice\n"
        "1704067200000,2060.2,2060.1\n"
        "1704067200000,2060.1,2060.2\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        audit_tick_csv(csv_file, "2024-01")


def test_full_acquisition_cli_returns_nonzero_when_manifest_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ml.dukascopy_node_pipeline.acquire_all_months",
        lambda **_kwargs: {
            "files_complete": False,
            "failed_months": ["2021-03"],
            "gap_receipt": {"missing_months": ["2021-03"]},
        },
    )
    assert main([]) == 1


def test_quarantine_never_collides_with_prior_invalid_file(tmp_path: Path) -> None:
    source = tmp_path / "month.csv"
    source.write_text("bad", encoding="utf-8")
    (tmp_path / "month.csv.invalid").write_text("older", encoding="utf-8")
    quarantined = quarantine_invalid_file(source)
    assert quarantined.name == "month.csv.invalid.1"
    assert quarantined.read_text(encoding="utf-8") == "bad"


def test_resume_ignores_only_a_truncated_final_jsonl_line(tmp_path: Path) -> None:
    state = tmp_path / "state.jsonl"
    audit = MonthAudit(month="2021-01", status="audited")
    state.write_text(json.dumps(audit.__dict__) + "\n{\"month\":", encoding="utf-8")
    assert _read_latest_state(state)["2021-01"] == audit
