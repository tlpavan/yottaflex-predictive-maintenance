# Data Dictionary and Relationship Guide

This document describes the generated CSV entities, their fields, logical data types, keys, relationships, domain values, and principal validation rules. CSV readers expose values as strings; the logical types below describe how the values are interpreted by the application. All records are synthetic.

## 1. Type and Requirement Conventions

- **Text / ID / enum:** string values.
- **Integer:** whole-number value.
- **Decimal:** numeric value that may contain a fractional part.
- **Timestamp:** ISO-8601 date-time string with an explicit timezone (UTC in the generated baseline unless otherwise stated).
- **Time:** `HH:MM` time-of-day value.
- **Required:** populated in the generated baseline. The current generators do not define optional columns in these records.
- A relationship may be optional even when every column in a related row is required. For example, a work order may have no replacement-part rows.

The SQLite exporter maps `ground_truth_label` and `quantity_used` to `INTEGER`; `min_value`, `max_value`, `unit_cost`, `repair_duration_hours`, and `downtime_hours` to `REAL`; and other exported relational columns to `TEXT`. Telemetry is retained in CSV rather than included in the 12 relational JSON/SQLite tables.

## 2. Master Data Entities

### 2.1 Plant - `plants.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `plant_id` | Text / ID | Yes | Primary key | Deterministic ID such as `PLT-001`; unique and non-empty. |
| `plant_name` | Text | Yes | - | Generated plant name, e.g. `Plant 1`. |
| `location` | Text / enum | Yes | - | `Hyderabad`, `Pune`, `Chennai`, or `Bengaluru`. |

Baseline: 3 plants.

### 2.2 Production line - `production_lines.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `line_id` | Text / ID | Yes | Primary key | Includes the parent plant ID; unique and non-empty. |
| `plant_id` | Text / ID | Yes | FK -> `plants.plant_id` | Must reference an existing plant. |
| `line_name` | Text | Yes | - | Generated production-line name. |

Baseline: 12 production lines. Each line belongs to one plant.

### 2.3 Machine - `machines.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `machine_id` | Text / ID | Yes | Primary key | Includes the parent line ID; unique and non-empty. |
| `line_id` | Text / ID | Yes | FK -> `production_lines.line_id` | Must reference an existing line. |
| `machine_type` | Text / enum | Yes | - | `PUMP`, `MOTOR`, `COMPRESSOR`, or `CONVEYOR`. |
| `machine_status` | Text / enum | Yes | - | Generated baseline value: `ACTIVE`. |

Baseline: 100 machines. Each machine belongs to one production line.

### 2.4 Sensor - `sensors.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `sensor_id` | Text / ID | Yes | Primary key | Includes machine ID, sensor type, and sequence; unique and non-empty. |
| `machine_id` | Text / ID | Yes | FK -> `machines.machine_id` | Must reference an existing machine. |
| `sensor_type` | Text / enum | Yes | - | `TEMP`, `VIBRATION`, `CURRENT`, `PRESSURE`, or `SPEED`. |
| `unit` | Text / enum | Yes | - | Must match sensor type: `TEMP` -> `C`; `VIBRATION` -> `mm/s`; `CURRENT` -> `A`; `PRESSURE` -> `bar`; `SPEED` -> `rpm`. |
| `min_value` | Decimal | Yes | - | Finite numeric lower limit; must be less than `max_value`. |
| `max_value` | Decimal | Yes | - | Finite numeric upper limit; must be greater than `min_value`. |

Generated sensor limits: TEMP `20-120 C`; VIBRATION `0-20 mm/s`; CURRENT `0-100 A`; PRESSURE `0-20 bar`; SPEED `0-5000 rpm`. These are synthetic generator limits, not manufacturer specifications. Baseline: 500 sensors.

### 2.5 Operating shift - `operating_shifts.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `shift_code` | Text / ID | Yes | Primary key | `A`, `B`, or `C`. |
| `shift_name` | Text | Yes | - | `Morning Shift`, `Evening Shift`, or `Night Shift` for the corresponding code. |
| `start_time` | Time | Yes | - | A=`06:00`; B=`14:00`; C=`22:00`. |
| `end_time` | Time | Yes | - | A=`14:00`; B=`22:00`; C=`06:00`. |
| `timezone` | Text | Yes | - | `UTC`. |

Baseline: 3 shifts. Each telemetry row is assigned one shift code according to its UTC timestamp.

### 2.6 Technician - `technicians.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `technician_id` | Text / ID | Yes | Primary key | Unique identifier such as `TECH-001`. |
| `technician_name` | Text | Yes | - | Generated technician name. |
| `specialization` | Text / enum | Yes | - | `MECHANICAL`, `ELECTRICAL`, `INSTRUMENTATION`, or `GENERAL_MAINTENANCE`. |
| `availability_status` | Text / enum | Yes | - | Generated baseline value: `AVAILABLE`. |

Baseline: 20 technicians.

### 2.7 Part - `parts.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `part_id` | Text / ID | Yes | Primary key | Unique part catalogue ID. |
| `part_name` | Text | Yes | - | Name from the generated part catalogue. |
| `unit_cost` | Decimal | Yes | - | Positive finite cost in the synthetic catalogue's currency units. |
| `unit` | Text / enum | Yes | - | `EACH`. |

Baseline: 10 catalogue parts. Linked work-order part costs are checked against the catalogue cost.

## 3. Telemetry and Outcome Entities

### 3.1 Telemetry event - `telemetry.csv` and `telemetry_enriched.csv`

The enriched file preserves the telemetry fields and is used by the extended validator and risk workflow.

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `telemetry_id` | Text / ID | Yes | Deterministic unique identifier | `TEL-<sensor-id>-<YYYYMMDDTHHMM>`; timestamp component is UTC. |
| `sensor_id` | Text / ID | Yes | FK-like reference -> `sensors.sensor_id` | Must reference a known sensor. |
| `machine_id` | Text / ID | Yes | FK-like reference -> `machines.machine_id` | Must match the machine assigned to the sensor. |
| `timestamp` | Timestamp | Yes | Part of the sensor/timestamp uniqueness check | Timezone-aware; aligned to configured sampling interval. |
| `sensor_type` | Text / enum | Yes | - | Must match the sensor master record. |
| `value` | Decimal | Yes | - | Finite numeric reading within the sensor's configured limits. |
| `unit` | Text / enum | Yes | - | Must match the sensor master record. |
| `operating_state` | Text / enum | Yes | - | `RUNNING`, `IDLE`, `STOPPED`, or `MAINTENANCE`. |
| `shift_code` | Text / ID | Yes | Reference -> `operating_shifts.shift_code` | `A`, `B`, or `C`; must agree with the UTC timestamp. |

Baseline: 1,080,000 readings across 500 sensors for 90 days at 60-minute intervals (2,160 readings per sensor). The validator checks each sensor's count, start/end timestamps, interval alignment, duplicates, and missing or irregular intervals. A missing interval is not replaced with a zero reading. Zero can be a valid synthetic reading for some sensor types and operating states.

### 3.2 Failure event - `failure_events.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `failure_id` | Text / ID | Yes | Primary key | Unique ID such as `FAIL-000001`. |
| `machine_id` | Text / ID | Yes | FK -> `machines.machine_id` | Must reference an existing machine. |
| `failure_type` | Text / enum | Yes | - | `OVERHEATING`, `EXCESSIVE_VIBRATION`, `BEARING_FAILURE`, `PRESSURE_DROP`, or `MOTOR_FAILURE`. |
| `root_cause` | Text / enum | Yes | - | `BEARING_WEAR`, `INSUFFICIENT_LUBRICATION`, `COOLING_SYSTEM_ISSUE`, `MECHANICAL_IMBALANCE`, or `ELECTRICAL_FAULT`. |
| `severity` | Text / enum | Yes | - | `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`. |
| `symptom_start_at` | Timestamp | Yes | - | Timezone-aware; must be earlier than `failure_at`. |
| `failure_at` | Timestamp | Yes | - | Timezone-aware; must be later than symptom start and no later than `detected_at`. |
| `detected_at` | Timestamp | Yes | - | Timezone-aware; must be at or after `failure_at` in the generated baseline. |
| `ground_truth_label` | Integer | Yes | - | Generated failure event label: `1`. Ground-truth outcomes are kept separate from telemetry input features. |

Baseline: 150 failure events.

### 3.3 Maintenance work order - `maintenance_work_orders.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `work_order_id` | Text / ID | Yes | Primary key | ID such as `WO-2026-000001`. |
| `failure_id` | Text / ID | Yes | FK -> `failure_events.failure_id` | One generated work order per failure in the baseline. |
| `machine_id` | Text / ID | Yes | FK -> `machines.machine_id` | Must match the machine on the referenced failure. |
| `technician_id` | Text / ID | Yes | FK -> `technicians.technician_id` | Must reference an existing technician. |
| `maintenance_type` | Text / enum | Yes | - | Generated baseline value: `CORRECTIVE`. |
| `priority` | Text / enum | Yes | - | Must match the referenced failure severity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). |
| `opened_at` | Timestamp | Yes | - | At or after the failure timestamp in the generated baseline. |
| `started_at` | Timestamp | Yes | - | At or after `opened_at`. |
| `completed_at` | Timestamp | Yes | - | Later than `started_at`. |
| `work_order_status` | Text / enum | Yes | - | Generated baseline value: `COMPLETED`. |
| `repair_duration_hours` | Decimal | Yes | - | Must equal `completed_at - started_at` in hours. |
| `downtime_hours` | Decimal | Yes | - | Must equal `completed_at - failure_at` in hours under the project's synthetic downtime assumption. |

Baseline: 150 work orders.

### 3.4 Work-order/part bridge - `work_order_parts.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `work_order_id` | Text / ID | Yes | Composite primary key part; FK -> `maintenance_work_orders.work_order_id` | Must reference an existing work order. |
| `part_id` | Text / ID | Yes | Composite primary key part; FK -> `parts.part_id` | Must reference an existing part. |
| `quantity_used` | Integer | Yes | - | Positive whole number. |
| `unit_cost` | Decimal | Yes | - | Finite non-negative value; must match the catalogue unit cost. |

The composite primary key is (`work_order_id`, `part_id`). The relationship between work orders and parts is many-to-many through this bridge. A work order may have no part rows; when parts are selected, the generator creates one or more bridge rows. Baseline: 240 bridge records.

### 3.5 Maintenance status history - `maintenance_status_history.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `status_event_id` | Text / ID | Yes | Primary key | Unique ID such as `WOST-000001`. |
| `work_order_id` | Text / ID | Yes | FK -> `maintenance_work_orders.work_order_id` | Must reference an existing work order. |
| `machine_id` | Text / ID | Yes | FK -> `machines.machine_id` | Must match the machine on the referenced work order. |
| `previous_status` | Text / enum | Yes | - | `NONE`, `OPENED`, or `IN_PROGRESS` in the generated transitions. |
| `new_status` | Text / enum | Yes | - | `OPENED`, `IN_PROGRESS`, or `COMPLETED` in the generated transitions. |
| `event_timestamp` | Timestamp | Yes | - | Timezone-aware and equal to the corresponding work-order lifecycle timestamp. |

Exactly three ordered transitions are expected per baseline work order: `NONE -> OPENED`, `OPENED -> IN_PROGRESS`, and `IN_PROGRESS -> COMPLETED`. Baseline: 450 status events for 150 work orders.

### 3.6 Ground truth - `ground_truth.csv`

| Field | Logical type | Required | Key / reference | Allowed values, unit, or validation |
|---|---|---|---|---|
| `telemetry_id` | Text / ID | Yes | Unique within ground truth; joins to `telemetry_enriched.telemetry_id` | Must identify one telemetry reading; duplicate IDs are rejected. |
| `failure_id` | Text / ID | Yes | FK -> `failure_events.failure_id` | Must reference an existing failure. |
| `machine_id` | Text / ID | Yes | FK -> `machines.machine_id` | Must match the telemetry and failure machine. |
| `failure_type` | Text / enum | Yes | - | Must match the referenced failure type. |
| `ground_truth_label` | Integer | Yes | - | `1` for labelled pre-failure observations. |
| `symptom_start_at` | Timestamp | Yes | - | Must match the referenced failure event. |
| `failure_at` | Timestamp | Yes | - | Must match the referenced failure event. |

The export schema does not assign a SQL primary key to `ground_truth`; the extended validator separately enforces uniqueness of `telemetry_id`. A ground-truth record refers to a telemetry reading in the pre-failure window (`symptom_start_at <= timestamp < failure_at`). Baseline: 2,850 records. Ground-truth labels are not used as risk-engine input features.

## 4. Identifier Patterns

Examples from the implemented generators:

| Entity | Pattern / example |
|---|---|
| Plant | `PLT-001` |
| Production line | `LINE-PLT-001-001` |
| Machine | `MCH-LINE-PLT-001-001-001` |
| Sensor | `SNS-<machine-id>-TEMP-01` |
| Telemetry | `TEL-<sensor-id>-20260701T0000` |
| Failure | `FAIL-000001` |
| Work order | `WO-2026-000001` |
| Technician | `TECH-001` |
| Status event | `WOST-000001` |

IDs are generated deterministically from the configured seed and sequence logic. IDs are not intended to be reassigned after records are created.

## 5. Primary Keys and Foreign Keys

The relational export schema defines these primary keys:

| Table | Primary key |
|---|---|
| `plants` | `plant_id` |
| `production_lines` | `line_id` |
| `machines` | `machine_id` |
| `sensors` | `sensor_id` |
| `operating_shifts` | `shift_code` |
| `technicians` | `technician_id` |
| `parts` | `part_id` |
| `failure_events` | `failure_id` |
| `maintenance_work_orders` | `work_order_id` |
| `work_order_parts` | (`work_order_id`, `part_id`) |
| `maintenance_status_history` | `status_event_id` |

The validator also checks `ground_truth.telemetry_id` uniqueness, although `ground_truth` has no SQL primary key in the export definition.

Configured foreign keys:

| Child table / field | Parent table / field |
|---|---|
| `production_lines.plant_id` | `plants.plant_id` |
| `machines.line_id` | `production_lines.line_id` |
| `sensors.machine_id` | `machines.machine_id` |
| `failure_events.machine_id` | `machines.machine_id` |
| `maintenance_work_orders.failure_id` | `failure_events.failure_id` |
| `maintenance_work_orders.machine_id` | `machines.machine_id` |
| `maintenance_work_orders.technician_id` | `technicians.technician_id` |
| `work_order_parts.work_order_id` | `maintenance_work_orders.work_order_id` |
| `work_order_parts.part_id` | `parts.part_id` |
| `maintenance_status_history.work_order_id` | `maintenance_work_orders.work_order_id` |
| `maintenance_status_history.machine_id` | `machines.machine_id` |
| `ground_truth.failure_id` | `failure_events.failure_id` |
| `ground_truth.machine_id` | `machines.machine_id` |

Telemetry and ground-truth linkage is validated separately because the high-volume telemetry dataset is kept in CSV rather than included in the relational SQLite/JSON export tables.

## 6. Relationship Cardinality and Optionality

| Relationship | Cardinality | Optionality / rule |
|---|---|---|
| Plant -> ProductionLine | 1:N | Every generated line has one parent plant. |
| ProductionLine -> Machine | 1:N | Every generated machine has one parent line. |
| Machine -> Sensor | 1:N | Every generated sensor has one parent machine. |
| Sensor -> TelemetryEvent | 1:N | Each sensor produces many scheduled readings. |
| OperatingShift -> TelemetryEvent | 1:N | Each telemetry row has one shift code; a shift is referenced by many rows. |
| Machine -> FailureEvent | 1:N | A machine may have multiple synthetic failure events. |
| FailureEvent -> MaintenanceWorkOrder | 1:1 in generated baseline | The extended validator expects exactly one work order for each baseline failure. |
| Technician -> MaintenanceWorkOrder | 1:N | Each work order has one assigned technician; a technician may receive many work orders. |
| MaintenanceWorkOrder -> Part | N:M | Implemented through `work_order_parts`; a work order may have zero linked parts. |
| MaintenanceWorkOrder -> MaintenanceStatusHistory | 1:N | Exactly three lifecycle events are generated per baseline work order. |
| FailureEvent -> GroundTruth | 1:N | A failure may label multiple pre-failure telemetry readings. |
| TelemetryEvent -> GroundTruth | 1:0..1 | A telemetry reading may have no ground-truth row or one matching labelled row. |

## 7. Effective Dates and Lifecycle States

The plant, production-line, machine, sensor, technician, part, and shift records are generated as a baseline master-data snapshot. They do not currently contain `effective_from` / `effective_to` fields or a separate historical version stream. This is a known scope limitation and is not represented as implemented effective-dated master-data history.

Maintenance work-order lifecycle history is explicitly event-based. Its `event_timestamp` records when each generated status transition occurs. Failure events use `symptom_start_at`, `failure_at`, and `detected_at` to preserve the failure timeline.

## 8. Risk and Evaluation Outputs

| Output | Purpose |
|---|---|
| `machine_risk_scores.csv` | Current machine-level risk score, band, components, reasons, data-quality indicators, and recommendation. |
| `risk_audit_log.csv` | Traceable record of scoring version, machine, input window, score/band, reasons, and recommendation. |
| `risk_evaluation_predictions.csv` | Historical machine-day decisions and evaluation outcomes. |
| `risk_evaluation_metrics.csv` | Aggregated risk-evaluation metrics. |

The risk engine uses recent 24-hour telemetry, sensor-specific thresholds/trends, maintenance activity over the previous 30 days, and operating context. Ground-truth labels are not input features. Risk scores are heuristic indicators, not calibrated failure probabilities.

## 9. Export and Validation Notes

`src/export_data.py` exports 12 relational datasets to JSON and SQLite and generates `seed.sql`. High-volume telemetry remains in CSV. The extended validator uses the export schema's configured primary-key and foreign-key definitions, applies the documented domain/lifecycle checks, validates each sensor's telemetry schedule, and independently checks the five exception fixtures.

Recorded export checks confirmed JSON/SQLite row-count agreement and no SQLite foreign-key violations. The SQL seed was generated, but a fresh-database replay is not recorded as tested.
