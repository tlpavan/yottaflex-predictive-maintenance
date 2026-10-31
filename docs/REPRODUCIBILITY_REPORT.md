# Reproducibility Report

## Objective

Check whether two independent pipeline runs using the same configuration and random seed produce identical CSV outputs.

## Configuration

- Random seed: `20261022`
- Baseline configuration: 3 plants, 12 production lines, 100 machines, 500 sensors.
- Telemetry period: 90 days.
- Telemetry interval: 60 minutes.
- Failure events: 150.

## Method

1. Execute the pipeline in one isolated project copy.
2. Execute the same pipeline in a second isolated project copy using the same configuration and seed.
3. Compare the generated CSV outputs by row count.
4. Compute SHA-256 checksums for each corresponding CSV output.
5. Compare the row counts and checksums between the two runs.

## Result

**PASS — all 24 compared CSV outputs matched.**

- CSV outputs compared: 24
- Row-count mismatches: 0
- SHA-256 checksum mismatches: 0

The comparison included high-volume telemetry CSV output and the generated raw, processed, and report CSV outputs included in the tested pipeline run.

## Scope Limitation

This recorded reproducibility test covered the CSV pipeline outputs. It did **not** compare the JSON exports, SQLite database, or SQL seed file produced by the separate export module. Those exports received separate record-count and SQLite foreign-key checks documented in `docs/VALIDATION_SUMMARY.md`.

## Conclusion

The two isolated pipeline runs produced identical CSV outputs for the same seed and configuration. This supports deterministic reproducibility for the compared CSV generation pipeline; it does not establish reproducibility of every export format or prove that synthetic values represent real industrial behaviour.
