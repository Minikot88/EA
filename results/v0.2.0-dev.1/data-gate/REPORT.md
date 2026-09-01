# Kurama ML data gate

Status: **Blocked — no model may be trained or tagged.**

- Required training history starts 2021-01-01.
- XSFintech reports available symbol history from 2023-09-06.
- Local real-tick files exist only for 2026-01 through 2026-09.
- A one-day 2021 real-tick Strategy Tester probe returned `no history data` and created no `202101.tkc` file.
- Other locally configured brokers contain no older XAU real-tick files.

The ML pipeline may be implemented and tested with synthetic fixtures, but training, model selection and `v0.2.0-dev.1` source/tag creation remain prohibited until the required real ticks are supplied.

After data is supplied, the gate still requires MT5 parity fixtures for the virtual Original basket and 1,000 Python/ONNX/MQL5 probability comparisons at maximum absolute difference `1e-5`.
