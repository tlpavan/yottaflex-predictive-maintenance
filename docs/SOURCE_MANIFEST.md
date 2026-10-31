# Source Manifest

This manifest describes the implementation modules and supporting files present in the project as recorded during the final documentation review.

## Configuration

| Path | Responsibility |
|---|---|
| `config/config.json` | Generation seed, entity counts, telemetry period/interval, output directory, and failure-event count. |
| `requirements.txt` | Python package dependencies for the project. |

## Application Source

| Path | Responsibility |
|---|---|
| `src/master_data.py` | Generates plant, production-line, machine, sensor, shift, technician, and part master data. |
| `src/telemetry_generator.py` | Generates timestamped synthetic sensor telemetry. |
| `src/event_generator.py` | Generates failure events, maintenance work orders, work-order/part records, and maintenance lifecycle history. |
| `src/scenario_injector.py` | Injects synthetic pre-failure patterns and creates a separate ground-truth dataset. |
| `src/data_validator.py` | Validates dataset identifiers, relationships, timestamps, units/ranges, and consistency rules. |
| `src/exception_generator.py` | Creates deliberate invalid-data and telemetry-gap fixtures and records detection results. |
| `src/risk_engine.py` | Calculates explainable rule-based machine risk scores and audit records. |
| `src/evaluate_risk.py` | Builds historical decision snapshots and evaluates them against subsequent synthetic failure outcomes. |
| `src/export_data.py` | Exports 12 relational datasets to JSON, SQLite, and SQL seed formats. |
| `src/dashboard.py` | Presents machine health, risk scores, recommendations, audit information, and exceptions in Streamlit. |
| `src/__init__.py` | Marks `src` as a Python package for module execution. |

## Automated Tests

| Path | Coverage area |
|---|---|
| `tests/test_master_data.py` | Master-data generation checks. |
| `tests/test_scenario_injector.py` | Scenario-injection and ground-truth checks. |
| `tests/test_work_order_downtime.py` | Work-order downtime and timestamp calculations. |

The recorded latest test result was **12 passed**. The test count is a run result, not a count of test files.

## Documentation

| Path | Purpose |
|---|---|
| `README.md` | Installation, configuration, pipeline execution, outputs, design, limitations, and verification summary. |
| `docs/data_dictionary.md` | Dataset definitions, identifiers, relationships, and derived-field notes. |
| `docs/AI_USAGE.md` | AI-use disclosure and candidate review/validation activities. |
| `docs/AI_PROMPT_HISTORY.md` | Reconstructed record of ChatGPT use, with representative project questions and original messages where available. |
| `docs/VALIDATION_SUMMARY.md` | Baseline, exception, maintenance, test, and export verification. |
| `docs/REPRODUCIBILITY_REPORT.md` | Independent-run row-count and SHA-256 comparison results. |
| `docs/RISK_EVALUATION.md` | Historical evaluation methodology and metrics. |
| `docs/DOCUMENTATION_CHECKLIST.md` | Outstanding documentation and pre-Git checklist. |

## Generated Data and Outputs

- `data/raw/`: synthetic source CSV datasets, including telemetry and relational records.
- `data/processed/`: machine-level risk-score output.
- `data/reports/`: risk audit and historical evaluation outputs.
- `data/exceptions/`: deliberate anomaly fixtures and exception report.
- `data/exports/`: JSON relational exports, SQLite database, and SQL seed file.

## Repository Cleanup

Legacy empty placeholder modules and misleading placeholder files were removed during project cleanup. They are not part of the implemented source manifest and should not be listed as functional modules.

## Manifest Limitations

This manifest reflects the module set and test files recorded during the documentation review. Before publishing, compare it once against the actual local repository tree and update any path that has changed.
