import hashlib
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "Kurama.mq5"
RELEASE = ROOT / "releases" / "v0.1.0" / "Kurama_v0.1.0.mq5"
EXPECTED_SHA256 = "E6E4D47A232451A0682000A30BAC8C13A51DD12FB77B0037458AB778AE74FCE1"


def _normalize_newlines(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _normalize_identity(text: str) -> str:
    text = re.sub(r"^//\|\s+[^|]+\.mq5\s+\|$", "//| PROGRAM.mq5 |", text, count=1, flags=re.MULTILINE)
    text = text.replace('#property description "Kurama Grid Recovery v0.1.0 baseline"\n', "")
    return text


def test_active_source_matches_immutable_release() -> None:
    source = SOURCE.read_bytes()
    release = RELEASE.read_bytes()
    assert source == release
    assert hashlib.sha256(source).hexdigest().upper() == EXPECTED_SHA256


def test_source_is_upstream_logic_with_identity_only_changes() -> None:
    candidate = _normalize_identity(SOURCE.read_text(encoding="utf-8"))
    upstream = subprocess.check_output(
        ["git", "show", "main:EA Susanoo Grid Recovery v2.mq5"], cwd=ROOT
    ).decode("utf-8")
    assert _normalize_newlines(candidate.encode("utf-8")) == _normalize_newlines(
        _normalize_identity(upstream).encode("utf-8")
    )


def test_original_contracts_are_preserved() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    for contract in (
        "input int      MaxOrder                = 99;",
        "input double   Lots                    = 0.01;",
        "input double   LotPlus                 = 0.01;",
        "input double   LotExponent             = 1.5;",
        "input double   MaxLot                  = 3.0;",
        "FirstEntrySignal(true)",
        "FirstEntrySignal(false)",
        "Trade.Buy(",
        "Trade.Sell(",
        "Trade.BuyStop(",
        "Trade.SellStop(",
    ):
        assert contract in source
    for forbidden in ("TargetEngine", "AdaptiveRecovery", "ProfitCycle", "RegimeProfitExit"):
        assert forbidden not in source
