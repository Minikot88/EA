# Kurama

Kurama is a versioned MetaTrader 5 Expert Advisor project derived from EA Susanoo Grid Recovery v2.

## Current channel

- Latest development: `v0.1.0` Original Kurama baseline
- Approved for Use: none
- Next authorized development: `v0.2.0-dev.1` Original AND Temporal CNN ML Quant

## Baseline

- Version and tag: v0.1.0
- MQL property version: 1.10 inherited from the upstream baseline
- Upstream repository: Minikot88/EA
- Upstream base commit: 10c3daad5c6b66e6832c8d9206c937731ef12b8f
- Development branch: Kurama
- Scope: identity and repository organization only

The v0.1.0 baseline preserves the original inputs, defaults, calculations, grid and recovery flow. It has not yet been optimized or qualified for live trading across brokers.

## Layout

- src contains the active EA source.
- releases contains immutable snapshots grouped by version.
- params contains parameter sets grouped by EA version.
- results contains test evidence grouped by EA version.
- docs contains versioning, testing and broker-compatibility rules.
- archive holds confirmed legacy artifacts when Git history alone is insufficient.

## Development rule

Every source-code change receives a new semantic version, commit and tag. Parameter-only experiments remain under the current version and never modify the source. The boss authorized `v0.2.0-dev.1` ML Quant development; no version is approved for live use.
