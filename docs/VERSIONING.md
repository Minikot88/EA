# Versioning Policy

Kurama uses semantic versions in the form vMAJOR.MINOR.PATCH.

## When to increase a version

- MAJOR: incompatible behavior, parameter contract or migration change.
- MINOR: a new trading, safety, broker-compatibility or reporting capability.
- PATCH: a bug fix, narrowly scoped calculation change or metadata correction.

Any source-code change must create a new version. A version change includes the source metadata, release snapshot, changelog entry, commit and annotated Git tag.

## Parameter-only experiments

Changing a set file or tester configuration does not create a new EA version when source/Kurama.mq5 remains byte-identical. Store each experiment under params/vX.Y.Z and its evidence under results/vX.Y.Z. Use a unique test ID in both filenames and result records.

Recommended filename pattern:

Kurama_vX.Y.Z_BROKER_ACCOUNTTYPE_SYMBOL_TIMEFRAME_PROFILE.set

## Immutable releases

A release directory is immutable after its tag is created. Never move or retag v0.1.0. If an error is found, create the next semantic version and preserve the old evidence for comparison.

Git tags and version folders are the canonical Kurama version. The v0.1.0 baseline retains the upstream MQL property version 1.10 because MetaEditor rejects a zero-major Market version.

## Release checklist

1. Confirm the branch and clean candidate boundary.
2. Verify the source changes against the prior version.
3. Compile when MetaEditor is available and retain the log.
4. Run the version-appropriate tests and store their evidence.
5. Copy the exact source into releases/vX.Y.Z.
6. Record SHA-256 hashes.
7. Commit once and create an annotated tag pointing to that commit.
8. Publish or push only with separate explicit approval.
