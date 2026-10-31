from src.extended_validator import (
    detect_exception_condition,
    infer_missing_intervals,
)


SENSORS = {
    "SNS-001-TEMP-01": {
        "unit": "C",
        "minimum": 20.0,
        "maximum": 120.0,
    }
}


def test_unknown_sensor_is_detected():
    row = {"sensor_id": "SNS-UNKNOWN-001"}
    assert detect_exception_condition(
        "UNKNOWN_SENSOR", row, SENSORS, 60
    ) is True


def test_invalid_sensor_unit_is_detected():
    row = {
        "sensor_id": "SNS-001-TEMP-01",
        "unit": "INVALID_UNIT",
        "value": "70",
    }
    assert detect_exception_condition(
        "INVALID_UNIT_OR_RANGE", row, SENSORS, 60
    ) is True


def test_out_of_range_sensor_value_is_detected():
    row = {
        "sensor_id": "SNS-001-TEMP-01",
        "unit": "C",
        "value": "130",
    }
    assert detect_exception_condition(
        "INVALID_UNIT_OR_RANGE", row, SENSORS, 60
    ) is True


def test_failure_before_symptom_is_detected():
    row = {
        "symptom_start_at": "2026-07-01T03:00:00+00:00",
        "failure_at": "2026-07-01T02:00:00+00:00",
        "detected_at": "2026-07-01T04:00:00+00:00",
    }
    assert detect_exception_condition(
        "FAILURE_BEFORE_SYMPTOM", row, SENSORS, 60
    ) is True


def test_maintenance_end_before_start_is_detected():
    row = {
        "started_at": "2026-07-01T04:00:00+00:00",
        "completed_at": "2026-07-01T03:00:00+00:00",
    }
    assert detect_exception_condition(
        "MAINTENANCE_END_BEFORE_START", row, SENSORS, 60
    ) is True


def test_three_hour_gap_means_two_missing_hourly_readings():
    assert infer_missing_intervals(
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T03:00:00+00:00",
        60,
    ) == 2


def test_adjacent_hourly_readings_have_no_gap():
    assert infer_missing_intervals(
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T01:00:00+00:00",
        60,
    ) == 0


def test_gap_fixture_is_detected_from_timestamps_not_missing_intervals_field():
    row = {
        "last_observed_at": "2026-07-01T00:00:00+00:00",
        "next_observed_at": "2026-07-01T03:00:00+00:00",
        # Deliberately wrong field: validator must not trust this value.
        "missing_intervals": "0",
    }
    assert detect_exception_condition(
        "MISSING_TELEMETRY_GAP", row, SENSORS, 60
    ) is True


def test_irregular_gap_is_not_counted_as_aligned_missing_slots():
    assert infer_missing_intervals(
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T01:30:00+00:00",
        60,
    ) is None
