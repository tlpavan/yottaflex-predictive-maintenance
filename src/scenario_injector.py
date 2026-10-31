
import csv
import json

from collections import defaultdict
from datetime import datetime
from pathlib import Path


# Sensor patterns expected before each failure type.
FAILURE_SENSOR_RULES = {
    "OVERHEATING": {
        "TEMP": "increase",
    },
    "EXCESSIVE_VIBRATION": {
        "VIBRATION": "increase",
    },
    "BEARING_FAILURE": {
        "VIBRATION": "increase",
        "TEMP": "increase",
    },
    "PRESSURE_DROP": {
        "PRESSURE": "decrease",
    },
    "MOTOR_FAILURE": {
        "CURRENT": "increase",
        "TEMP": "increase",
    },
}


GROUND_TRUTH_FIELDS = [
    "telemetry_id",
    "failure_id",
    "machine_id",
    "failure_type",
    "ground_truth_label",
    "symptom_start_at",
    "failure_at",
]


def load_sensor_limits(sensor_file):
    """Load minimum and maximum values for every sensor."""

    sensor_limits = {}

    with open(sensor_file, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        required = {"sensor_id", "min_value", "max_value"}

        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Sensor master data is missing required columns.")

        for row in reader:
            minimum = float(row["min_value"])
            maximum = float(row["max_value"])

            if minimum >= maximum:
                raise ValueError(
                    f"Invalid limits for sensor {row['sensor_id']}"
                )

            sensor_limits[row["sensor_id"]] = (minimum, maximum)

    return sensor_limits


def load_failure_events(failure_file):
    """Load failure events and group them by machine."""

    events_by_machine = defaultdict(list)

    with open(failure_file, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        required = {
            "failure_id",
            "machine_id",
            "failure_type",
            "symptom_start_at",
            "failure_at",
        }

        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Failure event CSV is missing required columns.")

        for row in reader:
            failure_type = row["failure_type"]

            if failure_type not in FAILURE_SENSOR_RULES:
                raise ValueError(
                    f"Unsupported failure type: {failure_type}"
                )

            symptom_start = datetime.fromisoformat(
                row["symptom_start_at"]
            )

            failure_time = datetime.fromisoformat(
                row["failure_at"]
            )

            if symptom_start.tzinfo is None or failure_time.tzinfo is None:
                raise ValueError("Failure timestamps must include timezones.")

            if symptom_start >= failure_time:
                raise ValueError(
                    f"Invalid timeline for {row['failure_id']}"
                )

            event = {
                **row,
                "symptom_start_dt": symptom_start,
                "failure_dt": failure_time,
            }

            events_by_machine[row["machine_id"]].append(event)

    for events in events_by_machine.values():
        events.sort(key=lambda event: event["symptom_start_dt"])

    return events_by_machine


def find_matching_event(row, events):
    """Find the active failure event affecting a sensor reading."""

    timestamp = datetime.fromisoformat(row["timestamp"])
    sensor_type = row["sensor_type"]

    for event in reversed(events):

        if event["symptom_start_dt"] <= timestamp < event["failure_dt"]:

            sensor_rules = FAILURE_SENSOR_RULES[event["failure_type"]]

            if sensor_type in sensor_rules:
                return event

    return None


def apply_failure_pattern(
    value,
    minimum,
    maximum,
    direction,
    progress,
):
    """Gradually change the sensor value towards a configured limit."""

    if direction == "increase":
        adjusted_value = value + (
            (maximum - value) * 0.65 * progress
        )

    elif direction == "decrease":
        adjusted_value = value - (
            (value - minimum) * 0.65 * progress
        )

    else:
        raise ValueError(f"Unknown direction: {direction}")

    adjusted_value = max(minimum, min(maximum, adjusted_value))

    return round(adjusted_value, 3)


def inject_pre_failure_patterns(
    telemetry_file,
    failure_file,
    sensor_file,
    enriched_file,
    ground_truth_file,
):
    """Generate enriched telemetry and separate ground-truth labels."""

    events_by_machine = load_failure_events(failure_file)
    sensor_limits = load_sensor_limits(sensor_file)

    enriched_path = Path(enriched_file)
    ground_truth_path = Path(ground_truth_file)

    enriched_path.parent.mkdir(parents=True, exist_ok=True)
    ground_truth_path.parent.mkdir(parents=True, exist_ok=True)

    enriched_temp = enriched_path.with_suffix(".csv.tmp")
    truth_temp = ground_truth_path.with_suffix(".csv.tmp")

    total_records = 0
    modified_records = 0

    try:
        with open(
            telemetry_file, "r", newline="", encoding="utf-8"
        ) as source, open(
            enriched_temp, "w", newline="", encoding="utf-8"
        ) as enriched_output, open(
            truth_temp, "w", newline="", encoding="utf-8"
        ) as truth_output:

            reader = csv.DictReader(source)

            required = {
                "telemetry_id",
                "sensor_id",
                "machine_id",
                "timestamp",
                "sensor_type",
                "value",
            }

            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError("Telemetry CSV is missing required columns.")

            telemetry_writer = csv.DictWriter(
                enriched_output,
                fieldnames=reader.fieldnames,
            )

            truth_writer = csv.DictWriter(
                truth_output,
                fieldnames=GROUND_TRUTH_FIELDS,
            )

            telemetry_writer.writeheader()
            truth_writer.writeheader()

            # Stream records instead of loading 1.08 million rows into memory.
            for row in reader:

                total_records += 1

                sensor_id = row["sensor_id"]

                if sensor_id not in sensor_limits:
                    raise ValueError(
                        f"Unknown sensor in telemetry: {sensor_id}"
                    )

                machine_events = events_by_machine.get(
                    row["machine_id"], []
                )

                event = find_matching_event(row, machine_events)

                if event is not None:

                    direction = FAILURE_SENSOR_RULES[
                        event["failure_type"]
                    ][row["sensor_type"]]

                    timestamp = datetime.fromisoformat(row["timestamp"])

                    duration = (
                        event["failure_dt"] -
                        event["symptom_start_dt"]
                    ).total_seconds()

                    elapsed = (
                        timestamp - event["symptom_start_dt"]
                    ).total_seconds()

                    progress = elapsed / duration

                    minimum, maximum = sensor_limits[sensor_id]

                    original_value = float(row["value"])

                    adjusted_value = apply_failure_pattern(
                        value=original_value,
                        minimum=minimum,
                        maximum=maximum,
                        direction=direction,
                        progress=progress,
                    )

                    row["value"] = str(adjusted_value)

                    modified_records += 1

                    truth_writer.writerow({
                        "telemetry_id": row["telemetry_id"],
                        "failure_id": event["failure_id"],
                        "machine_id": row["machine_id"],
                        "failure_type": event["failure_type"],
                        "ground_truth_label": 1,
                        "symptom_start_at": event["symptom_start_at"],
                        "failure_at": event["failure_at"],
                    })

                telemetry_writer.writerow(row)

        # Replace output files only after both files are written successfully.
        enriched_temp.replace(enriched_path)
        truth_temp.replace(ground_truth_path)

    except Exception:
        if enriched_temp.exists():
            enriched_temp.unlink()

        if truth_temp.exists():
            truth_temp.unlink()

        raise

    failure_count = sum(
        len(events) for events in events_by_machine.values()
    )

    print("\n========== SCENARIO INJECTION SUMMARY ==========")
    print(f"Telemetry records processed: {total_records:,}")
    print(f"Records with pre-failure patterns: {modified_records:,}")
    print(f"Failure events: {failure_count}")
    print(f"Enriched telemetry: {enriched_path}")
    print(f"Ground truth: {ground_truth_path}")
    print("RESULT: SCENARIO INJECTION COMPLETED")

    return total_records, modified_records


def main():
    project_root = Path(__file__).resolve().parent.parent

    config_file = project_root / "config" / "config.json"

    with open(config_file, "r", encoding="utf-8") as file:
        config = json.load(file)

    output_dir = project_root / config["output_dir"]

    telemetry_file = output_dir / "telemetry.csv"
    failure_file = output_dir / "failure_events.csv"
    sensor_file = output_dir / "sensors.csv"

    enriched_file = output_dir / "telemetry_enriched.csv"
    ground_truth_file = output_dir / "ground_truth.csv"

    inject_pre_failure_patterns(
        telemetry_file=telemetry_file,
        failure_file=failure_file,
        sensor_file=sensor_file,
        enriched_file=enriched_file,
        ground_truth_file=ground_truth_file,
    )


if __name__ == "__main__":
    main()
