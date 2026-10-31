
import csv
import json
from pathlib import Path

SENSOR_DEFINITIONS = [
    ("TEMP", "C", 20, 120),
    ("VIBRATION", "mm/s", 0, 20),
    ("CURRENT", "A", 0, 100),
    ("PRESSURE", "bar", 0, 20),
    ("SPEED", "rpm", 0, 5000)
]

MACHINE_TYPES = [
    "PUMP",
    "MOTOR",
    "COMPRESSOR",
    "CONVEYOR"
]

PLANT_LOCATIONS = [
    "Hyderabad",
    "Pune",
    "Chennai",
    "Bengaluru"
]


def write_csv(file_path, rows):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        return

    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def generate_master_data(config):
    plant_count = config["plants"]
    line_count = config["lines"]
    machine_count = config["machines"]
    sensor_count = config["sensors"]

    if min(plant_count, line_count, machine_count, sensor_count) <= 0:
        raise ValueError("All record counts must be positive.")

    if line_count < plant_count:
        raise ValueError("There must be at least one line per plant.")

    if machine_count < line_count:
        raise ValueError("There must be at least one machine per line.")

    if sensor_count < machine_count:
        raise ValueError("There must be at least one sensor per machine.")

    plants = []
    lines = []
    machines = []
    sensors = []

    # Generate parent records: plants
    for i in range(plant_count):
        plants.append({
            "plant_id": f"PLT-{i + 1:03d}",
            "plant_name": f"Plant {i + 1}",
            "location": PLANT_LOCATIONS[i % len(PLANT_LOCATIONS)]
        })

    # Generate production lines linked to plants
    for i in range(line_count):
        plant = plants[i % plant_count]

        lines.append({
            "line_id": f"LINE-{plant['plant_id']}-{i + 1:03d}",
            "plant_id": plant["plant_id"],
            "line_name": f"Production Line {i + 1}"
        })

    # Generate machines linked to production lines
    for i in range(machine_count):
        line = lines[i % line_count]

        machines.append({
            "machine_id": f"MCH-{line['line_id']}-{i + 1:03d}",
            "line_id": line["line_id"],
            "machine_type": MACHINE_TYPES[i % len(MACHINE_TYPES)],
            "machine_status": "ACTIVE"
        })

    # Generate sensors linked to machines
    for i in range(sensor_count):
        machine = machines[i % machine_count]

        sensor_type, unit, minimum, maximum = (
            SENSOR_DEFINITIONS[
                (i // machine_count) % len(SENSOR_DEFINITIONS)
            ]
        )

        sequence = (
            i // (machine_count * len(SENSOR_DEFINITIONS))
        ) + 1

        sensors.append({
            "sensor_id": (
                f"SNS-{machine['machine_id']}-{sensor_type}-{sequence:02d}"
            ),
            "machine_id": machine["machine_id"],
            "sensor_type": sensor_type,
            "unit": unit,
            "min_value": minimum,
            "max_value": maximum
        })

    return {
        "plants": plants,
        "production_lines": lines,
        "machines": machines,
        "sensors": sensors
    }


def validate_master_data(tables):
    errors = []

    def check_unique(rows, key, table_name):
        values = [row[key] for row in rows]

        if len(values) != len(set(values)):
            errors.append(f"Duplicate {key} found in {table_name}")

    check_unique(tables["plants"], "plant_id", "plants")
    check_unique(tables["production_lines"], "line_id", "production_lines")
    check_unique(tables["machines"], "machine_id", "machines")
    check_unique(tables["sensors"], "sensor_id", "sensors")

    plant_ids = {
        row["plant_id"] for row in tables["plants"]
    }

    line_ids = {
        row["line_id"] for row in tables["production_lines"]
    }

    machine_ids = {
        row["machine_id"] for row in tables["machines"]
    }

    for line in tables["production_lines"]:
        if line["plant_id"] not in plant_ids:
            errors.append(
                f"Invalid plant_id in production_lines: {line['line_id']}"
            )

    for machine in tables["machines"]:
        if machine["line_id"] not in line_ids:
            errors.append(
                f"Invalid line reference: {machine['machine_id']}"
            )

    for sensor in tables["sensors"]:
        if sensor["machine_id"] not in machine_ids:
            errors.append(
                f"Invalid machine reference: {sensor['sensor_id']}"
            )

        if sensor["min_value"] >= sensor["max_value"]:
            errors.append(
                f"Invalid sensor range: {sensor['sensor_id']}"
            )

    return errors


def save_master_data(tables, output_dir):
    output_dir = Path(output_dir)

    for table_name, rows in tables.items():
        file_path = output_dir / f"{table_name}.csv"
        write_csv(file_path, rows)
        print(f"Created: {file_path}")


def main():
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config" / "config.json"

    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    tables = generate_master_data(config)

    errors = validate_master_data(tables)

    print("\n========== MASTER DATA SUMMARY ==========")

    for table_name, rows in tables.items():
        print(f"{table_name}: {len(rows)}")

    print(f"Validation errors: {len(errors)}")

    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit(1)

    output_dir = project_root / config["output_dir"]
    save_master_data(tables, output_dir)

    print("\nRESULT: MASTER DATA GENERATED SUCCESSFULLY")


if __name__ == "__main__":
    main()
