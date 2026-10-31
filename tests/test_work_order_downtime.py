import random
from datetime import datetime

from src.event_generator import generate_work_orders


def test_downtime_is_failure_to_completion():
    failure = {
        "failure_id": "FAIL-000001",
        "machine_id": "MCH-LINE-PLT-001-001-001",
        "severity": "HIGH",
        "detected_at": "2026-07-01T00:00:00+00:00",
        "failure_at": "2026-07-01T00:00:00+00:00",
    }

    technicians = [
        {"technician_id": "TECH-001"}
    ]

    orders = generate_work_orders(
        [failure],
        technicians,
        random.Random(42)
    )

    order = orders[0]

    failure_time = datetime.fromisoformat(failure["failure_at"])
    start_time = datetime.fromisoformat(order["started_at"])
    completion_time = datetime.fromisoformat(order["completed_at"])

    expected_downtime = round(
        (completion_time - failure_time).total_seconds() / 3600,
        2
    )

    expected_repair = (
        completion_time - start_time
    ).total_seconds() / 3600

    assert order["downtime_hours"] == expected_downtime
    assert order["repair_duration_hours"] == expected_repair
    assert order["downtime_hours"] >= order["repair_duration_hours"]

def test_work_order_status_history():
    from src.event_generator import generate_work_order_status_history

    work_order = {
        "work_order_id": "WO-2026-000001",
        "machine_id": "MCH-LINE-PLT-001-001-001",
        "opened_at": "2026-07-01T00:00:00+00:00",
        "started_at": "2026-07-01T01:00:00+00:00",
        "completed_at": "2026-07-01T05:00:00+00:00",
    }

    history = generate_work_order_status_history([work_order])

    assert len(history) == 3

    assert [row["new_status"] for row in history] == [
        "OPENED",
        "IN_PROGRESS",
        "COMPLETED",
    ]

    assert [row["previous_status"] for row in history] == [
        "NONE",
        "OPENED",
        "IN_PROGRESS",
    ]

    assert all(
        row["work_order_id"] == work_order["work_order_id"]
        for row in history
    )
