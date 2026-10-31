# YottaFlex AI - Predictive Maintenance Data Engineering Pipeline

An end-to-end synthetic industrial data engineering solution that uses machine telemetry, operating context, and maintenance history to identify equipment with elevated failure risk.

The pipeline generates industrial datasets, validates relationships and data quality, injects synthetic pre-failure patterns, calculates explainable machine-risk scores, preserves maintenance history, evaluates historical decisions, and presents operational outputs through a Streamlit dashboard.

> **Data notice:** All operational records in this project are synthetic. The risk scores are heuristic indicators, not calibrated probabilities of equipment failure.

## 1. Key Capabilities

- Deterministic generation of industrial master data and timestamped telemetry.
- Synthetic failure events, corrective maintenance work orders, parts, and technician records.
- Pre-failure pattern injection with a separate ground-truth dataset.
- Validation of identifiers, relationships, units, ranges, chronology, and dataset consistency.
- Explicit maintenance downtime estimates and maintenance status-transition history.
- Explainable, rule-based machine risk scoring with reason codes and recommendations.
- Risk decision audit records.
- Deliberate exception fixtures and detection checks.
- Historical risk evaluation with a chronological holdout.
- CSV, JSON, SQLite, and SQL seed exports.
- Interactive Streamlit dashboard.

## 2. Technology Stack

- Python 3.10+
- Pandas
- Streamlit
- CSV, JSON, SQLite, and SQL
- Pytest

Install the dependencies listed in `requirements.txt`.

## 3. Baseline Dataset

| Entity / dataset | Records |
|---|---:|
| Plants | 3 |
| Production lines | 12 |
| Machines | 100 |
| Sensors | 500 |
| Operating shifts | 3 |
| Telemetry readings | 1,080,000 |
| Failure events | 150 |
| Maintenance work orders | 150 |
| Technicians | 20 |
| Parts | 10 |
| Work-order/part relationships | 240 |
| Maintenance status-history events | 450 |
| Ground-truth records | 2,850 |

Baseline configuration:

- Random seed: `20261022`
- Telemetry start: `2026-07-01T00:00:00+00:00`
- Duration: 90 days
- Sampling interval: 60 minutes
- Failure events: 150

The baseline contains 1.08 million telemetry records from 500 sensors at hourly intervals over 90 days.

## 4. Architecture and Pipeline

1. **Master data generation:** creates plants, production lines, machines, and sensors.
2. **Telemetry generation:** creates timestamped sensor readings with machine and operating context.
3. **Event generation:** creates failures, maintenance work orders, technicians, parts, work-order/part relationships, operating shifts, and maintenance status history.
4. **Scenario injection:** adds synthetic pre-failure patterns and creates a separate ground-truth dataset.
5. **Data validation:** checks identifiers, foreign-key relationships, timestamps, and dataset consistency.
6. **Exception generation:** creates deliberate anomaly fixtures and checks whether the validator detects them.
7. **Risk engine:** calculates machine-level rule-based risk scores from recent telemetry, maintenance history, and operating context.
8. **Risk evaluation:** compares historical risk decisions with subsequent synthetic failure outcomes.
9. **Data export:** publishes relational JSON, SQLite, and SQL seed outputs.
10. **Dashboard:** presents machine health, risk distribution, recommendations, audit history, and exception monitoring.

## 5. Project Structure

```text
yottaflex-predictive-maintenance/
├── config/
│   └── config.json
├── data/
│   ├── raw/
│   ├── processed/
│   ├── reports/
│   ├── exceptions/
│   └── exports/
├── docs/
│   ├── AI_USAGE.md
│   ├── AI_PROMPT_HISTORY.md
│   ├── DOCUMENTATION_CHECKLIST.md
│   ├── REPRODUCIBILITY_REPORT.md
│   ├── RISK_EVALUATION.md
│   ├── SOURCE_MANIFEST.md
│   ├── VALIDATION_SUMMARY.md
│   └── data_dictionary.md
├── src/
│   ├── __init__.py
│   ├── master_data.py
│   ├── telemetry_generator.py
│   ├── event_generator.py
│   ├── scenario_injector.py
│   ├── data_validator.py
│   ├── exception_generator.py
│   ├── risk_engine.py
│   ├── evaluate_risk.py
│   ├── export_data.py
│   └── dashboard.py
├── tests/
│   ├── test_master_data.py
│   ├── test_scenario_injector.py
│   └── test_work_order_downtime.py
├── .gitignore
├── requirements.txt
└── README.md
```

## 6. Installation

Run these commands in Windows PowerShell from the project root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If the virtual environment is not activated, use its interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 7. Configuration

Edit `config/config.json` to change the generation scale. The baseline configuration is:

```json
{
  "seed": 20261022,
  "plants": 3,
  "lines": 12,
  "machines": 100,
  "sensors": 500,
  "output_dir": "data/raw",
  "telemetry_days": 90,
  "telemetry_interval_minutes": 60,
  "telemetry_start": "2026-07-01T00:00:00+00:00",
  "failure_events": 150
}
```

The random seed controls deterministic generation. The event generator accepts 100 to 200 failure events. A starter-scale run was also verified using 20 machines, 100 sensors, seven telemetry days, and 100 failures.

## 8. Run the Pipeline

Run commands from the project root in the following order:

```powershell
python -m src.master_data
python -m src.telemetry_generator
python -m src.event_generator
python -m src.scenario_injector
python -m src.data_validator
python -m src.exception_generator
python -m src.risk_engine
python -m src.evaluate_risk
python -m src.export_data
```

Run automated tests:

```powershell
python -m pytest -q
```

Launch the dashboard:

```powershell
python -m streamlit run src/dashboard.py
```

The dashboard is available locally at `http://localhost:8501`.

Use `\.venv\Scripts\python.exe` in place of `python` if the virtual environment is not activated.

## 9. Generated Outputs

### Raw datasets — `data/raw/`

The generated CSV datasets include:

- `plants.csv`
- `production_lines.csv`
- `machines.csv`
- `sensors.csv`
- `operating_shifts.csv`
- `telemetry.csv`
- `telemetry_enriched.csv`
- `failure_events.csv`
- `ground_truth.csv`
- `maintenance_work_orders.csv`
- `maintenance_status_history.csv`
- `technicians.csv`
- `parts.csv`
- `work_order_parts.csv`

### Processed datasets — `data/processed/`

- `machine_risk_scores.csv` — machine-level scores, bands, scoring components, data-quality indicators, reasons, and recommendations.

### Reports — `data/reports/`

- `risk_audit_log.csv`
- `risk_evaluation_predictions.csv`
- `risk_evaluation_metrics.csv`

### Exception fixtures — `data/exceptions/`

Fixtures cover unknown sensors, invalid sensor units/ranges, invalid failure chronology, invalid maintenance chronology, and telemetry gaps. The generated exception report records detection outcomes.

### Relational exports — `data/exports/`

The exporter produces JSON files for 12 relational datasets, `yottaflex_seed.sqlite`, and `seed.sql`. High-volume telemetry remains in CSV format to avoid duplicating the large telemetry dataset in the relational exports.

## 10. Data Relationships and Maintenance History

Field definitions and dataset relationships are documented in `docs/data_dictionary.md`.

Principal relationships:

- Plant → ProductionLine: one-to-many.
- ProductionLine → Machine: one-to-many.
- Machine → Sensor: one-to-many.
- Sensor → TelemetryEvent: one-to-many.
- Machine → FailureEvent: one-to-many.
- FailureEvent → MaintenanceWorkOrder: one-to-one in the generated baseline.
- Technician → MaintenanceWorkOrder: one-to-many.
- MaintenanceWorkOrder → Part: many-to-many through `work_order_parts.csv`.

### Downtime definitions

Two separate time measurements are maintained:

- `repair_duration_hours` = `completed_at` − `started_at`.
- `downtime_hours` = `completed_at` − `failure_at`.

For this synthetic dataset, downtime is assumed to begin at failure occurrence and end at maintenance completion. It is a derived synthetic estimate, not a measurement from a real production monitoring system.

### Maintenance lifecycle history

`maintenance_status_history.csv` records three transitions for each baseline work order:

- `NONE` → `OPENED`
- `OPENED` → `IN_PROGRESS`
- `IN_PROGRESS` → `COMPLETED`

The 450 records preserve status changes as explicit events for the 150 baseline work orders.

## 11. Risk Scoring Method

The risk engine uses explainable, rule-based scoring. It considers:

- Recent 24-hour sensor telemetry.
- Sensor-specific thresholds and trends.
- Maintenance activity over the previous 30 days.
- Operating context and running percentage.

Risk bands:

| Risk band | Score |
|---|---:|
| LOW | Below 25 |
| MEDIUM | 25–54 |
| HIGH | 55–74 |
| CRITICAL | 75–100 |

The scoring algorithm records its version, input window, risk score, risk category, reasons, and recommendation in the audit output. Ground-truth labels are not used as risk-engine input features.

Risk scores are heuristic indicators, not calibrated probabilities of equipment failure.

## 12. Historical Risk Evaluation

The evaluation creates one machine decision snapshot per UTC day. It uses the previous 24 hours of telemetry and only maintenance information available by the decision timestamp. Future failure events are used only as evaluation outcomes. The final telemetry day is excluded because its future outcome window is unavailable.

A chronological holdout was used: 2026-07-01 through 2026-08-30 for threshold selection, 2026-08-31 excluded as a one-day gap, and 2026-09-01 through 2026-09-27 for testing. The HIGH/CRITICAL threshold of 55 was selected using the earlier period.

Held-out test results at threshold 55:

| Metric | Result |
|---|---:|
| Precision | 23.68% |
| Recall | 20.00% |
| F1-score | 21.69% |
| False-positive rate | 1.09% |
| True positives | 9 |
| False positives | 29 |
| True negatives | 2,626 |
| False negatives | 36 |

These results come from synthetic historical data and are not evidence of real industrial performance. The limited recall is an important limitation. Detailed methodology and full-period metrics are in `docs/RISK_EVALUATION.md`.

## 13. Validation and Reproducibility

Recorded verification results:

- Zero baseline data-validation errors.
- 12 automated tests passed.
- Five deliberate exception scenarios detected.
- Maintenance relationships and timestamps reconciled.
- All 150 downtime values independently reconciled.
- 450 maintenance lifecycle events generated and validated.
- Starter-scale generation verified.
- Two independent full-pipeline runs produced matching row counts and SHA-256 checksums across 24 CSV outputs.
- JSON and SQLite record counts matched for the 12 relational datasets; SQLite foreign-key integrity passed.

The SQL seed file was generated. A fresh-database replay of that SQL file is not included in the recorded verification results.

See `docs/VALIDATION_SUMMARY.md` and `docs/REPRODUCIBILITY_REPORT.md` for the supporting details.

## 14. Assumptions and Limitations

- All operational records are synthetic.
- The risk engine is rule-based, not a trained machine-learning model.
- Risk scores are not calibrated failure probabilities.
- Evaluation is based on synthetic failures and a defined 24-hour prediction horizon.
- Downtime is estimated from failure and maintenance-completion timestamps.
- The system has not been validated against real industrial plant data.
- Real deployment would require validation using actual sensor distributions, maintenance records, and failure outcomes.
- Explicit maintenance status history is preserved; broader plant and machine status histories are not claimed.
- The current held-out results show limited failure recall, so the score should be treated as a prioritisation aid, not a proven predictive-maintenance model.

## 15. AI Usage and Supporting Evidence

The use of AI, the work performed during development, and the verification activities are documented in:

- `docs/AI_USAGE.md`
- `docs/AI_PROMPT_HISTORY.md`

Supporting technical documents:

- `docs/SOURCE_MANIFEST.md`
- `docs/VALIDATION_SUMMARY.md`
- `docs/REPRODUCIBILITY_REPORT.md`
- `docs/RISK_EVALUATION.md`
- `docs/data_dictionary.md`

**Before submission:** complete the AI prompt history for every AI tool used. The currently assembled prompt record is partial and must not be represented as complete until the remaining historical prompts and any other AI tools are accounted for.

## 16. Documentation and Submission Readiness

Use `docs/DOCUMENTATION_CHECKLIST.md` to track remaining documentation checks. Git and GitHub preparation should begin only after the prompt history, local-file replacement, and documentation review have been completed.
