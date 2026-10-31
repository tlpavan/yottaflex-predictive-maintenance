
import csv
import json
import random

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Typical sensor readings for each machine operating state.
# These are synthetic baseline values, not real equipment specifications.
SENSOR_PROFILES = {
    "TEMP": {
        "RUNNING": (68, 5),
        "IDLE": (42, 3),
        "STOPPED": (30, 2),
        "MAINTENANCE": (35, 3),
    },
    "VIBRATION": {
        "RUNNING": (3.0, 0.7),
        "IDLE": (0.7, 0.2),
        "STOPPED": (0.1, 0.05),
        "MAINTENANCE": (0.4, 0.2),
    },
    "CURRENT": {
        "RUNNING": (48, 8),
        "IDLE": (10, 3),
        "STOPPED": (0.5, 0.2),
        "MAINTENANCE": (5, 2),
    },
    "PRESSURE": {
        "RUNNING": (9, 1.2),
        "IDLE": (3, 0.8),
        "STOPPED": (0.2, 0.1),
        "MAINTENANCE": (1, 0.4),
    },
    "SPEED": {
        "RUNNING": (1800, 150),
        "IDLE": (500, 80),
        "STOPPED": (0, 0),
        "MAINTENANCE": (0, 0),
    },
}


CSV_FIELDS = [
    "telemetry_id",
    "sensor_id",
    "machine_id",
    "timestamp",
    "sensor_type",
    "value",
    "unit",
    "operating_state",
    "shift_code",
]


def load_sensors(sensor_file):
    """Read sensors and group them by their parent machine."""

    sensors_by_machine = defaultdict(list)

    with open(sensor_file, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        required_columns = {
            "sensor_id",
            "machine_id",
            "sensor_type",
            "unit",
            "min_value",
            "max_value",
        }

        if not reader.fieldnames or not required_columns.issubset(
            reader.fieldnames
        ):
            raise ValueError("Sensor CSV is missing required columns.")

        for row in reader:
            sensor_type = row["sensor_type"]

            if sensor_type not in SENSOR_PROFILES:
                raise ValueError(
                    f"Unsupported sensor type: {sensor_type}"
                )

            minimum = float(row["min_value"])
            maximum = float(row["max_value"])

            if minimum >= maximum:
                raise ValueError(
                    f"Invalid range for sensor {row['sensor_id']}"
                )

            sensors_by_machine[row["machine_id"]].append({
                "sensor_id": row["sensor_id"],
                "machine_id": row["machine_id"],
                "sensor_type": sensor_type,
                "unit": row["unit"],
                "min_value": minimum,
                "max_value": maximum,
            })

    if not sensors_by_machine:
        raise ValueError("No sensors were found in the input CSV.")

    return sensors_by_machine


def choose_operating_state(generator):
    """Choose a machine state using reproducible probabilities."""

    chance = generator.random()

    if chance < 0.85:
        return "RUNNING"

    if chance < 0.94:
        return "IDLE"

    if chance < 0.99:
        return "STOPPED"

    return "MAINTENANCE"


def get_shift_code(timestamp):
    """Assign one of three eight-hour shifts using UTC time."""

    hour = timestamp.hour

    if 6 <= hour < 14:
        return "A"

    if 14 <= hour < 22:
        return "B"

    return "C"


def generate_sensor_value(sensor, operating_state, generator):
    """Generate a realistic synthetic reading within sensor limits."""

    sensor_type = sensor["sensor_type"]

    average, variation = SENSOR_PROFILES[sensor_type][operating_state]

    reading = generator.gauss(average, variation)

    # Keep the generated reading within the configured sensor range.
    reading = max(sensor["min_value"], reading)
    reading = min(sensor["max_value"], reading)

    return round(reading, 3)


def generate_telemetry(
    sensor_file,
    output_file,
    start_time,
    days,
    interval_minutes,
    seed,
):
    """Generate telemetry and write records incrementally to CSV."""

    if days <= 0:
        raise ValueError("Telemetry days must be greater than zero.")

    if interval_minutes <= 0:
        raise ValueError("Interval must be greater than zero.")

    start = datetime.fromisoformat(start_time)

    if start.tzinfo is None:
        raise ValueError("Telemetry start time must include a timezone.")

    start = start.astimezone(timezone.utc)

    sensors_by_machine = load_sensors(sensor_file)

    generator = random.Random(seed)
    interval = timedelta(minutes=interval_minutes)
    total_intervals = days * 24 * 60 // interval_minutes

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )

    record_count = 0

    try:
        with open(
            temporary_path,
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=CSV_FIELDS,
            )

            writer.writeheader()

            # Process one timestamp at a time.
            # This avoids storing millions of readings in memory.
            for interval_number in range(total_intervals):

                timestamp = start + interval * interval_number
                shift_code = get_shift_code(timestamp)

                for machine_id, sensors in sensors_by_machine.items():

                    # All sensors on a machine share its operating state
                    # for this timestamp.
                    operating_state = choose_operating_state(generator)

                    for sensor in sensors:

                        value = generate_sensor_value(
                            sensor,
                            operating_state,
                            generator,
                        )

                        writer.writerow({
                            "telemetry_id": (
                                f"TEL-{sensor['sensor_id']}-"
                                f"{timestamp.strftime('%Y%m%dT%H%M')}"
                            ),
                            "sensor_id": sensor["sensor_id"],
                            "machine_id": machine_id,
                            "timestamp": timestamp.isoformat(),
                            "sensor_type": sensor["sensor_type"],
                            "value": value,
                            "unit": sensor["unit"],
                            "operating_state": operating_state,
                            "shift_code": shift_code,
                        })

                        record_count += 1

        # Publish the completed file only after generation succeeds.
        temporary_path.replace(output_path)

    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise

    print("\n========== TELEMETRY SUMMARY ==========")
    print(f"Machines: {len(sensors_by_machine)}")
    print(f"Sensors: {sum(len(s) for s in sensors_by_machine.values())}")
    print(f"Days: {days}")
    print(f"Interval: {interval_minutes} minutes")
    print(f"Telemetry records: {record_count:,}")
    print(f"Output file: {output_path}")
    print("RESULT: TELEMETRY GENERATED SUCCESSFULLY")

    return record_count


def main():
    project_root = Path(__file__).resolve().parent.parent

    config_path = project_root / "config" / "config.json"

    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    output_dir = project_root / config["output_dir"]

    sensor_file = output_dir / "sensors.csv"
    telemetry_file = output_dir / "telemetry.csv"

    if not sensor_file.exists():
        raise FileNotFoundError(
            "sensors.csv not found. Run master_data.py first."
        )

    generate_telemetry(
        sensor_file=sensor_file,
        output_file=telemetry_file,
        start_time=config["telemetry_start"],
        days=config["telemetry_days"],
        interval_minutes=config["telemetry_interval_minutes"],
        seed=config["seed"],
    )


if __name__ == "__main__":
    main()
