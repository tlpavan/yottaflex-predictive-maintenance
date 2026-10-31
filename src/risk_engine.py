import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "config.json"

SENSOR_FILE = ROOT / "data" / "raw" / "sensors.csv"
TELEMETRY_FILE = ROOT / "data" / "raw" / "telemetry_enriched.csv"
WORK_ORDER_FILE = ROOT / "data" / "raw" / "maintenance_work_orders.csv"

SCORE_FILE = ROOT / "data" / "processed" / "machine_risk_scores.csv"
AUDIT_FILE = ROOT / "data" / "reports" / "risk_audit_log.csv"

ALGORITHM_VERSION = "1.0.0"

# Maximum risk points assigned to each sensor type.
SENSOR_WEIGHTS = {
    "TEMP": 25,
    "VIBRATION": 30,
    "CURRENT": 20,
    "PRESSURE": 15
}

# A sensor is considered abnormal when it crosses 65% of its
# configured range in the high direction, or falls below 35%
# of its range in the low direction.
HIGH_RISK_SENSORS = {"TEMP", "VIBRATION", "CURRENT"}
LOW_RISK_SENSORS = {"PRESSURE"}

WINDOW_HOURS = 24
MAINTENANCE_LOOKBACK_DAYS = 30


def parse_timestamp(value):
    """Convert an ISO timestamp into a timezone-aware datetime."""
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if timestamp.tzinfo is None:
        raise ValueError(f"Timestamp has no timezone: {value}")

    return timestamp.astimezone(timezone.utc)


def read_csv(path):
    """Read a CSV file and return its rows."""
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_sensor_metadata():
    """Load sensor details and group them by machine."""
    sensors = read_csv(SENSOR_FILE)
    metadata = {}

    for sensor in sensors:
        metadata[sensor["sensor_id"]] = {
            "machine_id": sensor["machine_id"],
            "sensor_type": sensor["sensor_type"],
            "unit": sensor["unit"],
            "min_value": float(sensor["min_value"]),
            "max_value": float(sensor["max_value"])
        }

    return metadata


def find_latest_telemetry_time():
    """Find the latest timestamp without loading telemetry into memory."""
    latest = None

    with TELEMETRY_FILE.open("r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            timestamp = parse_timestamp(row["timestamp"])

            if latest is None or timestamp > latest:
                latest = timestamp

    if latest is None:
        raise ValueError("Telemetry file contains no records.")

    return latest


def collect_recent_telemetry(sensor_metadata, window_start):
    """Stream telemetry and retain only the recent analysis window."""
    recent = defaultdict(list)

    with TELEMETRY_FILE.open("r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            timestamp = parse_timestamp(row["timestamp"])

            if timestamp < window_start:
                continue

            sensor_id = row["sensor_id"]

            if sensor_id not in sensor_metadata:
                continue

            value = float(row["value"])

            recent[sensor_id].append({
                "timestamp": timestamp,
                "value": value,
                "operating_state": row["operating_state"]
            })

    return recent


def analyse_sensor(sensor_id, metadata, readings):
    """Calculate abnormal readings, trend, and data-quality status."""
    sensor_type = metadata["sensor_type"]
    minimum = metadata["min_value"]
    maximum = metadata["max_value"]
    sensor_range = maximum - minimum

    if sensor_range <= 0:
        return {
            "points": 0,
            "reason": "Invalid configured sensor range",
            "quality_issue": True
        }

    if len(readings) < 20:
        return {
            "points": 0,
            "reason": "Insufficient recent sensor readings",
            "quality_issue": True
        }

    values = [reading["value"] for reading in readings]
    highest = max(values)
    lowest = min(values)

    # Check whether any reading is outside the configured sensor range.
    if any(value < minimum or value > maximum for value in values):
        return {
            "points": 0,
            "reason": "Sensor reading outside configured range",
            "quality_issue": True
        }

    points = 0
    reasons = []

    if sensor_type in HIGH_RISK_SENSORS:
        warning_limit = minimum + (sensor_range * 0.65)

        if highest >= warning_limit:
            points = SENSOR_WEIGHTS[sensor_type]
            reasons.append(f"{sensor_type} crossed its warning threshold")

    elif sensor_type in LOW_RISK_SENSORS:
        warning_limit = minimum + (sensor_range * 0.35)

        if lowest <= warning_limit:
            points = SENSOR_WEIGHTS[sensor_type]
            reasons.append(f"{sensor_type} fell below its warning threshold")

    # Compare the first half and second half of the recent readings.
    # A strong change in the risky direction earns half the sensor weight.
    if len(values) >= 6:
        midpoint = len(values) // 2
        first_average = sum(values[:midpoint]) / midpoint
        second_average = sum(values[midpoint:]) / len(values[midpoint:])

        change = second_average - first_average
        trend_limit = sensor_range * 0.08

        risky_trend = (
            sensor_type in HIGH_RISK_SENSORS and change >= trend_limit
        ) or (
            sensor_type in LOW_RISK_SENSORS and change <= -trend_limit
        )

        if risky_trend and points == 0:
            points = SENSOR_WEIGHTS[sensor_type] // 2
            reasons.append(f"{sensor_type} shows a concerning trend")

    return {
        "points": points,
        "reason": "; ".join(reasons) if reasons else "No threshold or trend alert",
        "quality_issue": False
    }


def count_recent_work_orders(latest_time):
    """Count maintenance work orders opened in the previous 30 days."""
    cutoff = latest_time - timedelta(days=MAINTENANCE_LOOKBACK_DAYS)
    counts = defaultdict(int)

    with WORK_ORDER_FILE.open("r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            opened_at = parse_timestamp(row["opened_at"])

            if cutoff <= opened_at <= latest_time:
                counts[row["machine_id"]] += 1

    return counts


def get_risk_band(score):
    """Convert a numeric score into a risk category."""
    if score >= 75:
        return "CRITICAL"
    if score >= 55:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def get_recommendation(risk_band):
    """Return an action appropriate to the risk category."""
    recommendations = {
        "CRITICAL": "Inspect machine immediately and plan corrective maintenance.",
        "HIGH": "Schedule priority inspection and review sensor trends.",
        "MEDIUM": "Monitor machine closely and review maintenance history.",
        "LOW": "Continue normal monitoring."
    }

    return recommendations[risk_band]


def calculate_machine_risk(
    machine_id,
    sensor_metadata,
    recent_readings,
    work_order_counts,
    latest_time
):
    """Calculate an explainable risk score for one machine."""
    sensor_points = {}
    reasons = []
    quality_issues = []

    machine_sensors = [
        (sensor_id, metadata)
        for sensor_id, metadata in sensor_metadata.items()
        if metadata["machine_id"] == machine_id
    ]

    operating_states = []

    for sensor_id, metadata in machine_sensors:
        readings = recent_readings.get(sensor_id, [])

        analysis = analyse_sensor(sensor_id, metadata, readings)

        sensor_type = metadata["sensor_type"]

        # If multiple sensors have the same type, use the highest
        # contribution rather than adding duplicate weights.
        sensor_points[sensor_type] = max(
            sensor_points.get(sensor_type, 0),
            analysis["points"]
        )

        if analysis["reason"] not in (
            "No threshold or trend alert",
            "Insufficient recent sensor readings",
            "Invalid configured sensor range",
            "Sensor reading outside configured range"
        ):
            reasons.append(analysis["reason"])

        if analysis["quality_issue"]:
            quality_issues.append(
                f"{sensor_id}: {analysis['reason']}"
            )

        operating_states.extend(
            reading["operating_state"] for reading in readings
        )

    sensor_score = sum(sensor_points.values())

    # Recent maintenance activity is a historical risk signal.
    work_order_count = work_order_counts.get(machine_id, 0)

    if work_order_count >= 2:
        maintenance_score = 10
        reasons.append("Two or more recent maintenance work orders")
    elif work_order_count == 1:
        maintenance_score = 5
        reasons.append("One recent maintenance work order")
    else:
        maintenance_score = 0

    # Operating context: sustained high running time adds a small
    # risk adjustment. It does not treat normal running as a fault.
    running_percentage = 0.0

    if operating_states:
        running_count = sum(
            state == "RUNNING" for state in operating_states
        )
        running_percentage = (
            running_count / len(operating_states)
        ) * 100

    operating_score = 5 if running_percentage > 80 else 0

    score = min(100, sensor_score + maintenance_score + operating_score)
    risk_band = get_risk_band(score)

    if not reasons:
        reasons.append("No significant risk indicators detected")

    quality_status = (
        "REVIEW_REQUIRED" if quality_issues else "OK"
    )

    return {
        "machine_id": machine_id,
        "risk_score": score,
        "risk_band": risk_band,
        "sensor_score": sensor_score,
        "maintenance_score": maintenance_score,
        "operating_context_score": operating_score,
        "running_percentage": round(running_percentage, 2),
        "recent_work_orders": work_order_count,
        "sensor_quality_status": quality_status,
        "quality_issues": "; ".join(quality_issues),
        "risk_reasons": "; ".join(reasons),
        "recommendation": get_recommendation(risk_band),
        "decision_timestamp": latest_time.isoformat()
    }


def write_results(rows, latest_time, window_start):
    """Write machine risk scores and the corresponding audit trail."""
    SCORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)

    score_fields = [
        "machine_id",
        "risk_score",
        "risk_band",
        "sensor_score",
        "maintenance_score",
        "operating_context_score",
        "running_percentage",
        "recent_work_orders",
        "sensor_quality_status",
        "quality_issues",
        "risk_reasons",
        "recommendation"
    ]

    audit_fields = [
        "decision_timestamp",
        "algorithm_version",
        "machine_id",
        "input_window_start",
        "input_window_end",
        "scoring_rule",
        "risk_score",
        "risk_band",
        "sensor_quality_status",
        "risk_reasons",
        "recommendation"
    ]

    with SCORE_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=score_fields)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                field: row[field] for field in score_fields
            })

    with AUDIT_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=audit_fields)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                "decision_timestamp": row["decision_timestamp"],
                "algorithm_version": ALGORITHM_VERSION,
                "machine_id": row["machine_id"],
                "input_window_start": window_start.isoformat(),
                "input_window_end": latest_time.isoformat(),
                "scoring_rule": (
                    "Sensor thresholds and trends + recent maintenance "
                    "+ operating context; see algorithm version 1.0.0"
                ),
                "risk_score": row["risk_score"],
                "risk_band": row["risk_band"],
                "sensor_quality_status": row["sensor_quality_status"],
                "risk_reasons": row["risk_reasons"],
                "recommendation": row["recommendation"]
            })


def main():
    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        config = json.load(file)

    print("========== MACHINE RISK ENGINE ==========")
    print("Loading sensor metadata...")

    sensor_metadata = load_sensor_metadata()
    machine_ids = sorted({
        metadata["machine_id"]
        for metadata in sensor_metadata.values()
    })

    print(f"Sensors loaded: {len(sensor_metadata)}")
    print(f"Machines found: {len(machine_ids)}")

    print("Finding latest telemetry timestamp...")
    latest_time = find_latest_telemetry_time()

    # Analyse the latest 24 hourly observations.
    window_start = latest_time - timedelta(hours=WINDOW_HOURS - 1)

    print("Collecting recent telemetry...")
    recent_readings = collect_recent_telemetry(
        sensor_metadata,
        window_start
    )

    print("Loading recent maintenance history...")
    work_order_counts = count_recent_work_orders(latest_time)

    print("Calculating machine risk scores...")
    results = []

    for machine_id in machine_ids:
        result = calculate_machine_risk(
            machine_id,
            sensor_metadata,
            recent_readings,
            work_order_counts,
            latest_time
        )
        results.append(result)

    write_results(results, latest_time, window_start)

    risk_counts = defaultdict(int)

    for row in results:
        risk_counts[row["risk_band"]] += 1

    quality_count = sum(
        row["sensor_quality_status"] != "OK"
        for row in results
    )

    print("\n========== RISK SUMMARY ==========")
    print(f"Machines scored: {len(results)}")
    print(f"LOW risk: {risk_counts['LOW']}")
    print(f"MEDIUM risk: {risk_counts['MEDIUM']}")
    print(f"HIGH risk: {risk_counts['HIGH']}")
    print(f"CRITICAL risk: {risk_counts['CRITICAL']}")
    print(f"Machines requiring sensor-quality review: {quality_count}")
    print(f"Risk scores saved: {SCORE_FILE.relative_to(ROOT)}")
    print(f"Audit log saved: {AUDIT_FILE.relative_to(ROOT)}")
    print("RESULT: RISK SCORING COMPLETED")


if __name__ == "__main__":
    main()