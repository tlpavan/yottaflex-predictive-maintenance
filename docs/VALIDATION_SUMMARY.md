# Validation Summary

This document summarises the recorded baseline, extended-validator, automated-test, export, reproducibility, and risk-evaluation results. All operational data is synthetic.

## 1. Baseline Dataset

The full baseline run used seed `20261022` and generated:

| Dataset | Records |
|---|---:|
| Plants | 3 |
| Production lines | 12 |
| Machines | 100 |
| Sensors | 500 |
| Operating shifts | 3 |
| Telemetry | 1,080,000 |
| Failure events | 150 |
| Maintenance work orders | 150 |
| Technicians | 20 |
| Parts | 10 |
| Work-order/part relationships | 240 |
| Maintenance status-history events | 450 |
| Ground-truth records | 2,850 |

The original baseline data validator completed with **zero errors**.

## 2. Automated Tests

The latest local test run after adding extended-validator coverage completed with:

```text
21 passed
```

This comprises the 12 existing project tests and 9 tests in `tests/test_extended_validator.py`.

The extended-validator unit tests cover unknown sensors, invalid units, out-of-range readings, failure chronology, maintenance chronology, timestamp-derived gap inference, adjacent observations, ignoring a supplied `missing_intervals` count, and unaligned intervals.

## 3. Primary-Key and Foreign-Key Checks

The extended validator reads the table, primary-key, and foreign-key definitions from `src/export_data.py`.

It checks non-empty and unique configured primary keys for the 11 tables with primary keys in the export schema, including the composite key (`work_order_id`, `part_id`) in `work_order_parts`. It separately checks uniqueness of `ground_truth.telemetry_id`.

Configured foreign-key checks cover:

- Production lines -> plants.
- Machines -> production lines.
- Sensors -> machines.
- Failure events -> machines.
- Maintenance work orders -> failures, machines, and technicians.
- Work-order parts -> work orders and parts.
- Maintenance status history -> work orders and machines.
- Ground truth -> failures and machines.

Telemetry-to-sensor, telemetry-to-machine, sensor type, and unit consistency are checked separately during telemetry validation.

## 4. Domain Values and Derived Rules

The extended validator checks the domain values defined by the generator modules, including plant locations, machine types/status, sensor types and units, technician specialisations/status, part units/catalogue details, failure types/root causes/severity, work-order type/priority/status, maintenance status transitions, and ground-truth labels.

It also validates configured sensor ranges, shift definitions and timestamp-to-shift assignment, finite telemetry values, positive part quantities, linked part costs, work-order priority against failure severity, and the generated duration arithmetic.

These are the explicit domain rules encoded in the current generators and extended validator; this statement does not claim an independent validation rule for every conceivable business enum or future extension.

## 5. Failure, Maintenance, and Lifecycle Validation

Recorded checks include:

- Failure symptom start < failure timestamp <= detected timestamp.
- Exactly one generated baseline work order for each failure event.
- Work-order opening at or after the related failure timestamp.
- Work-order opening <= start < completion.
- Work-order machine and failure consistency.
- Work-order priority matching failure severity.
- `repair_duration_hours` reconciliation against `completed_at - started_at`.
- `downtime_hours` reconciliation against `completed_at - failure_at`.
- Positive work-order part quantities and part-cost agreement with the part catalogue.
- Exactly three maintenance status events per baseline work order, in the expected order and at the corresponding work-order timestamps.

The baseline has 450 lifecycle events for 150 work orders. All 150 downtime values were independently reconciled in the recorded baseline checks.

## 6. Per-Sensor Telemetry Schedule and Data Quality

The extended validator checks the generated `telemetry_enriched.csv` against the configured schedule for each sensor individually.

For the 90-day hourly baseline:

- Expected readings per sensor: 2,160.
- Expected total readings: 500 sensors x 2,160 = 1,080,000.
- The configured start and final expected timestamps are checked.
- Timestamps must include a timezone and align to the configured interval.
- Duplicate sensor/timestamp pairs are reported.
- Missing intervals and unexpected short or irregular intervals are reported.
- Sensor-to-machine, sensor-type, unit, value-range, operating-state, and shift-code consistency is checked.
- The telemetry ID is checked against the sensor ID and UTC timestamp format.

A missing interval is derived from consecutive observed timestamps. The validator does not replace a missing reading with zero. Zero remains a valid possible reading for some sensor types and operating states.

## 7. Deliberate Exception Scenarios

The exception generator creates five separate labelled fixtures without modifying the baseline datasets. The extended validator independently evaluates their contents using the applicable condition rules and writes `data/exceptions/validator_exception_report.csv`.

| Fixture | Validation rule |
|---|---|
| Unknown sensor | Sensor ID is absent from the sensor master data. |
| Invalid unit or range | Unit differs from the sensor definition or value is outside configured limits. |
| Failure before symptom | Failure chronology does not satisfy symptom start < failure <= detected. |
| Maintenance end before start | Completion timestamp is earlier than maintenance start. |
| Missing telemetry gap | The difference between consecutive observed timestamps implies one or more missing configured intervals. |

The latest local integration run reported **5/5 exception fixtures detected** by the extended validator. The independent report is `data/exceptions/validator_exception_report.csv`. The original generator also writes `exception_report.csv`; its `detected` field is not used as the extended validator's detection result.

## 8. Starter-Scale Verification

The previously recorded starter-scale configuration used:

- 2 plants.
- 4 production lines.
- 20 machines.
- 100 sensors.
- 7 telemetry days.
- 100 failure events.

Recorded output included 16,800 telemetry records, 100 work orders, 300 lifecycle events, and 1,968 ground-truth records. The starter-scale run was verified with the original validator. The extended validator's recorded full-dataset run is the 100-machine baseline described above.

## 9. Reproducibility

Two independent full-pipeline runs with the same seed were compared using row counts and SHA-256 checksums. All **24 CSV outputs** matched. See `docs/REPRODUCIBILITY_REPORT.md`.

The reproducibility comparison covered the pipeline CSV outputs; it did not include the JSON/SQLite/SQL export stage.

## 10. JSON and SQLite Export Checks

The export step generated JSON outputs for 12 relational datasets, a SQLite database, and a SQL seed file.

Recorded checks:

- JSON and SQLite row counts matched for all 12 relational datasets.
- SQLite `PRAGMA foreign_key_check` returned no violations.
- The SQL seed file was generated.

A replay of `seed.sql` into a fresh database was not recorded as completed and must not be claimed as verified.

## 11. Risk-Evaluation Checks

The historical evaluation produced 8,900 machine-day snapshots across the 89 evaluated UTC dates, with 149 positive outcomes. It used a 24-hour feature window and a subsequent 24-hour outcome horizon. The final telemetry day was excluded.

For the chronological holdout, 6,100 training snapshots covered 2026-07-01 through 2026-08-30, 2026-08-31 was excluded, and 2,700 test snapshots covered 2026-09-01 through 2026-09-27. The threshold of 55 was selected on the earlier training period.

The held-out test result at HIGH/CRITICAL threshold 55 was precision 23.68%, recall 20.00%, F1 21.69%, and false-positive rate 1.09%. See `docs/RISK_EVALUATION.md` for full details.

## 12. Known Limitations / Remaining Verification

- All generated operating data and failure outcomes are synthetic.
- Risk scores are heuristic and not calibrated failure probabilities.
- Held-out recall is limited.
- Downtime is estimated from synthetic timestamps.
- Master data is generated as a static baseline snapshot; effective-from/effective-to master-data history is not implemented.
- Broader plant, line, and machine lifecycle event streams are not implemented; explicit event history is provided for maintenance work orders.
- The SQL seed has not been replay-tested in a fresh database in the recorded evidence.
- Reproducibility checks cover 24 CSV outputs, not JSON/SQLite/SQL artifacts.
