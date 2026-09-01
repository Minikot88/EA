# Testing and Result Standard

Every result must identify the exact source version and parameter set so comparisons remain reproducible.

## Required result fields

- EA version and Git tag
- unique test ID and test date in UTC
- broker and server
- account type: cent, standard or another explicit type
- symbol and timeframe
- test date range
- initial deposit, deposit currency and leverage
- tester model and spread mode or value
- parameter file
- net profit and profit factor
- maximum drawdown in money and percent
- total trades
- notes and known limitations

Use results/vX.Y.Z/result-template.csv as the canonical column order.

## Evidence naming

Use the same test ID for the set file, tester report and result row. Recommended result prefix:

Kurama_vX.Y.Z_BROKER_ACCOUNTTYPE_SYMBOL_TIMEFRAME_TESTID

## Baseline comparison

Before accepting a later code version, run the same data window and compatible parameter set against the prior release. Report profit, profit factor, drawdown and total trades side by side. Do not combine results from different source versions in one unlabeled aggregate.

## v0.1.0 limitation

This release is a rename-only code baseline. No optimization, multi-broker qualification or risk-guardrail validation is claimed. These tests begin only after the boss authorizes the next development phase.

## v0.2.0-dev.1 ML gates

- Training data must cover the locked 2021-2026 ranges using real ticks, with a 24-hour purge at every boundary.
- Exact 24-hour purge edges are excluded, not assigned to either adjacent split.
- The virtual Original simulator must first match MT5 fixtures for pending fills, dynamic TP, trailing, money/percent closes and SecureProfit behavior.
- The training split must contain at least 5,000 BUY, 5,000 SELL and 10,000 SKIP labels.
- Python, ONNX Runtime and MQL5 probabilities must match for at least 1,000 samples with maximum absolute difference at most `1e-5`.
- OFF and MONITOR must match v0.1.0 entries, recovery, closes, profit, trades and deals.
- ACTIVE must pass every frozen validation window, then March 2026 continuously, then untouched July 2026.
- Acceptance requires PF at least 1.20, DD at most 30%, no StopOut, and simple average 3-5% per trading day across both continuous months.
- Results above 5% per day require leakage, fill and friction audit and are not automatically approved.
