from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": SPREADSHEET_NS, "r": REL_NS, "pr": PKG_REL_NS}


@dataclass(frozen=True)
class ParsedXlsxSheet:
    """Rows parsed from a single XLSX worksheet without requiring openpyxl."""

    sheet_name: str
    rows: list[list[str]]


def _shared_strings(zip_file: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zip_file.namelist():
        return []
    tree = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for si in tree.findall("a:si", NS):
        values.append("".join(node.text or "" for node in si.iter(f"{{{SPREADSHEET_NS}}}t")))
    return values


def _sheet_targets(zip_file: ZipFile) -> dict[str, str]:
    rels = ET.fromstring(zip_file.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    workbook = ET.fromstring(zip_file.read("xl/workbook.xml"))
    targets: dict[str, str] = {}
    for sheet in workbook.find("a:sheets", NS) or []:
        name = sheet.attrib["name"]
        rid = sheet.attrib[f"{{{REL_NS}}}id"]
        target = rid_to_target[rid]
        targets[name] = target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
    return targets


def list_sheet_names(path: str | Path) -> list[str]:
    """Return worksheet names in workbook order."""

    with ZipFile(path) as zip_file:
        workbook = ET.fromstring(zip_file.read("xl/workbook.xml"))
        return [sheet.attrib["name"] for sheet in workbook.find("a:sheets", NS) or []]


def parse_xlsx_sheet(path: str | Path, preferred_sheet: str = "Hoja1") -> ParsedXlsxSheet:
    """Parse a worksheet into rows using only the XLSX XML files.

    The fallback avoids making raw-data ingestion depend on a particular Excel engine.
    It is sufficient for the workbook layout present in this repository.
    """

    workbook_path = Path(path)
    with ZipFile(workbook_path) as zip_file:
        shared = _shared_strings(zip_file)
        targets = _sheet_targets(zip_file)
        sheet_name = preferred_sheet if preferred_sheet in targets else next(iter(targets))
        sheet_xml = ET.fromstring(zip_file.read(targets[sheet_name]))
        rows: list[list[str]] = []
        for row in sheet_xml.findall(".//a:sheetData/a:row", NS):
            values: list[str] = []
            current_col = 1
            for cell in row.findall("a:c", NS):
                ref = cell.attrib.get("r", "")
                col_index = _column_index(ref)
                while current_col < col_index:
                    values.append("")
                    current_col += 1
                values.append(_cell_value(cell, shared))
                current_col += 1
            rows.append(values)
    return ParsedXlsxSheet(sheet_name=sheet_name, rows=rows)


def _column_index(cell_reference: str) -> int:
    letters = "".join(ch for ch in cell_reference if ch.isalpha())
    if not letters:
        return 1
    value = 0
    for char in letters:
        value = value * 26 + (ord(char.upper()) - ord("A") + 1)
    return value


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    node = cell.find("a:v", NS)
    if node is None:
        inline = cell.find("a:is/a:t", NS)
        return inline.text if inline is not None and inline.text else ""
    raw = node.text or ""
    if cell.attrib.get("t") == "s" and raw.isdigit():
        idx = int(raw)
        return shared[idx] if idx < len(shared) else raw
    return raw
