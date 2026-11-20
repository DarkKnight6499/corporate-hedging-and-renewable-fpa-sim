"""Audit generated tables and workbook after run_all.py."""
import json
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

# CONFIG
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
DATA = ROOT / "data"
BOOK = OUTPUT / "synthetic_finance_model.xlsx"
AUTHOR = "Project Author"
MIN_TABLE_COUNT = 16
SUMMARY = OUTPUT / "summary.json"
PROHIBITED = (chr(8211), chr(8212), chr(45) * 2)
TEXT_SUFFIXES = (".py", ".md", ".csv", ".json", ".txt")
METRIC = "metric"
VALUE = "value"
CELL_ABSOLUTE_TOLERANCE = 1e-8
CELL_RELATIVE_TOLERANCE = 1e-12
FREEZE_CELL = "A2"
CSV_GLOB = "*.csv"
VAR_SHEET = "cashflow_var"
SUMMARY_SHEET = "summary"
VAR_COLUMNS = ("unhedged_cash_usd", "hedged_cash_usd")
MONTH = "month"


def main():
    files = sorted(DATA.glob(CSV_GLOB)) + sorted(OUTPUT.glob(CSV_GLOB))
    assert len(files) >= MIN_TABLE_COUNT
    for file in files:
        frame = pd.read_csv(file)
        assert not frame.empty and not frame.isna().any().any(), file
        assert np.isfinite(frame.select_dtypes(include="number").to_numpy()).all(), file
    metrics = json.loads(SUMMARY.read_text(encoding="utf-8"))
    workbook = load_workbook(BOOK, read_only=False, data_only=True)
    assert workbook.properties.creator == AUTHOR
    assert workbook.properties.lastModifiedBy == AUTHOR
    assert len(workbook[VAR_SHEET]._charts) == 1
    var_sheet = workbook[VAR_SHEET]
    headers = [cell.value for cell in var_sheet[1]]
    chart = var_sheet._charts[0]
    assert len(chart.series) == len(VAR_COLUMNS)
    month_letter = get_column_letter(headers.index(MONTH) + 1)
    for series, column in zip(chart.series, VAR_COLUMNS):
        letter = get_column_letter(headers.index(column) + 1)
        assert series.val.numRef.f == f"'{VAR_SHEET}'!${letter}$2:${letter}${var_sheet.max_row}"
        assert series.cat.numRef.f == f"'{VAR_SHEET}'!${month_letter}$2:${month_letter}${var_sheet.max_row}"
    for file in files:
        frame = pd.read_csv(file)
        sheet = workbook[file.stem]
        assert sheet.max_row == len(frame) + 1, file
        assert [cell.value for cell in sheet[1]] == list(frame.columns), file
        assert sheet.freeze_panes == FREEZE_CELL, file
        for expected, cells in zip(frame.to_dict("records"), sheet.iter_rows(min_row=2)):
            for column, cell in zip(frame.columns, cells):
                value = expected[column]
                if isinstance(cell.value, datetime):
                    assert pd.Timestamp(cell.value) == pd.Timestamp(value), (file, column)
                elif isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                    assert np.isclose(cell.value, float(value), rtol=CELL_RELATIVE_TOLERANCE,
                                      atol=CELL_ABSOLUTE_TOLERANCE), (file, column)
                else:
                    assert cell.value == value, (file, column)
    sheet = workbook[SUMMARY_SHEET]
    summary_frame = pd.DataFrame(sheet.iter_rows(min_row=2, values_only=True),
                                 columns=[cell.value for cell in sheet[1]])
    values = summary_frame.set_index(METRIC)[VALUE].to_dict()
    for metric, value in metrics.items():
        assert np.isclose(values[metric], value), metric
    for sheet in workbook:
        assert sheet.sheet_properties.tabColor is None
        for row in sheet.iter_rows():
            for cell in row:
                assert cell.fill.patternType is None
                assert cell.font.color is None or (cell.font.color.type == "theme" and cell.font.color.theme == 1)
    workbook.close()
    for file in ROOT.rglob("*"):
        if file.is_file() and file.suffix in TEXT_SUFFIXES:
            lines = file.read_text(encoding="utf-8").splitlines()
            content = "\n".join(line for line in lines
                                if not (line.strip().startswith("|") and set(line.strip()) <= set("| :-")))
            assert not any(mark in content for mark in PROHIBITED), file
    print(f"PASS output audit: {len(files)} CSVs, every workbook cell, chart, metadata, plain formatting and punctuation")


if __name__ == "__main__":
    main()
