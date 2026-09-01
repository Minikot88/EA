# Changelog

## Unreleased v0.2.0-dev.1 infrastructure

- Replaced the unavailable XS 2021-2025 requirement with an explicitly source-isolated Hybrid contract: Dukascopy Train/Validation and XS Calibration/OOS/Holdout.
- Added pinned monthly Dukascopy acquisition, streaming quote audits, resumable state and download-manifest hashes.
- Added closed-bar M5/M15/H1 feature extraction and counterfactual BUY/SELL/SKIP label policy.
- Added a virtual Original one-sided basket simulator that preserves first lot 0.01, grid recovery, lot normalization and the Original BUY/SELL MaxOrder asymmetry.
- Added immutable train/validation/OOS/holdout splits with 24-hour purge gaps and class-specific data gates.
- Added the locked three-branch Temporal CNN, deterministic seeds, weighted training, robust confidence selection, ONNX export and reproducibility hashes.
- Verified the ONNX architecture in MT5 with 0 compile errors, 0 warnings and matching Python/MQL5 probe probabilities.
- Recorded that model training and the `v0.2.0-dev.1` source/tag remain blocked by missing 2021-2025 broker real ticks.
- Did not change `src/Kurama.mq5`, its release snapshot, parameters or Approved-for-Use status.

## v0.1.0

- Created branch Kurama from upstream main commit 10c3daad5c6b66e6832c8d9206c937731ef12b8f.
- Renamed EA Susanoo Grid Recovery v2 to Kurama.
- Changed identity and version metadata only.
- Preserved all inputs, defaults and trading logic.
- Added versioned source, release, parameter, result, documentation and archive structure.
- Added no strategy changes, optimizations, broker normalization or risk guardrails.
