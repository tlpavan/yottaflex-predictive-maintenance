
import pytest

from src.scenario_injector import apply_failure_pattern


def test_increasing_pattern_increases_sensor_value():
    result = apply_failure_pattern(
        value=50,
        minimum=0,
        maximum=100,
        direction="increase",
        progress=0.5,
    )

    assert result > 50


def test_decreasing_pattern_decreases_sensor_value():
    result = apply_failure_pattern(
        value=50,
        minimum=0,
        maximum=100,
        direction="decrease",
        progress=0.5,
    )

    assert result < 50


def test_increasing_pattern_respects_maximum_limit():
    result = apply_failure_pattern(
        value=95,
        minimum=0,
        maximum=100,
        direction="increase",
        progress=1.0,
    )

    assert result <= 100


def test_decreasing_pattern_respects_minimum_limit():
    result = apply_failure_pattern(
        value=5,
        minimum=0,
        maximum=100,
        direction="decrease",
        progress=1.0,
    )

    assert result >= 0


def test_zero_progress_keeps_original_value():
    result = apply_failure_pattern(
        value=50,
        minimum=0,
        maximum=100,
        direction="increase",
        progress=0,
    )

    assert result == 50


def test_invalid_direction_raises_error():
    with pytest.raises(ValueError):
        apply_failure_pattern(
            value=50,
            minimum=0,
            maximum=100,
            direction="unknown",
            progress=0.5,
        )
