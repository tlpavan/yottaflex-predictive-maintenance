# Validation Summary

## 1. Baseline Dataset

The recorded full baseline run used seed `20261022` and generated:

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

Baseline data validation completed with **zero errors**.

## 2. Automated Tests

The latest recorded test run completed with:

```text
12 passed
```

Test modules recorded in the source manifest:

- `tests/test_master_data.py`
- `tests/test_scenario_injector.py`
- `tests/test_work_order_downtime.py`

## 3. Deliberate Exception Scenarios

All five recorded exception scenarios were detected:

| Scenario | Expected detection |
|---|---|
| Unknown sensor reference | Unknown sensor is reported. |
| Invalid sensor unit | Unit mismatch is reported. |
| Invalid sensor range | Out-of-range reading is reported. |
| Failure before the recorded symptom | Chronology anomaly is reported. |
| Maintenance completion before maintenance start | Chronology anomaly is reported. |

A telemetry-gap fixture was also checked separately. Two missing hourly intervals were identified as a gap; they were not converted into zero-valued telemetry. The fixture was marked `scenario_fixture_only=YES`.

## 4. Maintenance Integrity and Downtime

Recorded maintenance checks passed for the following areas:

- Unique work-order identifiers.
- One baseline work order per failure event.
- Valid machine, failure, technician, and part references.
- Machine consistency between failure and work order.
- Valid work-order/part relationships.
- Chronological timestamps.
- Repair-duration arithmetic.
- Downtime arithmetic.
- Three expected lifecycle transitions per work order.

The 150 downtime values were independently reconciled with zero mismatches. In this synthetic model:

- `repair_duration_hours = completed_at - started_at`
- `downtime_hours = completed_at - failure_at`

Downtime is an assumed synthetic estimate, not measured plant downtime.

## 5. Maintenance Lifecycle History

The baseline contains 450 maintenance status-history records for 150 work orders:

1. `NONE` → `OPENED`
2. `OPENED` → `IN_PROGRESS`
3. `IN_PROGRESS` → `COMPLETED`

The history is explicitly represented as event records. Broader plant and machine status histories are not claimed.

## 6. Starter-Scale Verification

The starter-scale test configuration used:

- 2 plants.
- 4 production lines.
- 20 machines.
- 100 sensors.
- 7 telemetry days.
- 100 failure events.

Recorded output included 16,800 telemetry records, 100 work orders, 300 lifecycle events, and 1,968 ground-truth records. The starter-scale validator reported zero errors.

## 7. Reproducibility

Two independent full-pipeline runs with the same seed were compared using row counts and SHA-256 checksums. All **24 CSV outputs** matched. See `docs/REPRODUCIBILITY_REPORT.md`.

The reproducibility comparison covered the pipeline CSV outputs; it did not include the JSON/SQLite/SQL export stage.

## 8. JSON and SQLite Export Checks

The export step generated JSON outputs for 12 relational datasets, a SQLite database, and a SQL seed file.

Recorded checks:

- JSON and SQLite row counts matched for all 12 relational datasets.
- SQLite `PRAGMA foreign_key_check` returned no violations.
- The SQL seed file was generated.

A replay of `seed.sql` into a fresh database was not recorded as completed and should not be claimed as verified.

## 9. Risk-Evaluation Checks

The historical evaluation produced 8,900 machine-day snapshots across the 89 evaluated UTC dates, with 149 positive outcomes. It used a 24-hour feature window and a subsequent 24-hour outcome horizon. The final telemetry day was excluded.

For the chronological holdout, 6,100 training snapshots covered 2026-07-01 through 2026-08-30, 2026-08-31 was excluded, and 2,700 test snapshots covered 2026-09-01 through 2026-09-27. The threshold of 55 was selected on the earlier training period.

The held-out test result at HIGH/CRITICAL threshold 55 was precision 23.68%, recall 20.00%, F1 21.69%, and false-positive rate 1.09%. See `docs/RISK_EVALUATION.md` for full details.

## 10. Known Limitations / Remaining Verification

- All generated operating data and failure outcomes are synthetic.
- Risk scores are heuristic and not calibrated failure probabilities.
- Held-out recall is limited.
- Downtime is estimated from synthetic timestamps.
- The SQL seed has not been replay-tested in a fresh database in the recorded evidence.
- Reproducibility checks cover 24 CSV outputs, not JSON/SQLite/SQL artifacts.
- Prompt-history completeness and the list of all AI tools used still require candidate confirmation.
