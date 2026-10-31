
import csv
import json

from datetime import datetime
from pathlib import Path


class DataValidator:

    def __init__(self, data_dir, config):
        self.data_dir = Path(data_dir)
        self.config = config
        self.errors = []
        self.warnings = []

    def add_error(self, message):
        if len(self.errors) < 50:
            self.errors.append(message)

    def read_small_csv(self, filename):
        path = self.data_dir / filename

        if not path.exists():
            self.add_error(f"Missing file: {filename}")
            return []

        with open(path, "r", newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def validate_master_relationships(self):
        print("Checking master data relationships...")

        machines = self.read_small_csv("machines.csv")
        sensors = self.read_small_csv("sensors.csv")
        plants = self.read_small_csv("plants.csv")
        lines = self.read_small_csv("production_lines.csv")

        plant_ids = {row["plant_id"] for row in plants}
        line_ids = {row["line_id"] for row in lines}
        machine_ids = {row["machine_id"] for row in machines}

        sensor_ids = set()

        for row in lines:
            if row["plant_id"] not in plant_ids:
                self.add_error(
                    f"Invalid plant reference in line {row['line_id']}"
                )

        for row in machines:
            if row["line_id"] not in line_ids:
                self.add_error(
                    f"Invalid line reference in machine {row['machine_id']}"
                )

        sensor_details = {}

        for row in sensors:
            sensor_id = row["sensor_id"]

            if sensor_id in sensor_ids:
                self.add_error(f"Duplicate sensor ID: {sensor_id}")

            sensor_ids.add(sensor_id)

            if row["machine_id"] not in machine_ids:
                self.add_error(
                    f"Invalid machine reference in sensor {sensor_id}"
                )

            minimum = float(row["min_value"])
            maximum = float(row["max_value"])

            if minimum >= maximum:
                self.add_error(
                    f"Invalid sensor limits: {sensor_id}"
                )

            sensor_details[sensor_id] = {
                "machine_id": row["machine_id"],
                "sensor_type": row["sensor_type"],
                "unit": row["unit"],
                "minimum": minimum,
                "maximum": maximum,
            }

        return machine_ids, sensor_details

    def validate_failure_events(self, machine_ids):
        print("Checking failure events...")

        failures = self.read_small_csv("failure_events.csv")

        failure_details = {}
        failure_ids = set()

        for row in failures:
            failure_id = row["failure_id"]

            if failure_id in failure_ids:
                self.add_error(f"Duplicate failure ID: {failure_id}")

            failure_ids.add(failure_id)

            if row["machine_id"] not in machine_ids:
                self.add_error(
                    f"Invalid machine in failure {failure_id}"
                )

            start = datetime.fromisoformat(row["symptom_start_at"])
            failure = datetime.fromisoformat(row["failure_at"])

            if start.tzinfo is None or failure.tzinfo is None:
                self.add_error(
                    f"Missing timezone in failure {failure_id}"
                )

            if start >= failure:
                self.add_error(
                    f"Invalid failure timeline: {failure_id}"
                )

            failure_details[failure_id] = {
                "machine_id": row["machine_id"],
                "start": start,
                "failure": failure,
            }

        return failure_details

    def validate_work_orders(self, machine_ids, failure_details):
        print("Checking maintenance work orders...")

        work_orders = self.read_small_csv(
            "maintenance_work_orders.csv"
        )

        technicians = self.read_small_csv("technicians.csv")

        technician_ids = {
            row["technician_id"] for row in technicians
        }

        work_order_ids = set()

        for row in work_orders:
            work_order_id = row["work_order_id"]

            if work_order_id in work_order_ids:
                self.add_error(
                    f"Duplicate work order: {work_order_id}"
                )

            work_order_ids.add(work_order_id)

            if row["machine_id"] not in machine_ids:
                self.add_error(
                    f"Invalid machine in work order {work_order_id}"
                )

            if row["failure_id"] not in failure_details:
                self.add_error(
                    f"Invalid failure reference in {work_order_id}"
                )

            elif (
                failure_details[row["failure_id"]]["machine_id"]
                != row["machine_id"]
            ):
                self.add_error(
                    f"Machine mismatch in work order {work_order_id}"
                )

            if row["technician_id"] not in technician_ids:
                self.add_error(
                    f"Invalid technician in {work_order_id}"
                )

            try:
                opened_at = datetime.fromisoformat(row["opened_at"])
                started_at = datetime.fromisoformat(row["started_at"])
                completed_at = datetime.fromisoformat(row["completed_at"])

                if not (opened_at <= started_at <= completed_at):
                    self.add_error(
                        f"Invalid maintenance chronology: {work_order_id}"
                    )

                if row["failure_id"] in failure_details:
                    failure_at = failure_details[row["failure_id"]]["failure"]

                    if opened_at < failure_at:
                        self.add_error(
                            f"Work order opened before failure: {work_order_id}"
                        )

                    expected_downtime = round(
                        (completed_at - failure_at).total_seconds() / 3600,
                        2
                    )

                    recorded_downtime = float(row["downtime_hours"])

                    if abs(expected_downtime - recorded_downtime) > 0.01:
                        self.add_error(
                            f"Downtime mismatch: {work_order_id}"
                        )

                expected_repair = (
                    completed_at - started_at
                ).total_seconds() / 3600

                recorded_repair = float(row["repair_duration_hours"])

                if abs(expected_repair - recorded_repair) > 0.01:
                    self.add_error(
                        f"Repair duration mismatch: {work_order_id}"
                    )

            except (ValueError, TypeError, KeyError):
                self.add_error(
                    f"Invalid maintenance timestamp or duration: {work_order_id}"
                )

        return len(work_orders)

    def validate_work_order_status_history(self):
        print("Checking maintenance status history...")

        work_orders = self.read_small_csv("maintenance_work_orders.csv")
        history = self.read_small_csv("maintenance_status_history.csv")

        order_map = {
            row["work_order_id"]: row for row in work_orders
        }

        event_ids = set()
        events_by_order = {}

        for event in history:
            event_id = event["status_event_id"]
            order_id = event["work_order_id"]

            if event_id in event_ids:
                self.add_error(f"Duplicate status event: {event_id}")

            event_ids.add(event_id)

            if order_id not in order_map:
                self.add_error(
                    f"Invalid work order in status history: {order_id}"
                )
                continue

            order = order_map[order_id]

            if event["machine_id"] != order["machine_id"]:
                self.add_error(
                    f"Machine mismatch in status event: {event_id}"
                )

            try:
                timestamp = datetime.fromisoformat(
                    event["event_timestamp"]
                )

                if timestamp.tzinfo is None:
                    self.add_error(
                        f"Missing timezone in status event: {event_id}"
                    )

                events_by_order.setdefault(order_id, []).append(
                    (timestamp, event)
                )

            except ValueError:
                self.add_error(
                    f"Invalid status event timestamp: {event_id}"
                )

        for order_id, order in order_map.items():
            actual = sorted(
                events_by_order.get(order_id, []),
                key=lambda item: item[0],
            )

            expected = [
                ("NONE", "OPENED", order["opened_at"]),
                ("OPENED", "IN_PROGRESS", order["started_at"]),
                ("IN_PROGRESS", "COMPLETED", order["completed_at"]),
            ]

            if len(actual) != 3:
                self.add_error(
                    f"Expected three lifecycle events for {order_id}"
                )
                continue

            for actual_item, expected_item in zip(actual, expected):
                timestamp, event = actual_item
                previous_status, new_status, expected_time = expected_item

                if (
                    event["previous_status"] != previous_status
                    or event["new_status"] != new_status
                ):
                    self.add_error(
                        f"Invalid status transition in {order_id}"
                    )

                try:
                    if timestamp != datetime.fromisoformat(expected_time):
                        self.add_error(
                            f"Status timestamp mismatch in {order_id}"
                        )
                except ValueError:
                    self.add_error(
                        f"Invalid work order timestamp in {order_id}"
                    )

        return len(history)

    def validate_telemetry_and_ground_truth(
        self,
        sensor_details,
        failure_details,
    ):
        print("Checking telemetry and ground truth...")

        telemetry_path = self.data_dir / "telemetry_enriched.csv"
        ground_truth_path = self.data_dir / "ground_truth.csv"

        if not telemetry_path.exists():
            self.add_error("Missing telemetry_enriched.csv")
            return 0, 0

        if not ground_truth_path.exists():
            self.add_error("Missing ground_truth.csv")
            return 0, 0

        ground_truth = {}

        with open(
            ground_truth_path, "r", newline="", encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:
                telemetry_id = row["telemetry_id"]

                if telemetry_id in ground_truth:
                    self.add_error(
                        f"Duplicate ground-truth telemetry ID: {telemetry_id}"
                    )
                    continue

                if row["failure_id"] not in failure_details:
                    self.add_error(
                        f"Unknown failure in ground truth: {row['failure_id']}"
                    )
                    continue

                if row["ground_truth_label"] != "1":
                    self.add_error(
                        f"Invalid ground-truth label: {telemetry_id}"
                    )

                ground_truth[telemetry_id] = row

        telemetry_count = 0
        matched_count = 0

        with open(
            telemetry_path, "r", newline="", encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            required = {
                "telemetry_id",
                "sensor_id",
                "machine_id",
                "timestamp",
                "sensor_type",
                "value",
                "unit",
            }

            if not reader.fieldnames or not required.issubset(
                reader.fieldnames
            ):
                self.add_error(
                    "Telemetry CSV is missing required columns."
                )
                return 0, len(ground_truth)

            for row in reader:
                telemetry_count += 1

                telemetry_id = row["telemetry_id"]
                sensor_id = row["sensor_id"]

                sensor = sensor_details.get(sensor_id)

                if sensor is None:
                    self.add_error(
                        f"Unknown sensor in telemetry: {sensor_id}"
                    )
                    continue

                if row["machine_id"] != sensor["machine_id"]:
                    self.add_error(
                        f"Machine mismatch: {telemetry_id}"
                    )

                if row["sensor_type"] != sensor["sensor_type"]:
                    self.add_error(
                        f"Sensor type mismatch: {telemetry_id}"
                    )

                if row["unit"] != sensor["unit"]:
                    self.add_error(
                        f"Sensor unit mismatch: {telemetry_id}"
                    )

                try:
                    value = float(row["value"])

                    if not sensor["minimum"] <= value <= sensor["maximum"]:
                        self.add_error(
                            f"Sensor value outside limits: {telemetry_id}"
                        )

                    datetime.fromisoformat(row["timestamp"])

                except (ValueError, TypeError):
                    self.add_error(
                        f"Invalid telemetry value or timestamp: {telemetry_id}"
                    )
                    continue

                truth = ground_truth.get(telemetry_id)

                if truth is not None:
                    matched_count += 1

                    if truth["machine_id"] != row["machine_id"]:
                        self.add_error(
                            f"Ground-truth machine mismatch: {telemetry_id}"
                        )

                    event = failure_details[truth["failure_id"]]

                    timestamp = datetime.fromisoformat(row["timestamp"])

                    if not (
                        event["start"] <= timestamp < event["failure"]
                    ):
                        self.add_error(
                            f"Ground-truth timestamp outside failure window: "
                            f"{telemetry_id}"
                        )

                    if (
                        truth["symptom_start_at"]
                        != event["start"].isoformat()
                        or truth["failure_at"]
                        != event["failure"].isoformat()
                    ):
                        self.add_error(
                            f"Ground-truth timeline mismatch: {telemetry_id}"
                        )

        unmatched = len(ground_truth) - matched_count

        if unmatched:
            self.add_error(
                f"{unmatched} ground-truth records have no telemetry match."
            )

        return telemetry_count, len(ground_truth)

    def run(self):
        print("\n========== DATA QUALITY VALIDATION ==========\n")

        machine_ids, sensor_details = (
            self.validate_master_relationships()
        )

        failure_details = self.validate_failure_events(machine_ids)

        work_order_count = self.validate_work_orders(
            machine_ids,
            failure_details,
        )

        status_history_count = self.validate_work_order_status_history()

        telemetry_count, ground_truth_count = (
            self.validate_telemetry_and_ground_truth(
                sensor_details,
                failure_details,
            )
        )

        expected_count = (
            len(sensor_details)
            * self.config["telemetry_days"]
            * 24
            * 60
            // self.config["telemetry_interval_minutes"]
        )

        if telemetry_count != expected_count:
            self.add_error(
                f"Expected {expected_count} telemetry records, "
                f"found {telemetry_count}."
            )

        print("\n========== VALIDATION SUMMARY ==========")
        print(f"Machines: {len(machine_ids)}")
        print(f"Sensors: {len(sensor_details)}")
        print(f"Failure events: {len(failure_details)}")
        print(f"Work orders: {work_order_count}")
        print(f"Maintenance status events: {status_history_count}")
        print(f"Telemetry records: {telemetry_count:,}")
        print(f"Ground-truth records: {ground_truth_count:,}")
        print(f"Validation errors: {len(self.errors)}")

        if self.errors:
            print("\nERROR DETAILS:")

            for error in self.errors:
                print(f"- {error}")

            print("\nRESULT: VALIDATION FAILED")
            return False

        print("\nRESULT: ALL CHECKS PASSED")
        return True



def main():
    project_root = Path(__file__).resolve().parent.parent

    with open(
        project_root / "config" / "config.json",
        "r",
        encoding="utf-8",
    ) as file:
        config = json.load(file)

    validator = DataValidator(
        data_dir=project_root / config["output_dir"],
        config=config,
    )

    # Run the original data validation
    success = validator.run()

    if not success:
        raise SystemExit(1)

    # Run the additional validation checks
    from src.extended_validator import ExtendedDataValidator

    extended_validator = ExtendedDataValidator(project_root, config)

    if not extended_validator.run():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
