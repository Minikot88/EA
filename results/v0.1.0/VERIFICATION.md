# Kurama v0.1.0 Verification

Candidate ID: kurama-v0.1.0-candidate-1

Base: origin/main at 10c3daad5c6b66e6832c8d9206c937731ef12b8f

## Verified evidence

- Clean-history reboot verification: 2026-09-01.

- Full normalized source comparison: 1,428 of 1,428 upstream lines matched after reversing only the Kurama filename header and description metadata.
- Normalized upstream SHA-256: 3D8BE5F3FE27B7914B04EA10AD17C46594D67846EE37B91F218F7BF962611EBC.
- Normalized candidate SHA-256: 3D8BE5F3FE27B7914B04EA10AD17C46594D67846EE37B91F218F7BF962611EBC.
- Active source and immutable release snapshot are byte-identical.
- Release SHA-256: E6E4D47A232451A0682000A30BAC8C13A51DD12FB77B0037458AB778AE74FCE1.
- MetaEditor compile: 0 errors and 0 warnings; see compile-v0.1.0.txt.
- Reboot EX5 SHA-256: B1B7FE6457DBD5C8A5EB36A390CD463D1F2813B15EFB4C8189DEE7AAF83CFC49.
- Fresh executable baseline tests: 3 passed.
- No Susanoo identity remains in active or release source.
- Boss explicitly approved removal of 109 unrelated upstream files from branch Kurama.
- Removed upstream set: 43 MQ5 files, 46 EX5 files and 20 supporting files; all remain recoverable from main.

## Not claimed

- No parameter optimization or strategy backtest was performed.
- No live trading, cent-account, standard-account or multi-broker compatibility was validated.
- No strategy, risk guardrail or broker-normalization behavior was added.
