# Kurama ML data gate

Status: **Hybrid acquisition in progress — no model may be trained or tagged.**

- XSFintech reports symbol history from 2023-09-06 and local real ticks from 2026, so it cannot supply Train/Validation.
- Boss approved a source-isolated Hybrid contract on 2026-09-02.
- Dukascopy XAUUSD supplies Train 2021-2024 and Validation 2025.
- XSFintech XAUUSDc supplies Calibration Jan-Feb, Locked OOS Mar-Jun and Final Holdout Jul-Aug 2026.
- All 60 Dukascopy months require streaming audit and SHA-256 receipt before labels or training.

Training, model selection and `v0.2.0-dev.1` source/tag creation remain prohibited until the Hybrid gate is ready.

After data is supplied, the gate still requires MT5 parity fixtures for the virtual Original basket and 1,000 Python/ONNX/MQL5 probability comparisons at maximum absolute difference `1e-5`.
