# Kurama v0.2 Original AND Temporal CNN ML

## Runtime contract

- One EA, magic and basket; no second execution engine.
- Original inputs/defaults/grid/recovery/lot/TP/close remain unchanged.
- `OFF` is exact Original behavior.
- `MONITOR` runs Original and logs ML probabilities only.
- `ACTIVE` opens the first entry only when Original direction equals ML `BUY` or `SELL`; ML `SKIP`, disagreement, warm-up failure or inference failure blocks the entry.
- Inference runs once per newly closed M15 bar from closed M5/M15/H1 inputs.
- The ONNX model is embedded as an MQL5 resource; Python is never required at trading runtime.

## Model input and architecture

- M5: 96 bars x 8 features.
- M15: 96 bars x 8 features.
- H1: 48 bars x 8 features.
- Features: close log-return, open gap/ATR, high/ATR, low/ATR, body/ATR, range/ATR, tick-volume z-score and spread/ATR.
- Each branch: Conv1D(32,k=5), ReLU, MaxPool, Conv1D(64,k=3), ReLU, Global Average Pool.
- Concatenated branches feed Dense64, ReLU, Dropout0.20 and a BUY/SELL/SKIP softmax.

## Counterfactual labels

- At each candidate time, simulate Original basket Buy and Sell independently on real ticks.
- Success requires a profitable basket close within 24 hours and basket DD at or below 20%.
- If one side succeeds, use that side; if both succeed, choose the faster close.
- If close durations differ by no more than 10%, choose lower DD; if DD differs by no more than 1 percentage point, label SKIP.
- If neither succeeds, label SKIP.

## Locked time splits and gates

- Train 2021-2024 and Validation 2025 use Dukascopy XAUUSD Bid/Ask ticks only.
- XS Jan-Feb 2026 is Calibration only; Locked OOS is Mar-Jun 2026; Final Holdout is Jul-Aug 2026.
- Exness is external multi-broker stress only and cannot select the model.
- Purge 24 hours at every split boundary.
- Require at least 5,000 BUY, 5,000 SELL and 10,000 SKIP labels.
- Training remains prohibited until all 60 Dukascopy months, class counts and parity receipts pass.
- Final trading gates: 3-5% simple average per trading day, PF >= 1.20, DD <= 30%, no StopOut and a non-overlapping OOS pass.
- No automatic equity stop is added.

## Exact feature contract

For closed bar `t`, with previous closed bar `t-1` and ATR in price units:

1. `log(close[t] / close[t-1])`
2. `(open[t] - close[t-1]) / ATR[t]`
3. `(high[t] - open[t]) / ATR[t]`
4. `(low[t] - open[t]) / ATR[t]`
5. `(close[t] - open[t]) / ATR[t]`
6. `(high[t] - low[t]) / ATR[t]`
7. tick-volume z-score against the prior 20 closed bars, excluding bar `t`
8. spread in price units divided by `ATR[t]`

An unclosed bar is discarded before window selection. M5/M15 therefore require 116 closed bars and H1 requires 68 closed bars so every output row has the full 20-bar volume warm-up. Invalid/non-positive close or ATR blocks inference instead of filling fabricated values.

Dataset bar timestamps represent bar-close time, must be timezone-aware and cannot exceed the candidate timestamp. The candidate timestamp is the exact timestamp of its first forward tick, and the slice must extend through 24 hours unless both virtual baskets close earlier.

The 24-hour purge is edge-exclusive: samples exactly 24 hours before or after a split boundary are removed because their label horizon can touch the adjacent split.

## Virtual Original basket scope

The simulator models forced first entry, broker-triggered pending fills, five-second EA sleep, common position TP modification, trailing stops, recovery creation/repricing, lot-plus/multiply normalization, TP2/SL2, TP3/SL3, SecureProfit extreme-pair closes and orphan completion. It preserves the source's missing `MaxOrder` check on SELL recovery.

Broker gap fills, rejected stop modifications, commission, swap and exact position enumeration remain external parity items. Training stays prohibited until these are compared with MT5 receipts on supplied real ticks; an unverified simulator must not generate an accepted dataset.

## Implementation state

- Python, NumPy and Torch determinism, class gates, strict locked splits and dataset receipts are implemented under `ml/`.
- The fixed ONNX architecture has executed successfully in MT5 with all three input tensors and a BUY/SELL/SKIP output.
- The runtime probe used an untrained temporary model and is not a candidate.
- Product source integration, 1,000-sample parity, training, model selection and trading tests cannot begin until the data gate is ready.
- Public product training and ONNX export always read the committed gate path; callers cannot substitute another gate. A ready gate must prove full tick coverage, class counts, simulator parity and 1,000-sample ONNX parity with repository-contained receipt hashes.
- Gate readiness is bound to `XSFintech-REAL-2` / `XAUUSDc`, exact bar/tick ranges and the locked split table. Receipt JSON is parsed and cross-checked: the dataset binds broker, symbol, ranges, coverage and training counts; virtual parity binds required Original behaviors and zero-warning compile; ONNX parity binds dataset/model hashes, sample count and maximum difference.
