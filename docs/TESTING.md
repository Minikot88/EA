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
