# Broker Compatibility Matrix

Kurama targets gold instruments across multiple brokers and both cent and standard accounts. Compatibility must be observed, not assumed.

| Broker | Server | Account type | Symbol | Digits | Contract size | Min lot | Lot step | Leverage | Status | Notes |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| Unverified | Unverified | cent | gold symbol | - | - | - | - | - | Not tested | Reserved for a future approved phase |
| Unverified | Unverified | standard | gold symbol | - | - | - | - | - | Not tested | Reserved for a future approved phase |

For every broker, capture the actual symbol name including prefix or suffix, tick size, tick value, volume limits, volume step, stop level, filling mode and account currency.

Kurama v0.1.0 preserves upstream symbol and lot handling. It does not yet claim automatic normalization across brokers or account types.
