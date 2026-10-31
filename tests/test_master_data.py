from src.master_data import (
    generate_master_data,
    validate_master_data
)


def get_test_config():

    return {
        "seed": 20261022,
        "plants": 2,
        "lines": 4,
        "machines": 8,
        "sensors": 40
    }


# Test 1: Check record counts

def test_entity_counts():

    tables = generate_master_data(
        get_test_config()
    )

    assert len(tables["plants"]) == 2
    assert len(tables["production_lines"]) == 4
    assert len(tables["machines"]) == 8
    assert len(tables["sensors"]) == 40


# Test 2: Check relationships

def test_foreign_keys_are_valid():

    tables = generate_master_data(
        get_test_config()
    )

    errors = validate_master_data(tables)

    assert errors == []


# Test 3: Check deterministic generation

def test_same_config_produces_same_data():

    first = generate_master_data(
        get_test_config()
    )

    second = generate_master_data(
        get_test_config()
    )

    assert first == second


# Test 4: Detect invalid foreign key

def test_invalid_foreign_key():

    tables = {
        "plants": [
            {"plant_id": "PLT-001"}
        ],

        "production_lines": [
            {
                "line_id": "LINE-PLT-001-001",
                "plant_id": "PLT-999"
            }
        ],

        "machines": [],

        "sensors": []
    }

    errors = validate_master_data(tables)

    assert any(
        "Invalid plant_id" in error
        for error in errors
    )