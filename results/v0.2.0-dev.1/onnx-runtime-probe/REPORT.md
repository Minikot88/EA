# Temporary ONNX runtime probe

The locked three-input Temporal CNN architecture compiled with **0 errors and 0 warnings** and executed successfully in the XSFintech MT5 Strategy Tester.

- Inputs: M5 `1x96x8`, M15 `1x96x8`, H1 `1x48x8`
- Output: BUY/SELL/SKIP `1x3`
- Python: `0.315484703, 0.337257236, 0.347258121`
- MQL5: `0.315484703, 0.337257236, 0.347258121`

This used an untrained, seeded model stored only under the ignored `ml/runs/` area. It is not a candidate model and is not committed. The required 1,000-sample production parity test remains blocked by the historical-data gate.
