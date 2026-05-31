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


@dataclass(frozen=True)
class ParsedDate:
    value: date | None
    raw_text: str
    encoding: str
    warning: str = ""


@dataclass(frozen=True)
class ContextualParsedDate:
    source_row: int
    parsed: ParsedDate
    was_repaired: bool = False


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

    return parse_date_value_with_context(value).value


def parse_date_value_with_context(value: Any) -> ParsedDate:
    """Parse row dates while preserving raw encoding for data QA."""

    if value is None:
        return ParsedDate(None, "", "blank", "blank_date")
    if isinstance(value, datetime):
        return ParsedDate(value.date(), value.isoformat(), "python_datetime")
    if isinstance(value, date):
        return ParsedDate(value, value.isoformat(), "python_date")
    text = str(value).strip()
    if not text:
        return ParsedDate(None, text, "blank", "blank_date")
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        serial = int(float(text))
        if 20_000 <= serial <= 80_000:
            return ParsedDate(
                (datetime(1899, 12, 30) + timedelta(days=serial)).date(),
                text,
                "excel_serial",
            )
        return ParsedDate(None, text, "numeric_out_of_range", "invalid_excel_serial")
    for fmt, encoding in (
        ("%d/%m/%Y", "slash_dmy"),
        ("%Y-%m-%d", "iso"),
        ("%d-%m-%Y", "dash_dmy"),
    ):
        try:
            return ParsedDate(datetime.strptime(text, fmt).date(), text, encoding)
        except ValueError:
            continue
    return ParsedDate(None, text, "unparsed", "unparsed_date")


def _contextual_date_rows(raw_table: RawTable) -> list[ContextualParsedDate]:
    """Parse date rows and repair workbook-level DMY/MDY Excel auto-conversions.

    The Pucón XLSX mixes literal Spanish ``dd/mm/yyyy`` strings with numeric Excel
    serials. In that workbook, serials appear where the original day was <= 12;
    Excel stored them as ``m/d/yy`` (e.g. intended 07/02/2024 became the serial for
    2024-07-02). We only apply the day/month swap when doing so resolves a mixed,
    non-monotonic table into chronological row order. Generic Excel serial parsing
    is intentionally left unchanged in ``parse_date_value_with_context``.
    """

    header = raw_table.rows[0] if raw_table.rows else []
    date_idx = _find_date_column(header) if header else None
    if date_idx is None:
        return []
    parsed_rows = [
        ContextualParsedDate(
            source_row=source_row,
            parsed=parse_date_value_with_context(row[date_idx] if date_idx < len(row) else ""),
        )
        for source_row, row in enumerate(raw_table.rows[1:], start=2)
    ]
    if not _should_repair_excel_serial_day_month_swaps(parsed_rows):
        return parsed_rows
    repaired_rows: list[ContextualParsedDate] = []
    for row in parsed_rows:
        repaired_value = _day_month_swapped_excel_serial_date(row.parsed)
        if repaired_value is None:
            repaired_rows.append(row)
            continue
        repaired_rows.append(
            ContextualParsedDate(
                source_row=row.source_row,
                parsed=ParsedDate(
                    repaired_value,
                    row.parsed.raw_text,
                    "excel_serial_dmy_swapped",
                    row.parsed.warning,
                ),
                was_repaired=True,
            )
        )
    return repaired_rows


def _contextual_date_lookup(raw_table: RawTable) -> dict[int, ParsedDate]:
    return {row.source_row: row.parsed for row in _contextual_date_rows(raw_table)}


def _should_repair_excel_serial_day_month_swaps(rows: list[ContextualParsedDate]) -> bool:
    encodings = {row.parsed.encoding for row in rows if row.parsed.value is not None}
    if "excel_serial" not in encodings or len(encodings) < 2:
        return False
    original_dates = [row.parsed.value for row in rows if row.parsed.value is not None]
    original_nonmonotonic = _nonmonotonic_step_count(original_dates)
    if original_nonmonotonic == 0:
        return False
    candidate_dates: list[date] = []
    repairable_count = 0
    for row in rows:
        parsed_value = row.parsed.value
        if parsed_value is None:
            continue
        repaired = _day_month_swapped_excel_serial_date(row.parsed)
        if repaired is not None:
            candidate_dates.append(repaired)
            repairable_count += 1
        else:
            candidate_dates.append(parsed_value)
    candidate_nonmonotonic = _nonmonotonic_step_count(candidate_dates)
    return repairable_count >= 2 and candidate_nonmonotonic == 0


def _day_month_swapped_excel_serial_date(parsed: ParsedDate) -> date | None:
    if parsed.encoding != "excel_serial" or parsed.value is None:
        return None
    if parsed.value.day > 12:
        return None
    return date(parsed.value.year, parsed.value.day, parsed.value.month)


def _nonmonotonic_step_count(values: list[date]) -> int:
    return sum(
        int(current < previous) for previous, current in zip(values, values[1:], strict=False)
    )


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
            raw_unit = unit_match.group(1).strip() if unit_match else default_unit
            unit = _normalize_unit(raw_unit, default_unit)
            return {
                "raw_column": header,
                "variable": variable,
                "statistic": statistic,
                "raw_unit": raw_unit,
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


def canonicalize_table(
    raw_table: RawTable,
    repo_root: Path,
    *,
    source_file_sha256: str,
    file_collision_reason: str = "",
    file_collision_station_count: int = 1,
) -> pd.DataFrame:
    if not raw_table.rows:
        return pd.DataFrame()
    header = raw_table.rows[0]
    date_idx = _find_date_column(header)
    if date_idx is None:
        return pd.DataFrame()
    date_validation = date_table_validation(raw_table)
    contextual_dates = _contextual_date_lookup(raw_table)
    column_specs: dict[int, dict[str, str]] = {}
    for idx, column in enumerate(header):
        spec = parse_measurement_column(column)
        if spec is not None:
            column_specs[idx] = spec

    records: list[dict[str, Any]] = []
    for source_row, row in enumerate(raw_table.rows[1:], start=2):
        raw_date = row[date_idx] if date_idx < len(row) else ""
        parsed = contextual_dates.get(source_row, parse_date_value_with_context(raw_date))
        if parsed.value is None:
            continue
        for idx, spec in column_specs.items():
            raw_value = row[idx] if idx < len(row) else ""
            value = parse_float(raw_value)
            if value is None:
                continue
            quality_flag = classify_quality(spec["variable"], value)
            exclusion_reasons = _model_exclusion_reasons(
                quality_flag=quality_flag,
                file_collision_reason=file_collision_reason,
                date_warning=parsed.warning,
            )
            records.append(
                {
                    "station_id": raw_table.station_id,
                    "station_name": raw_table.station_name,
                    "date": parsed.value.isoformat(),
                    "variable": spec["variable"],
                    "statistic": spec["statistic"],
                    "value": value,
                    "unit": spec["unit"],
                    "raw_unit": spec.get("raw_unit", spec["unit"]),
                    "value_role": "daily_summary_statistic",
                    "source_type": "in_situ_buoy",
                    "source_file": relative_to_root(raw_table.path, repo_root),
                    "source_file_sha256": source_file_sha256,
                    "source_file_collision_station_count": file_collision_station_count,
                    "source_sheet": raw_table.sheet_name,
                    "source_row": source_row,
                    "raw_column": spec["raw_column"],
                    "raw_value_text": str(raw_value).strip(),
                    "raw_date_value": parsed.raw_text,
                    "date_parse_method": parsed.encoding,
                    "date_validation_status": date_validation["date_validation_status"],
                    "date_validation_note": date_validation["date_validation_note"],
                    "quality_flag": quality_flag,
                    "is_observed": True,
                    "is_station_assignment_suspect": bool(file_collision_reason),
                    "is_model_eligible": not exclusion_reasons,
                    "model_exclusion_reason": ";".join(exclusion_reasons),
                    "notes": _canonical_notes(quality_flag, exclusion_reasons),
                }
            )
    return pd.DataFrame.from_records(records)


def _model_exclusion_reasons(
    *, quality_flag: str, file_collision_reason: str, date_warning: str
) -> list[str]:
    reasons: list[str] = []
    if quality_flag != "ok":
        reasons.append(quality_flag)
    if file_collision_reason:
        reasons.append(file_collision_reason)
    if date_warning and date_warning not in {"blank_date"}:
        reasons.append(date_warning)
    return reasons


def _canonical_notes(quality_flag: str, exclusion_reasons: list[str]) -> str:
    if exclusion_reasons:
        return "excluded_from_model: " + ";".join(exclusion_reasons)
    return "valid numeric observation" if quality_flag == "ok" else quality_flag


def _find_date_column(header: list[str]) -> int | None:
    for idx, column in enumerate(header):
        token = normalize_token(column)
        if "fecha" in token or "date" in token:
            return idx
    return None


def date_table_validation(raw_table: RawTable) -> dict[str, Any]:
    header = raw_table.rows[0] if raw_table.rows else []
    date_idx = _find_date_column(header) if header else None
    parsed_dates: list[date] = []
    encodings: list[str] = []
    warnings: list[str] = []
    repair_count = 0
    if date_idx is None:
        return {
            "date_validation_status": "missing_date_column",
            "date_validation_note": "No date column was detected.",
            "date_encoding_set": "",
            "nonmonotonic_parsed_date_steps": 0,
            "date_repair_count": 0,
        }
    for row in _contextual_date_rows(raw_table):
        parsed = row.parsed
        if parsed.value is not None:
            parsed_dates.append(parsed.value)
            encodings.append(parsed.encoding)
        if parsed.warning:
            warnings.append(parsed.warning)
        repair_count += int(row.was_repaired)
    nonmonotonic_steps = _nonmonotonic_step_count(parsed_dates)
    encoding_set = sorted(set(encodings))
    status = "ok"
    note = "Parsed date values are usable."
    if warnings:
        status = "date_parse_warnings"
        note = ";".join(sorted(set(warnings)))
    elif repair_count > 0 and nonmonotonic_steps == 0:
        status = "repaired_mixed_excel_serial_dates"
        note = (
            "Numeric Excel serials in a mixed date table were repaired as day/month-swapped "
            "dates after the repair restored chronological row order; raw_date_value and "
            "date_parse_method retain row-level provenance."
        )
    elif len(encoding_set) > 1 or nonmonotonic_steps > 0:
        status = "review_mixed_or_nonmonotonic_source_dates"
        note = (
            "Dates parse to valid calendar days but source rows mix encodings or are not "
            "chronologically sorted; row-level date_parse_method is retained."
        )
    return {
        "date_validation_status": status,
        "date_validation_note": note,
        "date_encoding_set": ";".join(encoding_set),
        "nonmonotonic_parsed_date_steps": nonmonotonic_steps,
        "date_repair_count": repair_count,
    }


def inventory_table(raw_table: RawTable, repo_root: Path) -> dict[str, Any]:
    header = raw_table.rows[0] if raw_table.rows else []
    date_idx = _find_date_column(header) if header else None
    parsed_dates: list[date] = []
    missing_by_column: dict[str, int] = dict.fromkeys(header, 0)
    duplicate_dates = 0
    seen_dates: set[date] = set()

    contextual_dates = _contextual_date_lookup(raw_table)
    for source_row, row in enumerate(raw_table.rows[1:], start=2):
        if date_idx is not None and date_idx < len(row):
            parsed = contextual_dates.get(source_row, parse_date_value_with_context(row[date_idx]))
            if parsed.value is not None:
                duplicate_dates += int(parsed.value in seen_dates)
                seen_dates.add(parsed.value)
                parsed_dates.append(parsed.value)
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
    date_validation = date_table_validation(raw_table)

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
        "date_validation_status": date_validation["date_validation_status"],
        "date_validation_note": date_validation["date_validation_note"],
        "date_encoding_set": date_validation["date_encoding_set"],
        "nonmonotonic_parsed_date_steps": date_validation["nonmonotonic_parsed_date_steps"],
        "date_repair_count": date_validation["date_repair_count"],
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


def raw_file_hash_collisions(inventory: pd.DataFrame) -> pd.DataFrame:
    if inventory.empty or "file_sha256" not in inventory.columns:
        return pd.DataFrame()
    grouped = inventory.groupby("file_sha256", dropna=False)
    rows = grouped.agg(
        source_files=("source_file", lambda s: "; ".join(sorted(set(s.astype(str))))),
        station_ids=("station_id", lambda s: "; ".join(sorted(set(s.astype(str))))),
        station_count=("station_id", "nunique"),
        row_counts=("row_count_raw", lambda s: "; ".join(str(int(v)) for v in s)),
        date_ranges=(
            "date_min",
            lambda s: "; ".join(
                f"{start}–{end}"
                for start, end in zip(
                    inventory.loc[s.index, "date_min"],
                    inventory.loc[s.index, "date_max"],
                    strict=True,
                )
            ),
        ),
    ).reset_index()
    return rows[rows["station_count"].gt(1)].sort_values("file_sha256")


def file_hash_collision_lookup(inventory: pd.DataFrame) -> dict[str, dict[str, Any]]:
    collisions = raw_file_hash_collisions(inventory)
    lookup: dict[str, dict[str, Any]] = {}
    if collisions.empty:
        return lookup
    for _, row in collisions.iterrows():
        lookup[str(row["file_sha256"])] = {
            "reason": "same_raw_file_assigned_to_multiple_stations",
            "station_count": int(row["station_count"]),
        }
    return lookup


def mixed_date_encoding_audit(raw_tables: list[RawTable]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for raw_table in raw_tables:
        header = raw_table.rows[0] if raw_table.rows else []
        date_idx = _find_date_column(header) if header else None
        serial_count = 0
        slash_date_count = 0
        iso_date_count = 0
        unparsed_count = 0
        parsed_dates: list[date] = []
        contextual_dates = _contextual_date_lookup(raw_table)
        repair_count = 0
        for source_row, raw_row in enumerate(raw_table.rows[1:], start=2):
            raw_value = (
                raw_row[date_idx] if date_idx is not None and date_idx < len(raw_row) else ""
            )
            raw_text = str(raw_value).strip()
            if re.fullmatch(r"\d+(?:\.0+)?", raw_text):
                serial_count += 1
            elif "/" in raw_text:
                slash_date_count += 1
            elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_text):
                iso_date_count += 1
            parsed = contextual_dates.get(source_row, parse_date_value_with_context(raw_text))
            if parsed.value is None and raw_text:
                unparsed_count += 1
            if parsed.value is not None:
                parsed_dates.append(parsed.value)
            repair_count += int(parsed.encoding == "excel_serial_dmy_swapped")
        nonmonotonic_steps = _nonmonotonic_step_count(parsed_dates)
        validation = date_table_validation(raw_table)
        rows.append(
            {
                "source_file": str(raw_table.path),
                "station_id": raw_table.station_id,
                "station_name": raw_table.station_name,
                "parsed_sheet": raw_table.sheet_name,
                "excel_serial_date_count": serial_count,
                "slash_date_count": slash_date_count,
                "iso_date_count": iso_date_count,
                "unparsed_date_count": unparsed_count,
                "excel_serial_dmy_swapped_repair_count": repair_count,
                "nonmonotonic_parsed_date_steps": nonmonotonic_steps,
                "date_validation_status": validation["date_validation_status"],
                "date_validation_note": validation["date_validation_note"],
                "date_encoding_set": validation["date_encoding_set"],
                "date_min": min(parsed_dates).isoformat() if parsed_dates else "",
                "date_max": max(parsed_dates).isoformat() if parsed_dates else "",
            }
        )
    return pd.DataFrame.from_records(rows)


def build_ingestion_outputs(config: dict[str, Any]) -> dict[str, Path]:
    repo_root = Path(config["_repo_root"])
    processed_dir = path_from_config(config, "processed_data")
    tables_dir = path_from_config(config, "tables")
    raw_files = discover_raw_files(config)
    raw_tables = [read_raw_table(path, config) for path in raw_files]

    inventory = pd.DataFrame([inventory_table(table, repo_root) for table in raw_tables])
    collision_lookup = file_hash_collision_lookup(inventory)
    canonical_parts = []
    for table in raw_tables:
        source_hash = file_sha256(table.path)
        collision = collision_lookup.get(source_hash, {})
        canonical_parts.append(
            canonicalize_table(
                table,
                repo_root,
                source_file_sha256=source_hash,
                file_collision_reason=str(collision.get("reason", "")),
                file_collision_station_count=int(collision.get("station_count", 1)),
            )
        )
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
        "raw_file_hash_collisions": write_csv(
            raw_file_hash_collisions(inventory), tables_dir / "raw_file_hash_collisions.csv"
        ),
        "mixed_date_encoding_audit": write_csv(
            mixed_date_encoding_audit(raw_tables), tables_dir / "mixed_date_encoding_audit.csv"
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
