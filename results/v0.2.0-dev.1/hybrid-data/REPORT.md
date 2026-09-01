# Dukascopy Hybrid acquisition probe

The pinned daily JSON API output was independently compared with the older hourly BI5 source for `2024-01-02 00:00 UTC`.

- Downloader: `dukascopy-node@1.50.0`
- Quotes compared: 2,948
- Timestamp/Bid/Ask equality: exact for every quote
- BI5 XAUUSD price divisor: 1,000
- JSON CSV header: `timestamp,askPrice,bidPrice`

This validates the acquisition representation only. It does not satisfy the 60-month completeness, label, MT5 simulator parity, ONNX parity or trading-performance gates.

## Partial acquisition status

- January 2021: audited, 4,751,517 quotes.
- February 2021: audited, 5,243,959 quotes.
- March 2021: blocked by HTTP 429 on the public JSON API after safe-batch retries.
- Remaining: 58 of 60 months.

Raw files remain local and ignored. Training is still fail-closed.
