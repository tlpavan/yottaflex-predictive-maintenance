import csv
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
EXPORT = ROOT / "data" / "exports"
JSON_DIR = EXPORT / "json"

# Relational and event datasets.
# High-volume telemetry remains available in its original CSV files.
TABLES = [
    "plants",
    "production_lines",
    "machines",
    "sensors",
    "operating_shifts",
    "technicians",
    "parts",
    "failure_events",
    "maintenance_work_orders",
    "work_order_parts",
    "maintenance_status_history",
    "ground_truth",
]

PRIMARY_KEYS = {
    "plants": ["plant_id"],
    "production_lines": ["line_id"],
    "machines": ["machine_id"],
    "sensors": ["sensor_id"],
    "operating_shifts": ["shift_code"],
    "technicians": ["technician_id"],
    "parts": ["part_id"],
    "failure_events": ["failure_id"],
    "maintenance_work_orders": ["work_order_id"],
    "work_order_parts": ["work_order_id", "part_id"],
    "maintenance_status_history": ["status_event_id"],
}

FOREIGN_KEYS = {
    "production_lines": [
        ("plant_id", "plants", "plant_id")
    ],
    "machines": [
        ("line_id", "production_lines", "line_id")
    ],
    "sensors": [
        ("machine_id", "machines", "machine_id")
    ],
    "failure_events": [
        ("machine_id", "machines", "machine_id")
    ],
    "maintenance_work_orders": [
        ("failure_id", "failure_events", "failure_id"),
        ("machine_id", "machines", "machine_id"),
        ("technician_id", "technicians", "technician_id"),
    ],
    "work_order_parts": [
        ("work_order_id", "maintenance_work_orders", "work_order_id"),
        ("part_id", "parts", "part_id"),
    ],
    "maintenance_status_history": [
        ("work_order_id", "maintenance_work_orders", "work_order_id"),
        ("machine_id", "machines", "machine_id"),
    ],
    "ground_truth": [
        ("failure_id", "failure_events", "failure_id"),
        ("machine_id", "machines", "machine_id"),
    ],
}

INTEGER_COLUMNS = {
    "ground_truth_label",
    "quantity_used",
}

REAL_COLUMNS = {
    "min_value",
    "max_value",
    "unit_cost",
    "repair_duration_hours",
    "downtime_hours",
}


def convert_value(column, value):
    if value == "":
        return None

    if column in INTEGER_COLUMNS:
        return int(value)

    if column in REAL_COLUMNS:
        return float(value)

    return value


def export_json(table):
    source = RAW / f"{table}.csv"
    destination = JSON_DIR / f"{table}.json"

    count = 0

    with source.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)

        with destination.open("w", encoding="utf-8") as dst:
            dst.write("[\n")

            for row in reader:
                record = {
                    key: convert_value(key, value)
                    for key, value in row.items()
                }

                if count:
                    dst.write(",\n")

                json.dump(record, dst, ensure_ascii=False)
                count += 1

            dst.write("\n]\n")

    return count


def create_sqlite_database():
    database = EXPORT / "yottaflex_seed.sqlite"

    if database.exists():
        database.unlink()

    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys = ON")

    counts = {}

    try:
        for table in TABLES:
            source = RAW / f"{table}.csv"

            with source.open(
                "r", encoding="utf-8-sig", newline=""
            ) as file:
                reader = csv.DictReader(file)
                columns = reader.fieldnames

                if not columns:
                    raise ValueError(f"No columns found in {source}")

                definitions = []

                for column in columns:
                    if column in INTEGER_COLUMNS:
                        sql_type = "INTEGER"
                    elif column in REAL_COLUMNS:
                        sql_type = "REAL"
                    else:
                        sql_type = "TEXT"

                    definitions.append(
                        f'"{column}" {sql_type}'
                    )

                primary = PRIMARY_KEYS.get(table, [])

                if primary:
                    key_columns = ", ".join(
                        f'"{column}"' for column in primary
                    )
                    definitions.append(
                        f"PRIMARY KEY ({key_columns})"
                    )

                for column, parent, parent_column in FOREIGN_KEYS.get(
                    table, []
                ):
                    definitions.append(
                        f'FOREIGN KEY ("{column}") '
                        f'REFERENCES "{parent}"("{parent_column}")'
                    )

                schema = (
                    f'CREATE TABLE "{table}" '
                    f'({", ".join(definitions)})'
                )

                connection.execute(schema)

                placeholders = ", ".join("?" for _ in columns)
                column_names = ", ".join(
                    f'"{column}"' for column in columns
                )

                insert_sql = (
                    f'INSERT INTO "{table}" ({column_names}) '
                    f'VALUES ({placeholders})'
                )

                batch = []
                count = 0

                for row in reader:
                    values = tuple(
                        convert_value(column, row[column])
                        for column in columns
                    )
                    batch.append(values)

                    if len(batch) >= 1000:
                        connection.executemany(insert_sql, batch)
                        count += len(batch)
                        batch.clear()

                if batch:
                    connection.executemany(insert_sql, batch)
                    count += len(batch)

                counts[table] = count
                connection.commit()

                print(f"SQLite: {table}: {count} records")

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_errors:
            raise RuntimeError(
                f"SQL foreign-key violations: {foreign_key_errors[:10]}"
            )

        # Generate a portable SQL schema and seed-data dump.
        sql_file = EXPORT / "seed.sql"

        with sql_file.open("w", encoding="utf-8") as output:
            output.write("-- YottaFlex Predictive Maintenance SQL seed\n")
            output.write("-- High-volume telemetry remains in CSV files.\n\n")

            for statement in connection.iterdump():
                output.write(statement + ";\n")

        print("\nSQLite foreign-key validation: PASSED")
        print("SQLite database:", database)
        print("SQL seed:", sql_file)

    finally:
        connection.close()

    return counts


def main():
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT.mkdir(parents=True, exist_ok=True)

    print("========== JSON EXPORT ==========")

    json_counts = {}

    for table in TABLES:
        json_counts[table] = export_json(table)
        print(f"JSON: {table}: {json_counts[table]} records")

    print("\n========== SQLITE AND SQL EXPORT ==========")

    sql_counts = create_sqlite_database()

    if json_counts != sql_counts:
        raise RuntimeError(
            "JSON and SQL export record counts do not match."
        )

    print("\n========== EXPORT SUMMARY ==========")
    print("Tables exported:", len(TABLES))
    print("JSON and SQLite record counts match.")
    print("RESULT: DATA EXPORT COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
