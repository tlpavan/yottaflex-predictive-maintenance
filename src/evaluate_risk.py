import csv
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import pandas as pd

from src.risk_engine import (
    load_sensor_metadata,
    calculate_machine_risk,
    count_recent_work_orders,
    parse_timestamp,
)

ROOT = Path(__file__).resolve().parent.parent
TELEMETRY_FILE = ROOT / "data/raw/telemetry_enriched.csv"
FAILURE_FILE = ROOT / "data/raw/failure_events.csv"
PREDICTIONS_FILE = ROOT / "data/reports/risk_evaluation_predictions.csv"
METRICS_FILE = ROOT / "data/reports/risk_evaluation_metrics.csv"
REPORT_FILE = ROOT / "docs/RISK_EVALUATION.md"

FEATURE_WINDOW_HOURS = 24
PREDICTION_HORIZON_HOURS = 24
HIGH_RISK_THRESHOLD = 55
WATCH_THRESHOLD = 25


def load_failures():
    failures = defaultdict(list)

    with FAILURE_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            failures[row["machine_id"]].append(
                parse_timestamp(row["failure_at"])
            )

    for machine_id in failures:
        failures[machine_id].sort()

    return failures


def calculate_classification_metrics(rows, threshold, threshold_name):
    tp = fp = tn = fn = 0

    for row in rows:
        actual = int(row["actual_failure_next_24h"])
        predicted = int(float(row["risk_score"]) >= threshold)

        if actual == 1 and predicted == 1:
            tp += 1
        elif actual == 0 and predicted == 1:
            fp += 1
        elif actual == 0 and predicted == 0:
            tn += 1
        else:
            fn += 1

    total = tp + fp + tn + fn

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    accuracy = (tp + tn) / total if total else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    return {
        "threshold_name": threshold_name,
        "risk_score_threshold": threshold,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "specificity": round(specificity, 4),
        "false_positive_rate": round(1 - specificity, 4),
        "evaluation_samples": total,
    }


def main():
    print("========== HISTORICAL RISK EVALUATION ==========")

    print("Loading sensor metadata...")
    sensor_metadata = load_sensor_metadata()

    machine_ids = sorted({
        metadata["machine_id"]
        for metadata in sensor_metadata.values()
    })

    print(f"Sensors: {len(sensor_metadata)}")
    print(f"Machines: {len(machine_ids)}")

    print("Loading telemetry...")
    telemetry = pd.read_csv(
        TELEMETRY_FILE,
        usecols=[
            "sensor_id",
            "machine_id",
            "timestamp",
            "value",
            "operating_state",
        ],
    )

    telemetry["timestamp"] = pd.to_datetime(
        telemetry["timestamp"],
        utc=True,
        errors="raise",
    )

    telemetry["value"] = pd.to_numeric(
        telemetry["value"],
        errors="raise",
    )

    days = sorted(
        pd.Timestamp(value)
        for value in telemetry["timestamp"].dt.floor("D").unique()
    )

    if len(days) < 2:
        raise ValueError("At least two telemetry days are required.")

    print(f"Telemetry days: {len(days)}")

    print("Loading failure outcomes...")
    failures = load_failures()

    prediction_rows = []

    # The final telemetry day cannot be evaluated because
    # its following 24-hour outcome window is unavailable.
    evaluation_days = days[:-1]

    for day_number, day in enumerate(evaluation_days, start=1):

        decision_time = (
            day + pd.Timedelta(hours=23)
        ).to_pydatetime()

        horizon_end = (
            decision_time
            + timedelta(hours=PREDICTION_HORIZON_HOURS)
        )

        # Use only readings from this decision day's 24-hour window.
        daily_rows = telemetry.loc[
            (telemetry["timestamp"] >= day)
            & (
                telemetry["timestamp"]
                <= day + pd.Timedelta(hours=23)
            )
        ].sort_values(["sensor_id", "timestamp"])

        sensor_counts = daily_rows["sensor_id"].value_counts()

        if (
            len(sensor_counts) != len(sensor_metadata)
            or not (sensor_counts == FEATURE_WINDOW_HOURS).all()
        ):
            raise ValueError(
                f"Incomplete 24-hour telemetry window on {day.date()}"
            )

        recent_readings = defaultdict(list)

        for row in daily_rows.itertuples(index=False):
            recent_readings[row.sensor_id].append({
                "timestamp": row.timestamp.to_pydatetime(),
                "value": float(row.value),
                "operating_state": row.operating_state,
            })

        # The existing function includes only work orders opened
        # on or before the historical decision timestamp.
        work_order_counts = count_recent_work_orders(decision_time)

        for machine_id in machine_ids:

            result = calculate_machine_risk(
                machine_id,
                sensor_metadata,
                recent_readings,
                work_order_counts,
                decision_time,
            )

            # Failure events are used only as future outcomes.
            # They are never passed into the risk-scoring function.
            actual_failure = int(
                any(
                    decision_time < failure_time <= horizon_end
                    for failure_time in failures.get(machine_id, [])
                )
            )

            prediction_rows.append({
                "machine_id": machine_id,
                "decision_timestamp": decision_time.isoformat(),
                "risk_score": result["risk_score"],
                "risk_band": result["risk_band"],
                "sensor_score": result["sensor_score"],
                "maintenance_score": result["maintenance_score"],
                "operating_context_score": result[
                    "operating_context_score"
                ],
                "actual_failure_next_24h": actual_failure,
            })

        if day_number % 15 == 0 or day_number == len(evaluation_days):
            print(
                f"Completed evaluation day {day_number}/"
                f"{len(evaluation_days)}"
            )

    print("\nCalculating classification metrics...")

    metrics = [
        calculate_classification_metrics(
            prediction_rows,
            HIGH_RISK_THRESHOLD,
            "HIGH_OR_CRITICAL",
        ),
        calculate_classification_metrics(
            prediction_rows,
            WATCH_THRESHOLD,
            "MEDIUM_OR_HIGH_OR_CRITICAL",
        ),
    ]

    PREDICTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(prediction_rows).to_csv(
        PREDICTIONS_FILE,
        index=False,
    )

    pd.DataFrame(metrics).to_csv(
        METRICS_FILE,
        index=False,
    )

    positive_samples = sum(
        row["actual_failure_next_24h"]
        for row in prediction_rows
    )

    report = [
        "# Historical Risk Evaluation",
        "",
        "## Evaluation methodology",
        "",
        f"- Decision frequency: once per UTC day.",
        f"- Feature window: {FEATURE_WINDOW_HOURS} hours.",
        f"- Prediction horizon: next {PREDICTION_HORIZON_HOURS} hours.",
        "- Target: a machine failure occurring strictly after the "
        "decision time and within the prediction horizon.",
        "- Maintenance history: only work orders opened by the "
        "decision timestamp are included.",
        "- Failure events are used only to determine evaluation "
        "outcomes, never as scoring features.",
        "- The final telemetry day is excluded because its future "
        "24-hour outcome window is unavailable.",
        "",
        "## Results",
        "",
        "| Threshold | TP | FP | TN | FN | Precision | Recall | F1 | Accuracy |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for item in metrics:
        report.append(
            f"| {item['threshold_name']} "
            f"| {item['true_positives']} "
            f"| {item['false_positives']} "
            f"| {item['true_negatives']} "
            f"| {item['false_negatives']} "
            f"| {item['precision']:.4f} "
            f"| {item['recall']:.4f} "
            f"| {item['f1_score']:.4f} "
            f"| {item['accuracy']:.4f} |"
        )

    report.extend([
        "",
        f"- Evaluation samples: {len(prediction_rows)}.",
        f"- Positive outcomes: {positive_samples}.",
        "",
        "## Limitations",
        "",
        "- This is a backtest against synthetic generated failures, "
        "not real industrial failure data.",
        "- Risk scores are heuristic decision-support scores, "
        "not calibrated probabilities.",
        "- Results depend on the selected 24-hour prediction horizon "
        "and risk thresholds.",
        "- The evaluation does not establish performance on "
        "independent real-world data.",
    ])

    REPORT_FILE.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    print("\n========== EVALUATION SUMMARY ==========")
    print(f"Evaluation samples: {len(prediction_rows)}")
    print(f"Positive outcomes: {positive_samples}")

    for item in metrics:
        print(f"\n{item['threshold_name']}")
        print(f"Precision: {item['precision']}")
        print(f"Recall: {item['recall']}")
        print(f"F1-score: {item['f1_score']}")
        print(f"Accuracy: {item['accuracy']}")
        print(f"Specificity: {item['specificity']}")
        print(f"False-positive rate: {item['false_positive_rate']}")

    print("\nReports created:")
    print(PREDICTIONS_FILE)
    print(METRICS_FILE)
    print(REPORT_FILE)
    print("\nRESULT: HISTORICAL RISK EVALUATION COMPLETED")


if __name__ == "__main__":
    main()
