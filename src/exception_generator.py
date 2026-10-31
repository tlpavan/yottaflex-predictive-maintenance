
import csv
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUTPUT = ROOT / "data" / "exceptions"

OUTPUT.mkdir(parents=True, exist_ok=True)


def read_first_record(filename):
    with open(RAW / filename, "r", newline="", encoding="utf-8") as file:
        return next(csv.DictReader(file))


def read_sensors():
    with open(RAW / "sensors.csv", "r", newline="", encoding="utf-8") as file:
        return {
            row["sensor_id"]: row
            for row in csv.DictReader(file)
        }


def write_csv(filename, rows):
    if not rows:
        return

    fields = list(dict.fromkeys(
        key for row in rows for key in row
    ))

    with open(OUTPUT / filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def add_label(row, issue_type):
    row["issue_type"] = issue_type
    row["ground_truth_label"] = 1
    return row


def parse_time(value):
    return datetime.fromisoformat(value)


def main():
    sensors = read_sensors()

    telemetry = read_first_record("telemetry.csv")
    failure = read_first_record("failure_events.csv")
    work_order = read_first_record("maintenance_work_orders.csv")

    sensor = sensors[telemetry["sensor_id"]]

    exceptions = []

    # 1. Telemetry from an unknown sensor
    unknown = telemetry.copy()
    unknown["telemetry_id"] = "EXC-TEL-UNKNOWN-001"
    unknown["sensor_id"] = "SNS-UNKNOWN-001"
    unknown = add_label(unknown, "UNKNOWN_SENSOR")

    write_csv("unknown_sensor.csv", [unknown])

    detected = unknown["sensor_id"] not in sensors

    exceptions.append({
        "issue_id": "EXC-001",
        "issue_type": "UNKNOWN_SENSOR",
        "record_id": unknown["telemetry_id"],
        "detected": detected,
        "ground_truth_label": 1,
        "description": "Telemetry references a sensor absent from master data"
    })

    # 2. Impossible sensor unit and out-of-range value
    invalid = telemetry.copy()
    invalid["telemetry_id"] = "EXC-TEL-INVALID-001"
    invalid["value"] = str(float(sensor["max_value"]) + 10)
    invalid["unit"] = "INVALID_UNIT"
    invalid = add_label(invalid, "INVALID_UNIT_OR_RANGE")

    write_csv("invalid_sensor_reading.csv", [invalid])

    detected = (
        invalid["unit"] != sensor["unit"]
        or float(invalid["value"]) > float(sensor["max_value"])
    )

    exceptions.append({
        "issue_id": "EXC-002",
        "issue_type": "INVALID_UNIT_OR_RANGE",
        "record_id": invalid["telemetry_id"],
        "detected": detected,
        "ground_truth_label": 1,
        "description": "Sensor reading has an invalid unit and exceeds its configured maximum"
    })

    # 3. Failure recorded before symptom start
    invalid_failure = failure.copy()
    invalid_failure["failure_id"] = "EXC-FAIL-001"

    symptom_time = parse_time(invalid_failure["symptom_start_at"])
    invalid_failure["failure_at"] = (
        symptom_time - timedelta(hours=1)
    ).isoformat()

    invalid_failure = add_label(
        invalid_failure, "FAILURE_BEFORE_SYMPTOM"
    )

    write_csv("invalid_failure_chronology.csv", [invalid_failure])

    detected = (
        parse_time(invalid_failure["failure_at"])
        < parse_time(invalid_failure["symptom_start_at"])
    )

    exceptions.append({
        "issue_id": "EXC-003",
        "issue_type": "FAILURE_BEFORE_SYMPTOM",
        "record_id": invalid_failure["failure_id"],
        "detected": detected,
        "ground_truth_label": 1,
        "description": "Failure timestamp occurs before symptom start"
    })

    # 4. Maintenance completion before maintenance start
    invalid_work_order = work_order.copy()
    invalid_work_order["work_order_id"] = "EXC-WO-001"

    start_time = parse_time(invalid_work_order["started_at"])
    invalid_work_order["completed_at"] = (
        start_time - timedelta(hours=1)
    ).isoformat()

    invalid_work_order = add_label(
        invalid_work_order, "MAINTENANCE_END_BEFORE_START"
    )

    write_csv("invalid_maintenance_chronology.csv", [invalid_work_order])

    detected = (
        parse_time(invalid_work_order["completed_at"])
        < parse_time(invalid_work_order["started_at"])
    )

    exceptions.append({
        "issue_id": "EXC-004",
        "issue_type": "MAINTENANCE_END_BEFORE_START",
        "record_id": invalid_work_order["work_order_id"],
        "detected": detected,
        "ground_truth_label": 1,
        "description": "Maintenance completion occurs before maintenance start"
    })

    # 5. Missing telemetry interval - never replace missing readings with zero
    observed_time = parse_time(telemetry["timestamp"])
    next_time = observed_time + timedelta(hours=3)

    gap = {
        "sensor_id": telemetry["sensor_id"],
        "machine_id": telemetry["machine_id"],
        "last_observed_at": observed_time.isoformat(),
        "next_observed_at": next_time.isoformat(),
        "missing_start_at": (observed_time + timedelta(hours=1)).isoformat(),
        "missing_end_at": (observed_time + timedelta(hours=2)).isoformat(),
        "missing_intervals": 2,
        "issue_type": "MISSING_TELEMETRY_GAP",
        "ground_truth_label": 1,
        "scenario_fixture_only": "YES"
    }

    write_csv("telemetry_gaps.csv", [gap])

    detected = gap["missing_intervals"] > 0

    exceptions.append({
        "issue_id": "EXC-005",
        "issue_type": "MISSING_TELEMETRY_GAP",
        "record_id": telemetry["sensor_id"],
        "detected": detected,
        "ground_truth_label": 1,
        "description": "Two expected hourly readings are missing; no zero readings are inserted"
    })

    # Final exception report
    write_csv("exception_report.csv", exceptions)

    detected_count = sum(row["detected"] for row in exceptions)

    print("\n========== EXCEPTION SCENARIO SUMMARY ==========")
    print(f"Scenarios created: {len(exceptions)}")
    print(f"Scenarios detected: {detected_count}")
    print(f"Scenarios not detected: {len(exceptions) - detected_count}")
    print("Exception report: data/exceptions/exception_report.csv")
    print("Baseline data was not modified.")

    if detected_count != len(exceptions):
        raise RuntimeError("Some exception scenarios were not detected.")

    print("RESULT: ALL EXCEPTION SCENARIOS DETECTED")


if __name__ == "__main__":
    main()
