# Kurama Hybrid data contract

## Source isolation

- Dukascopy `XAUUSD` Bid/Ask ticks are used only for Train 2021-2024 and Validation 2025.
- XSFintech `XAUUSDc` is used only for Calibration Jan-Feb 2026, Locked OOS Mar-Jun 2026 and Final Holdout Jul-Aug 2026.
- Exness data is external stress evidence only and cannot select a model or threshold.
- Every source boundary and time split has an inclusive 24-hour purge edge.

The model must be described as **trained on Dukascopy and validated on XSFintech**. It must never be described as trained on XSFintech.

## Acquisition

The pinned acquisition path is `dukascopy-node@1.50.0` installed from the committed npm lock with install scripts disabled. It downloads one UTC month per file through Dukascopy's daily JSON API. Each monthly file is streamed through checks for:

- exact `timestamp,askPrice,bidPrice` schema;
- UTC millisecond timestamps within the requested month;
- strict chronological order and uniqueness;
- finite positive Bid/Ask with `Ask >= Bid`;
- SHA-256, size, quote count, first/last timestamp and spread range.

Raw files, staging data and partial state live under `ml/data/raw/` and are ignored by Git. A completed 60-month manifest is the only downloadable-data receipt eligible for commit.

The older hourly BI5 endpoint is retained only as an independent decoder/reference path. A 2024-01-02 probe matched all 2,948 quotes in the first UTC hour exactly between BI5 and the pinned JSON-API CSV.

## Domain calibration

The Original basket uses XS symbol/lot/tick specifications. Any Dukascopy-to-XS spread transformation may be fitted only on XS Jan-Feb 2026. March-August 2026 stays locked and cannot influence features, labels, confidence thresholds or model selection.

If XS Locked OOS fails, the candidate is rejected. The gates must not be weakened to compensate for source-domain differences.
