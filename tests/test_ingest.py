from __future__ import annotations

from pathlib import Path

from villarrica_forecaster.data.html_xls import parse_html_xls
from villarrica_forecaster.data.ingest import (
    classify_quality,
    parse_date_value,
    parse_measurement_column,
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


def test_parse_measurement_column_normalizes_spanish_header() -> None:
    spec = parse_measurement_column("LAGO VILLARRClorofila (ug/L)Media")
    assert spec == {
        "raw_column": "LAGO VILLARRClorofila (ug/L)Media",
        "variable": "chlorophyll_a",
        "statistic": "mean",
        "unit": "ug/L",
    }


def test_classify_quality_flags_sentinel_and_impossible_values() -> None:
    assert classify_quality("chlorophyll_a", -99.0) == "invalid_sentinel"
    assert classify_quality("turbidity", -0.5) == "invalid_negative"
    assert classify_quality("water_temperature", -1.0) == "implausible_temperature"
    assert classify_quality("chlorophyll_a", 3.2) == "ok"
