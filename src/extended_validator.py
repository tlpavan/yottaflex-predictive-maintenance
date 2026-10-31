import csv
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src.export_data import FOREIGN_KEYS, PRIMARY_KEYS, TABLES
from src.master_data import MACHINE_TYPES, PLANT_LOCATIONS, SENSOR_DEFINITIONS
from src.event_generator import (
    FAILURE_TYPES,
    ROOT_CAUSES,
    SEVERITIES,
    TECHNICIAN_SKILLS,
    PART_CATALOGUE,
    create_operating_shifts,
)
from src.telemetry_generator import SENSOR_PROFILES, get_shift_code


EXPECTED_EXCEPTION_FILES = {
    "UNKNOWN_SENSOR": "unknown_sensor.csv",
    "INVALID_UNIT_OR_RANGE": "invalid_sensor_reading.csv",
    "FAILURE_BEFORE_SYMPTOM": "invalid_failure_chronology.csv",
    "MAINTENANCE_END_BEFORE_START": "invalid_maintenance_chronology.csv",
    "MISSING_TELEMETRY_GAP": "telemetry_gaps.csv",
}

VALID_TRANSITIONS = {
    ("NONE", "OPENED"),
    ("OPENED", "IN_PROGRESS"),
    ("IN_PROGRESS", "COMPLETED"),
}


def parse_aware_datetime(value):
    """Parse an ISO timestamp and require an explicit timezone."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"Timezone is missing: {value}")
    return parsed


def infer_missing_intervals(last_observed_at, next_observed_at, interval_minutes):
    """Infer missing slots from the two observed timestamps, not a supplied count.

    Returns None for invalid chronology or a gap that is not aligned to the
    configured sampling interval. Returns zero when observations are adjacent.
    """
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive")

    previous = parse_aware_datetime(last_observed_at).astimezone(timezone.utc)
    following = parse_aware_datetime(next_observed_at).astimezone(timezone.utc)
    elapsed_seconds = int((following - previous).total_seconds())
    interval_seconds = interval_minutes * 60

    if elapsed_seconds <= 0 or elapsed_seconds % interval_seconds != 0:
        return None

    return (elapsed_seconds // interval_seconds) - 1


def detect_exception_condition(issue_type, row, sensor_details, interval_minutes):
    """Apply the validation rule for one deliberately invalid fixture."""
    if issue_type == "UNKNOWN_SENSOR":
        return row.get("sensor_id") not in sensor_details

    if issue_type == "INVALID_UNIT_OR_RANGE":
        sensor = sensor_details.get(row.get("sensor_id"))
        if sensor is None:
            return False
        try:
            value = float(row["value"])
        except (KeyError, TypeError, ValueError):
            return True
        return (
            row.get("unit") != sensor["unit"]
            or value < sensor["minimum"]
            or value > sensor["maximum"]
        )

    if issue_type == "FAILURE_BEFORE_SYMPTOM":
        try:
            symptom = parse_aware_datetime(row["symptom_start_at"])
            failure = parse_aware_datetime(row["failure_at"])
            detected = parse_aware_datetime(row["detected_at"])
            return not (symptom < failure <= detected)
        except (KeyError, TypeError, ValueError):
            return True

    if issue_type == "MAINTENANCE_END_BEFORE_START":
        try:
            started = parse_aware_datetime(row["started_at"])
            completed = parse_aware_datetime(row["completed_at"])
            return completed < started
        except (KeyError, TypeError, ValueError):
            return True

    if issue_type == "MISSING_TELEMETRY_GAP":
        try:
            missing = infer_missing_intervals(
                row["last_observed_at"],
                row["next_observed_at"],
                interval_minutes,
            )
            return missing is not None and missing > 0
        except (KeyError, TypeError, ValueError):
            return False

    raise ValueError(f"Unsupported exception type: {issue_type}")


class ExtendedDataValidator:
    """Additional relational, domain, telemetry and exception-fixture checks."""

    def __init__(self, project_root, config):
        self.project_root = Path(project_root)
        self.raw_dir = self.project_root / config["output_dir"]
        self.exception_dir = self.project_root / "data" / "exceptions"
        self.config = config
        self.errors = []
        self.tables = {}
        self.sensor_details = {}
        self.failure_by_id = {}
        self.work_order_by_id = {}
        self.max_errors = 100

    def add_error(self, message):
        if len(self.errors) < self.max_errors:
            self.errors.append(message)

    def read_csv(self, path):
        path = Path(path)
        if not path.exists():
            self.add_error(f"Missing file: {path}")
            return []
        with path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                self.add_error(f"CSV has no header: {path.name}")
                return []
            return list(reader)

    def load_relational_tables(self):
        print("Checking primary keys and foreign keys...")
        for table_name in TABLES:
            self.tables[table_name] = self.read_csv(
                self.raw_dir / f"{table_name}.csv"
            )

    def validate_primary_keys(self):
        for table_name, columns in PRIMARY_KEYS.items():
            rows = self.tables.get(table_name, [])
            seen = set()
            for row in rows:
                key = tuple(row.get(column, "") for column in columns)
                if any(value == "" for value in key):
                    self.add_error(
                        f"Missing primary-key value in {table_name}: {columns}"
                    )
                    continue
                if key in seen:
                    self.add_error(
                        f"Duplicate primary key in {table_name}: {key}"
                    )
                seen.add(key)

        # ground_truth is not assigned a SQL primary key in the export schema,
        # but the validator requires one telemetry reading to appear once.
        seen_ground_truth = set()
        for row in self.tables.get("ground_truth", []):
            telemetry_id = row.get("telemetry_id", "")
            if not telemetry_id:
                self.add_error("Missing telemetry_id in ground_truth.")
            elif telemetry_id in seen_ground_truth:
                self.add_error(
                    f"Duplicate telemetry_id in ground_truth: {telemetry_id}"
                )
            seen_ground_truth.add(telemetry_id)

    def validate_foreign_keys(self):
        for child_table, references in FOREIGN_KEYS.items():
            child_rows = self.tables.get(child_table, [])
            for child_column, parent_table, parent_column in references:
                parent_values = {
                    row.get(parent_column, "")
                    for row in self.tables.get(parent_table, [])
                }
                for row in child_rows:
                    value = row.get(child_column, "")
                    if not value or value not in parent_values:
                        self.add_error(
                            f"Invalid {child_table}.{child_column} reference: {value}"
                        )

    def validate_domain_values(self):
        print("Checking allowed values and domain rules...")

        allowed = {
            ("plants", "location"): set(PLANT_LOCATIONS),
            ("machines", "machine_type"): set(MACHINE_TYPES),
            ("machines", "machine_status"): {"ACTIVE"},
            ("sensors", "sensor_type"): {item[0] for item in SENSOR_DEFINITIONS},
            ("technicians", "specialization"): set(TECHNICIAN_SKILLS),
            ("technicians", "availability_status"): {"AVAILABLE"},
            ("parts", "unit"): {"EACH"},
            ("failure_events", "failure_type"): set(FAILURE_TYPES),
            ("failure_events", "root_cause"): set(ROOT_CAUSES),
            ("failure_events", "severity"): set(SEVERITIES),
            ("maintenance_work_orders", "maintenance_type"): {"CORRECTIVE"},
            ("maintenance_work_orders", "priority"): set(SEVERITIES),
            ("maintenance_work_orders", "work_order_status"): {"COMPLETED"},
            ("maintenance_status_history", "previous_status"): {
                "NONE", "OPENED", "IN_PROGRESS"
            },
            ("maintenance_status_history", "new_status"): {
                "OPENED", "IN_PROGRESS", "COMPLETED"
            },
            ("ground_truth", "ground_truth_label"): {"1"},
        }

        for (table_name, column), accepted in allowed.items():
            for row in self.tables.get(table_name, []):
                value = row.get(column, "")
                if value not in accepted:
                    self.add_error(
                        f"Unsupported {table_name}.{column} value: {value}"
                    )

        expected_units = {
            sensor_type: unit
            for sensor_type, unit, _, _ in SENSOR_DEFINITIONS
        }
        for row in self.tables.get("sensors", []):
            sensor_type = row.get("sensor_type", "")
            expected_unit = expected_units.get(sensor_type)
            if expected_unit and row.get("unit") != expected_unit:
                self.add_error(
                    f"Invalid unit for sensor {row.get('sensor_id')}: "
                    f"expected {expected_unit}, found {row.get('unit')}"
                )
            try:
                minimum = float(row["min_value"])
                maximum = float(row["max_value"])
                if not math.isfinite(minimum) or not math.isfinite(maximum):
                    raise ValueError("non-finite sensor limit")
                if minimum >= maximum:
                    self.add_error(
                        f"Invalid sensor range: {row.get('sensor_id')}"
                    )
            except (KeyError, TypeError, ValueError):
                self.add_error(
                    f"Invalid numeric sensor limits: {row.get('sensor_id')}"
                )

        expected_shifts = {
            row["shift_code"]: row for row in create_operating_shifts()
        }
        for row in self.tables.get("operating_shifts", []):
            expected = expected_shifts.get(row.get("shift_code"))
            if expected is None:
                self.add_error(
                    f"Unsupported operating shift: {row.get('shift_code')}"
                )
                continue
            for column in ("shift_name", "start_time", "end_time", "timezone"):
                if row.get(column) != expected[column]:
                    self.add_error(
                        f"Invalid operating_shifts.{column} for "
                        f"{row.get('shift_code')}"
                    )

        expected_parts = {
            part_id: (name, float(cost))
            for part_id, name, cost in PART_CATALOGUE
        }
        for row in self.tables.get("parts", []):
            expected = expected_parts.get(row.get("part_id"))
            try:
                cost = float(row["unit_cost"])
                if not math.isfinite(cost) or cost <= 0:
                    self.add_error(
                        f"Invalid part unit cost: {row.get('part_id')}"
                    )
                if expected and (
                    row.get("part_name") != expected[0]
                    or abs(cost - expected[1]) > 0.001
                ):
                    self.add_error(
                        f"Part catalogue mismatch: {row.get('part_id')}"
                    )
            except (KeyError, TypeError, ValueError):
                self.add_error(
                    f"Invalid part cost: {row.get('part_id')}"
                )

    def validate_failure_and_maintenance_rules(self):
        print("Checking failure and maintenance lifecycle rules...")

        failures = self.tables.get("failure_events", [])
        orders = self.tables.get("maintenance_work_orders", [])
        parts = self.tables.get("parts", [])
        links = self.tables.get("work_order_parts", [])

        self.failure_by_id = {
            row.get("failure_id", ""): row for row in failures
        }
        self.work_order_by_id = {
            row.get("work_order_id", ""): row for row in orders
        }

        for failure in failures:
            failure_id = failure.get("failure_id", "")
            try:
                symptom = parse_aware_datetime(failure["symptom_start_at"])
                failed = parse_aware_datetime(failure["failure_at"])
                detected = parse_aware_datetime(failure["detected_at"])
                if not symptom < failed <= detected:
                    self.add_error(
                        f"Invalid failure lifecycle timestamps: {failure_id}"
                    )
            except (KeyError, TypeError, ValueError):
                self.add_error(
                    f"Invalid failure timestamps: {failure_id}"
                )

        orders_by_failure = Counter(
            row.get("failure_id", "") for row in orders
        )
        for failure in failures:
            failure_id = failure.get("failure_id", "")
            if orders_by_failure[failure_id] != 1:
                self.add_error(
                    f"Expected exactly one work order for failure {failure_id}; "
                    f"found {orders_by_failure[failure_id]}"
                )

        for order in orders:
            order_id = order.get("work_order_id", "")
            failure = self.failure_by_id.get(order.get("failure_id", ""))
            try:
                opened = parse_aware_datetime(order["opened_at"])
                started = parse_aware_datetime(order["started_at"])
                completed = parse_aware_datetime(order["completed_at"])
                if not opened <= started < completed:
                    self.add_error(
                        f"Invalid work order chronology: {order_id}"
                    )
                if failure:
                    failure_at = parse_aware_datetime(failure["failure_at"])
                    if opened < failure_at:
                        self.add_error(
                            f"Work order opened before failure: {order_id}"
                        )
                    expected_downtime = round(
                        (completed - failure_at).total_seconds() / 3600, 2
                    )
                    if abs(float(order["downtime_hours"]) - expected_downtime) > 0.01:
                        self.add_error(
                            f"Downtime reconciliation failed: {order_id}"
                        )
                expected_repair = (
                    completed - started
                ).total_seconds() / 3600
                if abs(float(order["repair_duration_hours"]) - expected_repair) > 0.01:
                    self.add_error(
                        f"Repair-duration reconciliation failed: {order_id}"
                    )
                if failure and order.get("priority") != failure.get("severity"):
                    self.add_error(
                        f"Work-order priority does not match failure severity: {order_id}"
                    )
            except (KeyError, TypeError, ValueError):
                self.add_error(
                    f"Invalid work-order timestamp or duration: {order_id}"
                )

        part_map = {row.get("part_id", ""): row for row in parts}
        for link in links:
            key = (link.get("work_order_id"), link.get("part_id"))
            part = part_map.get(link.get("part_id", ""))
            try:
                quantity = int(link["quantity_used"])
                unit_cost = float(link["unit_cost"])
                if quantity <= 0:
                    self.add_error(f"Non-positive part quantity: {key}")
                if not math.isfinite(unit_cost) or unit_cost < 0:
                    self.add_error(f"Invalid linked part cost: {key}")
                if part and abs(unit_cost - float(part["unit_cost"])) > 0.001:
                    self.add_error(f"Linked part cost mismatch: {key}")
            except (KeyError, TypeError, ValueError):
                self.add_error(f"Invalid work-order part values: {key}")

    def validate_status_history(self):
        history = self.tables.get("maintenance_status_history", [])
        by_order = defaultdict(list)
        for event in history:
            order_id = event.get("work_order_id", "")
            order = self.work_order_by_id.get(order_id)
            if order is None:
                continue
            if event.get("machine_id") != order.get("machine_id"):
                self.add_error(
                    f"Status-history machine mismatch: {event.get('status_event_id')}"
                )
            transition = (
                event.get("previous_status"), event.get("new_status")
            )
            if transition not in VALID_TRANSITIONS:
                self.add_error(
                    f"Unsupported maintenance transition: {transition}"
                )
            try:
                event_time = parse_aware_datetime(event["event_timestamp"])
                by_order[order_id].append((event_time, event))
            except (KeyError, TypeError, ValueError):
                self.add_error(
                    f"Invalid status-history timestamp: {event.get('status_event_id')}"
                )

        for order_id, order in self.work_order_by_id.items():
            actual = sorted(by_order.get(order_id, []), key=lambda item: item[0])
            expected = [
                ("NONE", "OPENED", order.get("opened_at")),
                ("OPENED", "IN_PROGRESS", order.get("started_at")),
                ("IN_PROGRESS", "COMPLETED", order.get("completed_at")),
            ]
            if len(actual) != len(expected):
                self.add_error(
                    f"Expected {len(expected)} status events for {order_id}; "
                    f"found {len(actual)}"
                )
                continue
            for (actual_time, actual_event), (previous, new, timestamp) in zip(actual, expected):
                if (
                    actual_event.get("previous_status") != previous
                    or actual_event.get("new_status") != new
                ):
                    self.add_error(f"Incorrect lifecycle sequence for {order_id}")
                try:
                    if actual_time != parse_aware_datetime(timestamp):
                        self.add_error(f"Lifecycle timestamp mismatch for {order_id}")
                except (TypeError, ValueError):
                    self.add_error(f"Invalid work-order lifecycle timestamp for {order_id}")

    def validate_telemetry_schedule(self):
        print("Checking per-sensor telemetry schedule and data quality...")
        path = self.raw_dir / "telemetry_enriched.csv"
        if not path.exists():
            self.add_error("Missing telemetry_enriched.csv for extended validation")
            return

        sensors = {}
        for row in self.tables.get("sensors", []):
            try:
                sensors[row["sensor_id"]] = {
                    "machine_id": row["machine_id"],
                    "sensor_type": row["sensor_type"],
                    "unit": row["unit"],
                    "minimum": float(row["min_value"]),
                    "maximum": float(row["max_value"]),
                }
            except (KeyError, TypeError, ValueError):
                continue
        self.sensor_details = sensors

        interval_minutes = int(self.config["telemetry_interval_minutes"])
        if interval_minutes <= 0:
            self.add_error("Telemetry interval must be positive")
            return
        interval_seconds = interval_minutes * 60
        expected_per_sensor = (
            int(self.config["telemetry_days"]) * 24 * 60
        ) // interval_minutes
        expected_start = parse_aware_datetime(
            self.config["telemetry_start"]
        ).astimezone(timezone.utc)
        start_epoch = int(expected_start.timestamp())
        expected_end_epoch = start_epoch + (expected_per_sensor - 1) * interval_seconds
        timestamps_by_sensor = {sensor_id: [] for sensor_id in sensors}
        ground_truth_ids = {
            row.get("telemetry_id", "")
            for row in self.tables.get("ground_truth", [])
        }
        matched_ground_truth = set()
        telemetry_count = 0
        seen_shift_codes = {
            row.get("shift_code", "")
            for row in self.tables.get("operating_shifts", [])
        }
        valid_states = set(next(iter(SENSOR_PROFILES.values())).keys())

        with path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            required = {
                "telemetry_id", "sensor_id", "machine_id", "timestamp",
                "sensor_type", "value", "unit", "operating_state", "shift_code",
            }
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                self.add_error("telemetry_enriched.csv is missing required columns")
                return

            for row in reader:
                telemetry_count += 1
                telemetry_id = row.get("telemetry_id", "")
                sensor_id = row.get("sensor_id", "")
                sensor = sensors.get(sensor_id)
                if sensor is None:
                    self.add_error(f"Telemetry references unknown sensor: {sensor_id}")
                    continue

                if row.get("machine_id") != sensor["machine_id"]:
                    self.add_error(f"Telemetry machine/sensor mismatch: {telemetry_id}")
                if row.get("sensor_type") != sensor["sensor_type"]:
                    self.add_error(f"Telemetry sensor type mismatch: {telemetry_id}")
                if row.get("unit") != sensor["unit"]:
                    self.add_error(f"Telemetry unit mismatch: {telemetry_id}")

                if row.get("operating_state") not in valid_states:
                    self.add_error(
                        f"Unsupported telemetry operating state: {row.get('operating_state')}"
                    )
                if row.get("shift_code") not in seen_shift_codes:
                    self.add_error(f"Unknown telemetry shift code: {row.get('shift_code')}")

                try:
                    value = float(row["value"])
                    if not math.isfinite(value) or not sensor["minimum"] <= value <= sensor["maximum"]:
                        self.add_error(f"Telemetry value outside configured limits: {telemetry_id}")
                    timestamp = parse_aware_datetime(row["timestamp"]).astimezone(timezone.utc)
                    expected_shift = get_shift_code(timestamp)
                    if row.get("shift_code") != expected_shift:
                        self.add_error(f"Telemetry shift does not match timestamp: {telemetry_id}")
                    expected_id = (
                        f"TEL-{sensor_id}-{timestamp.strftime('%Y%m%dT%H%M')}"
                    )
                    if telemetry_id != expected_id:
                        self.add_error(f"Telemetry ID does not match sensor/timestamp: {telemetry_id}")
                    timestamps_by_sensor[sensor_id].append(int(timestamp.timestamp()))
                except (KeyError, TypeError, ValueError):
                    self.add_error(f"Invalid telemetry value or timestamp: {telemetry_id}")
                    continue

                if telemetry_id in ground_truth_ids:
                    matched_ground_truth.add(telemetry_id)

        expected_total = len(sensors) * expected_per_sensor
        if telemetry_count != expected_total:
            self.add_error(
                f"Telemetry total mismatch: expected {expected_total}, found {telemetry_count}"
            )

        for sensor_id, values in timestamps_by_sensor.items():
            values.sort()
            if len(values) != expected_per_sensor:
                self.add_error(
                    f"Sensor {sensor_id}: expected {expected_per_sensor} readings, found {len(values)}"
                )
            if not values:
                self.add_error(f"No telemetry readings for sensor {sensor_id}")
                continue
            if values[0] != start_epoch:
                self.add_error(f"Unexpected first telemetry timestamp for sensor {sensor_id}")
            if values[-1] != expected_end_epoch:
                self.add_error(f"Unexpected last telemetry timestamp for sensor {sensor_id}")

            for timestamp in values:
                offset = timestamp - start_epoch
                if (
                    offset < 0
                    or offset > expected_end_epoch - start_epoch
                    or offset % interval_seconds != 0
                ):
                    self.add_error(f"Timestamp is outside the configured schedule for sensor {sensor_id}")
                    break

            for previous, current in zip(values, values[1:]):
                difference = current - previous
                if difference == 0:
                    self.add_error(f"Duplicate sensor/timestamp pair for {sensor_id}")
                elif difference > interval_seconds:
                    if difference % interval_seconds == 0:
                        missing = difference // interval_seconds - 1
                        self.add_error(
                            f"Telemetry gap for sensor {sensor_id}: {missing} reading(s) missing"
                        )
                    else:
                        self.add_error(
                            f"Irregular telemetry gap for sensor {sensor_id}"
                        )
                elif difference < interval_seconds:
                    self.add_error(f"Unexpected short telemetry interval for sensor {sensor_id}")

        unmatched = ground_truth_ids - matched_ground_truth
        if unmatched:
            self.add_error(
                f"{len(unmatched)} ground-truth telemetry IDs are absent from telemetry_enriched.csv"
            )

    def validate_exception_fixtures(self):
        print("Checking five exception fixtures through validator rules...")
        interval_minutes = int(self.config["telemetry_interval_minutes"])
        report = []

        for issue_type, filename in EXPECTED_EXCEPTION_FILES.items():
            rows = self.read_csv(self.exception_dir / filename)
            if len(rows) != 1:
                self.add_error(
                    f"Expected exactly one record in exception fixture {filename}; found {len(rows)}"
                )
                report.append({
                    "issue_type": issue_type,
                    "record_id": "",
                    "ground_truth_label": "1",
                    "detected": "False",
                    "passed": "False",
                    "details": f"Expected one fixture row; found {len(rows)}",
                })
                continue

            row = rows[0]
            label_ok = row.get("issue_type") == issue_type
            try:
                ground_truth_ok = int(row.get("ground_truth_label", "0")) == 1
            except (TypeError, ValueError):
                ground_truth_ok = False

            detected = detect_exception_condition(
                issue_type,
                row,
                self.sensor_details,
                interval_minutes,
            )
            passed = label_ok and ground_truth_ok and detected
            if not label_ok:
                self.add_error(
                    f"Exception fixture label mismatch in {filename}: {row.get('issue_type')}"
                )
            if not ground_truth_ok:
                self.add_error(f"Exception fixture has invalid ground truth label: {filename}")
            if not detected:
                self.add_error(f"Main validator did not detect exception: {issue_type}")

            report.append({
                "issue_type": issue_type,
                "record_id": (
                    row.get("telemetry_id")
                    or row.get("failure_id")
                    or row.get("work_order_id")
                    or row.get("sensor_id")
                    or ""
                ),
                "ground_truth_label": row.get("ground_truth_label", ""),
                "detected": str(bool(detected)),
                "passed": str(bool(passed)),
                "details": "Detected by independent validator rule" if passed else "Validation failed",
            })

        report_path = self.exception_dir / "validator_exception_report.csv"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "issue_type", "record_id", "ground_truth_label",
                    "detected", "passed", "details",
                ],
            )
            writer.writeheader()
            writer.writerows(report)

        passed_count = sum(row["passed"] == "True" for row in report)
        print(f"Exception fixtures detected: {passed_count}/{len(EXPECTED_EXCEPTION_FILES)}")
        print(f"Validator exception report: {report_path}")

    def run(self):
        print("\n========== EXTENDED DATA VALIDATION ==========")
        self.load_relational_tables()
        self.validate_primary_keys()
        self.validate_foreign_keys()
        self.validate_domain_values()
        self.validate_failure_and_maintenance_rules()
        self.validate_status_history()
        self.validate_telemetry_schedule()
        self.validate_exception_fixtures()

        print("\n========== EXTENDED VALIDATION SUMMARY ==========")
        print(f"Errors: {len(self.errors)}")
        if self.errors:
            for error in self.errors:
                print(f"- {error}")
            print("RESULT: EXTENDED VALIDATION FAILED")
            return False

        print("RESULT: ALL EXTENDED CHECKS PASSED")
        return True
