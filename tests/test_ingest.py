from __future__ import annotations

from pathlib import Path

from villarrica_forecaster.data.html_xls import parse_html_xls
from villarrica_forecaster.data.ingest import (
    RawTable,
    canonicalize_table,
    classify_quality,
    date_table_validation,
    parse_date_value,
    parse_date_value_with_context,
    parse_measurement_column,
    raw_file_hash_collisions,
)


def test_parse_html_xls_rows(tmp_path: Path) -> None:
    path = tmp_path / "sample.xls"
    path.write_text(
        "<table><tr><th>Fecha-Hora de Medicion</th><th>Clorofila (ug/L)Media</th></tr>"
        "<tr><td>01/02/2024</td><td>1.23</td></tr></table>",
        encoding="utf-8",
    )
    parsed = parse_html_xls(path)
    assert parsed.rows == [
        ["Fecha-Hora de Medicion", "Clorofila (ug/L)Media"],
        ["01/02/2024", "1.23"],
    ]


def test_parse_date_value_supports_spanish_dates_and_excel_serials() -> None:
    assert parse_date_value("09/02/2025").isoformat() == "2025-02-09"
    assert parse_date_value("44204").isoformat() == "2021-01-08"


def test_parse_date_value_with_context_records_encoding() -> None:
    slash = parse_date_value_with_context("09/02/2025")
    serial = parse_date_value_with_context("44204")

    assert slash.value.isoformat() == "2025-02-09"
    assert slash.encoding == "slash_dmy"
    assert serial.value.isoformat() == "2021-01-08"
    assert serial.encoding == "excel_serial"


def test_canonicalize_table_repairs_mixed_excel_serial_day_month_dates(tmp_path: Path) -> None:
    path = tmp_path / "Fico VR litoral Pucón.xlsx"
    path.write_text("", encoding="utf-8")
    raw_table = RawTable(
        path=path,
        kind="xlsx",
        station_id="pucon",
        station_name="Pucón",
        sheet_name="Hoja1",
        rows=[
            ["Fecha-Hora de Medicion", "Clorofila (ug/L)Media"],
            ["28/07/2021", "1.8"],
            ["29/07/2021", "1.7"],
            ["30/07/2021", "1.6"],
            ["31/07/2021", "1.5"],
            ["44204", "1.4"],
            ["44235", "1.3"],
            ["44263", "1.2"],
            ["13/08/2021", "1.1"],
        ],
        workbook_sheets=["Hoja1"],
    )

    canonical = canonicalize_table(raw_table, tmp_path, source_file_sha256="abc")
    repaired = canonical[canonical["raw_date_value"].eq("44204")].iloc[0]

    assert repaired["date"] == "2021-08-01"
    assert repaired["date_parse_method"] == "excel_serial_dmy_swapped"
    assert repaired["date_validation_status"] == "repaired_mixed_excel_serial_dates"
    assert bool(repaired["is_model_eligible"])


def test_date_table_validation_keeps_true_excel_serials_when_monotonic(tmp_path: Path) -> None:
    path = tmp_path / "serial_dates.xlsx"
    path.write_text("", encoding="utf-8")
    raw_table = RawTable(
        path=path,
        kind="xlsx",
        station_id="pucon",
        station_name="Pucón",
        sheet_name="Hoja1",
        rows=[
            ["Fecha-Hora de Medicion", "Clorofila (ug/L)Media"],
            ["45475", "3.7"],
            ["45476", "3.6"],
        ],
        workbook_sheets=["Hoja1"],
    )

    canonical = canonicalize_table(raw_table, tmp_path, source_file_sha256="abc")
    validation = date_table_validation(raw_table)

    assert canonical.iloc[0]["date"] == "2024-07-02"
    assert canonical.iloc[0]["date_parse_method"] == "excel_serial"
    assert validation["date_validation_status"] == "ok"


def test_parse_measurement_column_normalizes_spanish_header() -> None:
    spec = parse_measurement_column("LAGO VILLARRClorofila (ug/L)Media")
    assert spec == {
        "raw_column": "LAGO VILLARRClorofila (ug/L)Media",
        "variable": "chlorophyll_a",
        "statistic": "mean",
        "raw_unit": "ug/L",
        "unit": "ug/L",
    }


def test_classify_quality_flags_sentinel_and_impossible_values() -> None:
    assert classify_quality("chlorophyll_a", -99.0) == "invalid_sentinel"
    assert classify_quality("turbidity", -0.5) == "invalid_negative"
    assert classify_quality("water_temperature", -1.0) == "implausible_temperature"
    assert classify_quality("chlorophyll_a", 3.2) == "ok"


def test_raw_file_hash_collisions_flags_same_file_across_stations() -> None:
    import pandas as pd

    inventory = pd.DataFrame(
        [
            {
                "file_sha256": "abc",
                "source_file": "raw_data/la_poza/same.xls",
                "station_id": "la_poza",
                "row_count_raw": 10,
                "date_min": "2024-01-01",
                "date_max": "2024-01-10",
            },
            {
                "file_sha256": "abc",
                "source_file": "raw_data/pucon/same.xls",
                "station_id": "pucon",
                "row_count_raw": 10,
                "date_min": "2024-01-01",
                "date_max": "2024-01-10",
            },
        ]
    )

    collisions = raw_file_hash_collisions(inventory)

    assert len(collisions) == 1
    assert collisions.iloc[0]["station_count"] == 2


def test_canonicalize_table_quarantines_station_hash_collision(tmp_path: Path) -> None:
    path = tmp_path / "station.xls"
    path.write_text("", encoding="utf-8")
    raw_table = RawTable(
        path=path,
        kind="html_xls",
        station_id="pucon",
        station_name="Pucón",
        sheet_name="html_table_1",
        rows=[
            ["Fecha-Hora de Medicion", "Clorofila (ug/L)Media"],
            ["09/02/2025", "1.23"],
        ],
        workbook_sheets=["html_table_1"],
    )

    canonical = canonicalize_table(
        raw_table,
        tmp_path,
        source_file_sha256="abc",
        file_collision_reason="same_raw_file_assigned_to_multiple_stations",
        file_collision_station_count=2,
    )

    row = canonical.iloc[0]
    assert row["date_parse_method"] == "slash_dmy"
    assert bool(row["is_station_assignment_suspect"])
    assert not bool(row["is_model_eligible"])
    assert row["model_exclusion_reason"] == "same_raw_file_assigned_to_multiple_stations"
