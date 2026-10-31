
import csv
import json
import random

from datetime import datetime, timedelta, timezone
from pathlib import Path


FAILURE_TYPES = [
    "OVERHEATING",
    "EXCESSIVE_VIBRATION",
    "BEARING_FAILURE",
    "PRESSURE_DROP",
    "MOTOR_FAILURE",
]

ROOT_CAUSES = [
    "BEARING_WEAR",
    "INSUFFICIENT_LUBRICATION",
    "COOLING_SYSTEM_ISSUE",
    "MECHANICAL_IMBALANCE",
    "ELECTRICAL_FAULT",
]

SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

TECHNICIAN_SKILLS = [
    "MECHANICAL",
    "ELECTRICAL",
    "INSTRUMENTATION",
    "GENERAL_MAINTENANCE",
]

PART_CATALOGUE = [
    ("BEARING-001", "Industrial Bearing", 1250.00),
    ("FILTER-001", "Air Filter", 450.00),
    ("BELT-001", "Drive Belt", 850.00),
    ("MOTOR-001", "Electric Motor Component", 3500.00),
    ("SEAL-001", "Mechanical Seal", 650.00),
    ("SENSOR-001", "Temperature Sensor", 1100.00),
    ("VALVE-001", "Pressure Valve", 1800.00),
    ("COOLANT-001", "Cooling Fluid", 300.00),
    ("LUBRICANT-001", "Industrial Lubricant", 550.00),
    ("SHAFT-001", "Drive Shaft", 2400.00),
]


def read_machine_ids(machine_file):
    """Load valid machine IDs from the master data."""

    machine_ids = []

    with open(machine_file, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames or "machine_id" not in reader.fieldnames:
            raise ValueError("Machine CSV is missing machine_id.")

        for row in reader:
            machine_ids.append(row["machine_id"])

    if not machine_ids:
        raise ValueError("No machines found.")

    if len(machine_ids) != len(set(machine_ids)):
        raise ValueError("Duplicate machine IDs found.")

    return machine_ids


def create_technicians():
    """Create a small synthetic technician master table."""

    technicians = []

    for number in range(1, 21):
        skill = TECHNICIAN_SKILLS[(number - 1) % len(TECHNICIAN_SKILLS)]

        technicians.append({
            "technician_id": f"TECH-{number:03d}",
            "technician_name": f"Technician {number:03d}",
            "specialization": skill,
            "availability_status": "AVAILABLE",
        })

    return technicians


def create_parts():
    """Create the replacement-parts catalogue."""

    parts = []

    for part_id, part_name, unit_cost in PART_CATALOGUE:
        parts.append({
            "part_id": part_id,
            "part_name": part_name,
            "unit_cost": unit_cost,
            "unit": "EACH",
        })

    return parts


def create_operating_shifts():
    """Define the three eight-hour operating shifts in UTC."""

    return [
        {
            "shift_code": "A",
            "shift_name": "Morning Shift",
            "start_time": "06:00",
            "end_time": "14:00",
            "timezone": "UTC",
        },
        {
            "shift_code": "B",
            "shift_name": "Evening Shift",
            "start_time": "14:00",
            "end_time": "22:00",
            "timezone": "UTC",
        },
        {
            "shift_code": "C",
            "shift_name": "Night Shift",
            "start_time": "22:00",
            "end_time": "06:00",
            "timezone": "UTC",
        },
    ]


def generate_failure_events(
    machine_ids,
    start_time,
    days,
    failure_count,
    generator,
):
    """Generate labelled failure events linked to valid machines."""

    if failure_count < 100 or failure_count > 200:
        raise ValueError("Failure count must be between 100 and 200.")

    total_hours = days * 24

    if total_hours <= 48:
        raise ValueError("At least three days are required.")

    failures = []

    # Keep the first 48 hours free of failures so that each event
    # can have a meaningful pre-failure observation window.
    for number in range(1, failure_count + 1):

        failure_hour = generator.randint(48, total_hours - 1)

        failure_time = start_time + timedelta(hours=failure_hour)

        symptom_hours = generator.randint(6, 24)

        symptom_start = failure_time - timedelta(hours=symptom_hours)

        severity = generator.choices(
            SEVERITIES,
            weights=[10, 35, 40, 15],
            k=1,
        )[0]

        failure = {
            "failure_id": f"FAIL-{number:06d}",
            "machine_id": generator.choice(machine_ids),
            "failure_type": generator.choice(FAILURE_TYPES),
            "root_cause": generator.choice(ROOT_CAUSES),
            "severity": severity,
            "symptom_start_at": symptom_start.isoformat(),
            "failure_at": failure_time.isoformat(),
            "detected_at": failure_time.isoformat(),
            "ground_truth_label": 1,
        }

        failures.append(failure)

    failures.sort(key=lambda event: event["failure_at"])

    return failures


def generate_work_orders(failures, technicians, generator):
    """Create one corrective maintenance order for every failure."""

    work_orders = []

    for number, failure in enumerate(failures, start=1):

        detected_at = datetime.fromisoformat(failure["detected_at"])

        opened_at = detected_at

        started_at = opened_at + timedelta(
            minutes=generator.randint(15, 120)
        )

        repair_hours = generator.randint(2, 24)

        completed_at = started_at + timedelta(hours=repair_hours)

        failure_at = datetime.fromisoformat(failure["failure_at"])

        downtime_hours = round(
            (completed_at - failure_at).total_seconds() / 3600,
            2
        )

        technician = generator.choice(technicians)

        work_orders.append({
            "work_order_id": f"WO-{detected_at.year}-{number:06d}",
            "failure_id": failure["failure_id"],
            "machine_id": failure["machine_id"],
            "technician_id": technician["technician_id"],
            "maintenance_type": "CORRECTIVE",
            "priority": failure["severity"],
            "opened_at": opened_at.isoformat(),
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "work_order_status": "COMPLETED",
            "repair_duration_hours": repair_hours,
            "downtime_hours": downtime_hours,
        })

    return work_orders


def generate_work_order_parts(work_orders, parts, generator):
    """Create the many-to-many relationship between orders and parts."""

    work_order_parts = []

    for work_order in work_orders:

        # Some maintenance jobs do not require replacement parts.
        if generator.random() < 0.20:
            continue

        selected_parts = generator.sample(
            parts,
            k=generator.randint(1, 3),
        )

        for part in selected_parts:

            work_order_parts.append({
                "work_order_id": work_order["work_order_id"],
                "part_id": part["part_id"],
                "quantity_used": generator.randint(1, 3),
                "unit_cost": part["unit_cost"],
            })

    return work_order_parts


def validate_events(
    machine_ids,
    failures,
    work_orders,
    technicians,
    parts,
    work_order_parts,
):
    """Validate event IDs, references and chronological consistency."""

    errors = []

    valid_machines = set(machine_ids)
    valid_technicians = {
        row["technician_id"] for row in technicians
    }
    valid_parts = {
        row["part_id"] for row in parts
    }
    valid_failures = {
        row["failure_id"] for row in failures
    }
    valid_work_orders = {
        row["work_order_id"] for row in work_orders
    }

    if len(valid_failures) != len(failures):
        errors.append("Duplicate failure IDs found.")

    if len(valid_work_orders) != len(work_orders):
        errors.append("Duplicate work order IDs found.")

    for failure in failures:

        if failure["machine_id"] not in valid_machines:
            errors.append(
                f"Unknown machine in failure: {failure['failure_id']}"
            )

        symptom = datetime.fromisoformat(failure["symptom_start_at"])
        failure_time = datetime.fromisoformat(failure["failure_at"])
        detected = datetime.fromisoformat(failure["detected_at"])

        if not symptom < failure_time <= detected:
            errors.append(
                f"Invalid failure timeline: {failure['failure_id']}"
            )

    for order in work_orders:

        if order["failure_id"] not in valid_failures:
            errors.append(
                f"Unknown failure in work order: {order['work_order_id']}"
            )

        if order["machine_id"] not in valid_machines:
            errors.append(
                f"Unknown machine in work order: {order['work_order_id']}"
            )

        if order["technician_id"] not in valid_technicians:
            errors.append(
                f"Unknown technician: {order['work_order_id']}"
            )

        opened = datetime.fromisoformat(order["opened_at"])
        started = datetime.fromisoformat(order["started_at"])
        completed = datetime.fromisoformat(order["completed_at"])

        if not opened <= started < completed:
            errors.append(
                f"Invalid work order timeline: {order['work_order_id']}"
            )

    seen_part_links = set()

    for link in work_order_parts:

        key = (link["work_order_id"], link["part_id"])

        if key in seen_part_links:
            errors.append(f"Duplicate work order part link: {key}")

        seen_part_links.add(key)

        if link["work_order_id"] not in valid_work_orders:
            errors.append(f"Unknown work order in parts: {key}")

        if link["part_id"] not in valid_parts:
            errors.append(f"Unknown part in work order: {key}")

        if link["quantity_used"] <= 0:
            errors.append(f"Invalid part quantity: {key}")

    return errors


def write_csv(file_path, rows):
    """Write a CSV file safely, replacing it after successful writing."""

    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        raise ValueError(f"Cannot write an empty dataset: {file_path}")

    temporary_path = file_path.with_suffix(file_path.suffix + ".tmp")

    try:
        with open(
            temporary_path,
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=list(rows[0].keys()),
            )

            writer.writeheader()
            writer.writerows(rows)

        temporary_path.replace(file_path)

    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def generate_work_order_status_history(work_orders):
    """Preserve each work order lifecycle as explicit status events."""

    history = []
    event_number = 1

    for order in work_orders:
        transitions = [
            ("NONE", "OPENED", order["opened_at"]),
            ("OPENED", "IN_PROGRESS", order["started_at"]),
            ("IN_PROGRESS", "COMPLETED", order["completed_at"]),
        ]

        for previous_status, new_status, timestamp in transitions:
            history.append({
                "status_event_id": f"WOST-{event_number:06d}",
                "work_order_id": order["work_order_id"],
                "machine_id": order["machine_id"],
                "previous_status": previous_status,
                "new_status": new_status,
                "event_timestamp": timestamp,
            })
            event_number += 1

    return history


def main():
    project_root = Path(__file__).resolve().parent.parent

    config_path = project_root / "config" / "config.json"

    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    output_dir = project_root / config["output_dir"]

    machine_file = output_dir / "machines.csv"

    if not machine_file.exists():
        raise FileNotFoundError(
            "machines.csv not found. Run master_data.py first."
        )

    machine_ids = read_machine_ids(machine_file)

    start_time = datetime.fromisoformat(
        config["telemetry_start"]
    )

    if start_time.tzinfo is None:
        raise ValueError("Start time must include a timezone.")

    start_time = start_time.astimezone(timezone.utc)

    days = config["telemetry_days"]

    generator = random.Random(config["seed"])

    failure_count = config["failure_events"]

    technicians = create_technicians()
    parts = create_parts()
    shifts = create_operating_shifts()

    failures = generate_failure_events(
        machine_ids,
        start_time,
        days,
        failure_count,
        generator,
    )

    work_orders = generate_work_orders(
        failures,
        technicians,
        generator,
    )

    work_order_parts = generate_work_order_parts(
        work_orders,
        parts,
        generator,
    )

    status_history = generate_work_order_status_history(work_orders)

    errors = validate_events(
        machine_ids,
        failures,
        work_orders,
        technicians,
        parts,
        work_order_parts,
    )

    if errors:
        print("EVENT VALIDATION FAILED")

        for error in errors:
            print("ERROR:", error)

        raise SystemExit(1)

    datasets = {
        "failure_events": failures,
        "maintenance_work_orders": work_orders,
        "technicians": technicians,
        "parts": parts,
        "work_order_parts": work_order_parts,
        "maintenance_status_history": status_history,
        "operating_shifts": shifts,
    }

    print("\n========== EVENT GENERATION SUMMARY ==========")

    for table_name, rows in datasets.items():
        output_file = output_dir / f"{table_name}.csv"
        write_csv(output_file, rows)

        print(f"{table_name}: {len(rows)} records")

    print("Validation errors: 0")
    print("RESULT: EVENTS GENERATED SUCCESSFULLY")


if __name__ == "__main__":
    main()
