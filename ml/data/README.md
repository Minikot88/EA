# ML data

Raw ticks and derived datasets are local-only and ignored by Git.

Committed evidence is limited to manifests, hashes, schemas and data-gate receipts. Training is forbidden until the Hybrid gate in `DATA_GATE.json` reports `ready` and all receipt bodies/hashes cross-check.

The raw acquisition root is `ml/data/raw/dukascopy_node/XAUUSD/`. It contains one audited UTC CSV per month for 2021-2025 plus ignored resume state. Do not manually edit or combine these files.
