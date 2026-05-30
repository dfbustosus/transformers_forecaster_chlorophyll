from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.data.html_xls import parse_html_xls
from villarrica_forecaster.data.xlsx_minimal import list_sheet_names, parse_xlsx_sheet
from villarrica_forecaster.io import relative_to_root, write_csv, write_json
from villarrica_forecaster.text import normalize_token


@dataclass(frozen=True)
class RawTable:
    path: Path
    kind: str
    station_id: str
    station_name: str
    sheet_name: str
    rows: list[list[str]]
    workbook_sheets: list[str]


STAT_SUFFIXES = {
    "min": "min",
    "max": "max",
    "media": "mean",
    "mean": "mean",
}

VARIABLE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("turbiedad", "turbidity", "NTU"),
    ("turbidity", "turbidity", "NTU"),
    ("temp sonda", "water_temperature", "degC"),
    ("temperature", "water_temperature", "degC"),
    ("oxigeno disuelto 2", "dissolved_oxygen", "ppm"),
    ("dissolved oxygen", "dissolved_oxygen", "ppm"),
    ("oxigeno disuelto 1", "dissolved_oxygen_saturation", "%"),
    ("clorofila", "chlorophyll_a", "ug/L"),
    ("chlorophyll", "chlorophyll_a", "ug/L"),
    ("materia organica disuelta", "dissolved_organic_matter", "QSU"),
    ("dissolved organic matter", "dissolved_organic_matter", "QSU"),
    ("ficocianina", "phycocyanin", "ug/L"),
    ("phycocyanin", "phycocyanin", "ug/L"),
    ("ph ", "pH", "pH"),
    ("ph", "pH", "pH"),
)

NONNEGATIVE_VARIABLES = {
    "turbidity",
    "dissolved_oxygen",
    "dissolved_oxygen_saturation",
    "chlorophyll_a",
    "dissolved_organic_matter",
    "phycocyanin",
}


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_date_value(value: Any) -> date | None:
    """Parse Spanish day/month dates and Excel serial dates to calendar dates."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        serial = int(float(text))
        if 20_000 <= serial <= 80_000:
            return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def infer_station(path: str | Path, stations_config: dict[str, Any]) -> tuple[str, str]:
    tokenized_path = normalize_token(str(path))
    for station in stations_config.values():
        for token in station.get("path_tokens", []):
            if normalize_token(token) in tokenized_path:
                return station["station_id"], station["station_name"]
    return "unknown", "Unknown"


def detect_raw_kind(path: str | Path) -> str:
    candidate = Path(path)
    start = candidate.read_bytes()[:16]
    if start.startswith(b"PK") and candidate.suffix.lower() == ".xlsx":
        return "xlsx"
    if start.lstrip().startswith(b"<table") or start.lstrip().startswith(b"<html"):
        return "html_xls"
    return "unknown_excel_like"


def discover_raw_files(config: dict[str, Any]) -> list[Path]:
    raw_root = path_from_config(config, "raw_data")
    files = [p for p in raw_root.rglob("*") if p.suffix.lower() in {".xls", ".xlsx"}]
    return sorted(files, key=lambda p: p.as_posix().lower())


def read_raw_table(path: str | Path, config: dict[str, Any]) -> RawTable:
    file_path = Path(path)
    kind = detect_raw_kind(file_path)
    station_id, station_name = infer_station(file_path, config.get("stations", {}))
    if kind == "html_xls":
        parsed = parse_html_xls(file_path)
        return RawTable(
            path=file_path,
            kind=kind,
            station_id=station_id,
            station_name=station_name,
            sheet_name="html_table_1",
            rows=parsed.rows,
            workbook_sheets=["html_table_1"],
        )
    if kind == "xlsx":
        parsed_xlsx = parse_xlsx_sheet(file_path, preferred_sheet="Hoja1")
        rows = _combine_two_row_header(parsed_xlsx.rows)
        return RawTable(
            path=file_path,
            kind=kind,
            station_id=station_id,
            station_name=station_name,
            sheet_name=parsed_xlsx.sheet_name,
            rows=rows,
            workbook_sheets=list_sheet_names(file_path),
        )
    return RawTable(
        path=file_path,
        kind=kind,
        station_id=station_id,
        station_name=station_name,
        sheet_name="unreadable",
        rows=[],
        workbook_sheets=[],
    )


def _combine_two_row_header(rows: list[list[str]]) -> list[list[str]]:
    if len(rows) < 2:
        return rows
    first = rows[0]
    second = rows[1]
    width = max(len(first), len(second))
    header: list[str] = []
    for idx in range(width):
        top = first[idx].strip() if idx < len(first) else ""
        bottom = second[idx].strip() if idx < len(second) else ""
        if idx == 0:
            header.append(top or bottom or "Fecha-Hora de Medicion")
        elif bottom:
            header.append(bottom)
        else:
            header.append(top)
    return [header, *rows[2:]]


def parse_measurement_column(header: str) -> dict[str, str] | None:
    clean = header.replace("LAGO VILLARR", "").strip()
    clean = re.sub(r"\s+", " ", clean)
    token = normalize_token(clean)
    if not token or token in {"nro", "fecha hora de medicion"}:
        return None

    statistic = "value"
    stat_match = re.search(r"(Min|Max|Media|Mean)$", clean, flags=re.IGNORECASE)
    if stat_match:
        statistic = STAT_SUFFIXES[normalize_token(stat_match.group(1))]
        clean_without_stat = clean[: stat_match.start()].strip()
    else:
        clean_without_stat = clean

    normalized = normalize_token(clean_without_stat)
    for pattern, variable, default_unit in VARIABLE_PATTERNS:
        if pattern in normalized:
            unit_match = re.search(r"\(([^)]+)\)", clean_without_stat)
            unit = unit_match.group(1).strip() if unit_match else default_unit
            unit = _normalize_unit(unit, default_unit)
            return {
                "raw_column": header,
                "variable": variable,
                "statistic": statistic,
                "unit": unit,
            }
    return None


def _normalize_unit(raw_unit: str, fallback: str) -> str:
    token = normalize_token(raw_unit)
    if token in {"ug l", "ug lt", "µg l", "microg l"}:
        return "ug/L"
    if token in {"oc", "c", "degc"}:
        return "degC"
    if token == "ntu":
        return "NTU"
    if token == "ppm":
        return "ppm"
    if token in {"ph"}:
        return "pH"
    if token in {"qsu", "od450", "od 450"}:
        return raw_unit
    if raw_unit == "%":
        return "%"
    return fallback


def classify_quality(variable: str, value: float) -> str:
    if value <= -90:
        return "invalid_sentinel"
    if variable in NONNEGATIVE_VARIABLES and value < 0:
        return "invalid_negative"
    if variable == "water_temperature" and not (0 <= value <= 35):
        return "implausible_temperature"
    if variable == "pH" and not (0 <= value <= 14):
        return "implausible_ph"
    if variable == "dissolved_oxygen" and value > 30:
        return "implausible_dissolved_oxygen"
    if variable == "dissolved_oxygen_saturation" and value > 250:
        return "implausible_dissolved_oxygen_saturation"
    return "ok"


def canonicalize_table(raw_table: RawTable, repo_root: Path) -> pd.DataFrame:
    if not raw_table.rows:
        return pd.DataFrame()
    header = raw_table.rows[0]
    date_idx = _find_date_column(header)
    if date_idx is None:
        return pd.DataFrame()
    column_specs: dict[int, dict[str, str]] = {}
    for idx, column in enumerate(header):
        spec = parse_measurement_column(column)
        if spec is not None:
            column_specs[idx] = spec

    records: list[dict[str, Any]] = []
    for source_row, row in enumerate(raw_table.rows[1:], start=2):
        raw_date = row[date_idx] if date_idx < len(row) else ""
        parsed_date = parse_date_value(raw_date)
        if parsed_date is None:
            continue
        for idx, spec in column_specs.items():
            value = parse_float(row[idx] if idx < len(row) else "")
            if value is None:
                continue
            quality_flag = classify_quality(spec["variable"], value)
            records.append(
                {
                    "station_id": raw_table.station_id,
                    "station_name": raw_table.station_name,
                    "date": parsed_date.isoformat(),
                    "variable": spec["variable"],
                    "statistic": spec["statistic"],
                    "value": value,
                    "unit": spec["unit"],
                    "source_type": "in_situ_buoy",
                    "source_file": relative_to_root(raw_table.path, repo_root),
                    "source_sheet": raw_table.sheet_name,
                    "source_row": source_row,
                    "raw_column": spec["raw_column"],
                    "quality_flag": quality_flag,
                    "is_observed": True,
                    "notes": "valid numeric observation" if quality_flag == "ok" else quality_flag,
                }
            )
    return pd.DataFrame.from_records(records)


def _find_date_column(header: list[str]) -> int | None:
    for idx, column in enumerate(header):
        token = normalize_token(column)
        if "fecha" in token or "date" in token:
            return idx
    return None


def inventory_table(raw_table: RawTable, repo_root: Path) -> dict[str, Any]:
    header = raw_table.rows[0] if raw_table.rows else []
    date_idx = _find_date_column(header) if header else None
    parsed_dates: list[date] = []
    missing_by_column: dict[str, int] = dict.fromkeys(header, 0)
    duplicate_dates = 0
    seen_dates: set[date] = set()

    for row in raw_table.rows[1:]:
        if date_idx is not None and date_idx < len(row):
            parsed = parse_date_value(row[date_idx])
            if parsed is not None:
                duplicate_dates += int(parsed in seen_dates)
                seen_dates.add(parsed)
                parsed_dates.append(parsed)
        for idx, column in enumerate(header):
            if idx >= len(row) or not str(row[idx]).strip():
                missing_by_column[column] = missing_by_column.get(column, 0) + 1

    variables = []
    units = []
    for column in header:
        spec = parse_measurement_column(column)
        if spec is not None:
            variables.append(spec["variable"])
            units.append(spec["unit"])

    return {
        "source_file": relative_to_root(raw_table.path, repo_root),
        "file_sha256": file_sha256(raw_table.path),
        "file_kind": raw_table.kind,
        "station_id": raw_table.station_id,
        "station_name": raw_table.station_name,
        "sheets": "; ".join(raw_table.workbook_sheets),
        "parsed_sheet": raw_table.sheet_name,
        "row_count_raw": max(len(raw_table.rows) - 1, 0),
        "column_count": len(header),
        "date_min": min(parsed_dates).isoformat() if parsed_dates else "",
        "date_max": max(parsed_dates).isoformat() if parsed_dates else "",
        "duplicate_date_count": duplicate_dates,
        "variables": "; ".join(sorted(set(variables))),
        "units": "; ".join(sorted(set(units))),
        "raw_columns": " | ".join(header),
        "missing_counts_by_column": " | ".join(
            f"{key}:{value}" for key, value in missing_by_column.items() if value
        ),
    }


def build_data_dictionary(canonical: pd.DataFrame) -> pd.DataFrame:
    if canonical.empty:
        return pd.DataFrame(columns=["variable", "unit", "statistics", "source_types", "row_count"])
    grouped = canonical.groupby("variable", dropna=False)
    return grouped.agg(
        unit=("unit", lambda s: "; ".join(sorted({str(v) for v in s.dropna()}))),
        statistics=("statistic", lambda s: "; ".join(sorted({str(v) for v in s.dropna()}))),
        source_types=("source_type", lambda s: "; ".join(sorted({str(v) for v in s.dropna()}))),
        row_count=("value", "size"),
    ).reset_index()


def build_station_coverage(canonical: pd.DataFrame) -> pd.DataFrame:
    if canonical.empty:
        return pd.DataFrame()
    valid = canonical[canonical["quality_flag"].eq("ok")].copy()
    valid["date"] = pd.to_datetime(valid["date"])
    grouped = valid.groupby(["station_id", "station_name", "variable", "statistic"], dropna=False)
    coverage = grouped.agg(
        observed_row_count=("value", "size"),
        unique_date_count=("date", "nunique"),
        date_min=("date", "min"),
        date_max=("date", "max"),
        unit=("unit", lambda s: "; ".join(sorted(set(s)))),
    ).reset_index()
    coverage["date_min"] = coverage["date_min"].dt.date.astype(str)
    coverage["date_max"] = coverage["date_max"].dt.date.astype(str)
    return coverage


def build_ingestion_outputs(config: dict[str, Any]) -> dict[str, Path]:
    repo_root = Path(config["_repo_root"])
    processed_dir = path_from_config(config, "processed_data")
    tables_dir = path_from_config(config, "tables")
    raw_files = discover_raw_files(config)
    raw_tables = [read_raw_table(path, config) for path in raw_files]

    inventory = pd.DataFrame([inventory_table(table, repo_root) for table in raw_tables])
    canonical_parts = [canonicalize_table(table, repo_root) for table in raw_tables]
    canonical = pd.concat(canonical_parts, ignore_index=True) if canonical_parts else pd.DataFrame()
    if not canonical.empty:
        canonical = canonical.sort_values(
            ["station_id", "date", "variable", "statistic", "source_file", "source_row"]
        ).reset_index(drop=True)

    paths = {
        "data_inventory": write_csv(inventory, tables_dir / "data_inventory.csv"),
        "canonical_observations": write_csv(
            canonical, processed_dir / "canonical_observations.csv"
        ),
        "data_dictionary": write_csv(
            build_data_dictionary(canonical), tables_dir / "data_dictionary.csv"
        ),
        "station_date_coverage": write_csv(
            build_station_coverage(canonical), tables_dir / "station_date_coverage.csv"
        ),
    }

    if not canonical.empty:
        validation = (
            canonical.groupby(["station_id", "variable", "quality_flag"], dropna=False)
            .size()
            .reset_index(name="row_count")
        )
    else:
        validation = pd.DataFrame(columns=["station_id", "variable", "quality_flag", "row_count"])
    paths["quality_flag_summary"] = write_csv(validation, tables_dir / "quality_flag_summary.csv")
    paths["raw_file_manifest"] = write_json(
        {
            "raw_file_count": len(raw_files),
            "raw_files": [relative_to_root(path, repo_root) for path in raw_files],
            "outputs": {key: relative_to_root(value, repo_root) for key, value in paths.items()},
        },
        processed_dir / "raw_file_manifest.json",
    )
    return paths
