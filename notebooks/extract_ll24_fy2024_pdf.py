"""
Extract appendix tables from the NYC Local Law 24 FY2024 Solar Readiness report.

The appendix is not a single repeated table. It has four sections with distinct
schemas and page ranges:

- PDF pages 12-43: Completed Projects
- PDF pages 45-67: In Progress Projects
- PDF pages 69-105: Solar Ready Projects
- PDF pages 106-380: Not Solar Ready

Camelot's lattice mode is a better fit than pdfplumber here because it detects the
grid directly. Two options matter for this file:

- split_text=True  -> prevents some values from spilling into the next column
- strip_text="\n" -> turns split values like 11/16/2\n3 into 11/16/23

The output CSV uses a unified superset schema across all four sections.
"""

from __future__ import annotations

import re
from pathlib import Path

import camelot
import pandas as pd

PDF_PATH = Path(
    "/Users/john/github/zohran-ghs-dashboard/data/raw_data/DCAS/local-law-24-fy2024-report.pdf"
)
OUT_PATH = (
    Path(__file__).parent.parent
    / "data"
    / "raw_data"
    / "DCAS"
    / "local-law-24-fy2024-report.csv"
)

UNIFIED_COLUMNS = [
    "Source PDF Page",
    "Appendix Section",
    "2024 Solar-Ready Status",
    "City Council District",
    "Agency",
    "Site",
    "Address",
    "Borough",
    "Disadvantaged Community",
    "Installation Date",
    "Capacity",
    "Percentage of Max Peak Demand",
    "Estimated Annual Production",
    "Percentage of Annual Electricity Consumption",
    "Estimated Annual Emissions Reduction",
    "Estimated Social Cost of Carbon Value",
    "Estimated Annual Energy Savings",
    "Upfront Project Cost",
    "Financing Mechanism",
    "Total Gross Square Footage",
    "Roof Condition",
    "Roof Age",
    "Other Sustainability Projects",
]

SECTION_SPECS = [
    {
        "name": "Completed Projects",
        "status": "Completed",
        "page_start": 12,
        "page_end": 43,
        "expected_cols": 16,
        "mapping": {
            0: "City Council District",
            1: "Agency",
            2: "Site",
            3: "Address",
            4: "Borough",
            5: "Disadvantaged Community",
            6: "Installation Date",
            7: "Capacity",
            8: "Percentage of Max Peak Demand",
            9: "Estimated Annual Production",
            10: "Percentage of Annual Electricity Consumption",
            11: "Estimated Annual Emissions Reduction",
            12: "Estimated Social Cost of Carbon Value",
            13: "Estimated Annual Energy Savings",
            14: "Upfront Project Cost",
            15: "Financing Mechanism",
        },
    },
    {
        "name": "In Progress Projects",
        "status": "In Progress",
        "page_start": 45,
        "page_end": 67,
        "expected_cols": 14,
        "mapping": {
            0: "City Council District",
            1: "Agency",
            2: "Site",
            3: "Address",
            4: "Borough",
            5: "Disadvantaged Community",
            6: "Capacity",
            7: "Percentage of Max Peak Demand",
            8: "Estimated Annual Production",
            9: "Percentage of Annual Electricity Consumption",
            10: "Estimated Annual Emissions Reduction",
            11: "Estimated Social Cost of Carbon Value",
            12: "Estimated Annual Energy Savings",
            13: "Financing Mechanism",
        },
    },
    {
        "name": "Solar Ready Projects",
        "status": "Solar Ready",
        "page_start": 69,
        "page_end": 105,
        "expected_cols": 9,
        "mapping": {
            0: "City Council District",
            1: "Agency",
            2: "Site",
            3: "Address",
            4: "Borough",
            5: "Disadvantaged Community",
            6: "Capacity",
            7: "Estimated Annual Production",
            8: "Estimated Annual Emissions Reduction",
        },
    },
    {
        "name": "Not Solar Ready",
        "status": None,
        "page_start": 106,
        "page_end": 380,
        "expected_cols": 11,
        "mapping": {
            0: "City Council District",
            1: "2024 Solar-Ready Status",
            2: "Agency",
            3: "Site",
            4: "Address",
            5: "Borough",
            6: "Disadvantaged Community",
            7: "Total Gross Square Footage",
            8: "Roof Condition",
            9: "Roof Age",
            10: "Other Sustainability Projects",
        },
    },
]


def clean_cell(value: object) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    while re.search(r"(\d+,\d+) (\d)\b", text):
        text = re.sub(r"(\d+,\d+) (\d)\b", r"\1\2", text)
    return text


def normalize_page_df(df: pd.DataFrame) -> pd.DataFrame:
    """Clean strings, remove the header row, drop only truly empty artifact columns."""
    cleaned = df.map(clean_cell)
    if cleaned.empty:
        return cleaned

    header = cleaned.iloc[0].copy()
    data = cleaned.iloc[1:].reset_index(drop=True).copy()
    if data.empty:
        return data

    # Camelot occasionally inserts a blank-header spill column immediately after a
    # real column header. Page 13 does this for Installed Capacity: header[7] is
    # the real label, header[8] is blank, and the kW values land in column 8.
    for idx in range(1, cleaned.shape[1]):
        previous_header_has_text = header.iloc[idx - 1] != ""
        current_header_blank = header.iloc[idx] == ""
        previous_data_empty = data.iloc[:, idx - 1].eq("").all()
        current_data_has_text = not data.iloc[:, idx].eq("").all()
        if (
            previous_header_has_text
            and current_header_blank
            and previous_data_empty
            and current_data_has_text
        ):
            data.iloc[:, idx - 1] = data.iloc[:, idx]
            data.iloc[:, idx] = ""

    non_empty_cols = []
    for idx in range(cleaned.shape[1]):
        header_has_text = header.iloc[idx] != ""
        data_has_text = not data.iloc[:, idx].eq("").all()
        is_appendix_artifact = (
            header.iloc[idx].strip().lower() == "appendix" and not data_has_text
        )
        non_empty_cols.append(
            (header_has_text or data_has_text) and not is_appendix_artifact
        )

    data = data.loc[:, non_empty_cols].reset_index(drop=True)
    data.columns = range(data.shape[1])
    return data


def extract_page(page_num: int) -> pd.DataFrame | None:
    tables = camelot.read_pdf(
        str(PDF_PATH),
        pages=str(page_num),
        flavor="lattice",
        split_text=True,
        strip_text="\n",
    )
    if tables.n == 0:
        return None
    return normalize_page_df(tables[0].df)


def make_unified_record(
    page_num: int,
    section_name: str,
    default_status: str | None,
    row: list[str],
    mapping: dict[int, str],
) -> dict[str, str]:
    record = {column: "" for column in UNIFIED_COLUMNS}
    record["Source PDF Page"] = str(page_num)
    record["Appendix Section"] = section_name
    if default_status is not None:
        record["2024 Solar-Ready Status"] = default_status

    for idx, target in mapping.items():
        if idx < len(row):
            record[target] = row[idx]

    return record


def extract_section(spec: dict[str, object]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    skipped_pages: list[tuple[int, int]] = []

    for page_num in range(spec["page_start"], spec["page_end"] + 1):
        df = extract_page(page_num)
        if df is None:
            skipped_pages.append((page_num, 0))
            continue

        if df.shape[1] != spec["expected_cols"]:
            skipped_pages.append((page_num, df.shape[1]))
            continue

        for _, series in df.iterrows():
            row = [clean_cell(value) for value in series.tolist()]
            if not any(row):
                continue
            records.append(
                make_unified_record(
                    page_num=page_num,
                    section_name=spec["name"],
                    default_status=spec["status"],
                    row=row,
                    mapping=spec["mapping"],
                )
            )

    if skipped_pages:
        preview = skipped_pages[:8]
        suffix = " ..." if len(skipped_pages) > 8 else ""
        print(
            f"  {spec['name']}: skipped {len(skipped_pages)} pages due to \
                missing/unexpected schema -> {preview}{suffix}"
        )
    return records


def extract_all() -> pd.DataFrame:
    all_records: list[dict[str, str]] = []

    for spec in SECTION_SPECS:
        section_records = extract_section(spec)
        all_records.extend(section_records)
        print(f"  {spec['name']}: extracted {len(section_records)} records")

    return pd.DataFrame(all_records, columns=UNIFIED_COLUMNS)


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    print(f"Reading: {PDF_PATH}")
    df = extract_all()

    print(f"\nExtraction complete: {df.shape[0]} rows x {df.shape[1]} columns")
    print("\nRows by section:")
    print(df.groupby("Appendix Section").size().to_string())
    print("\nFirst 5 rows:")
    print(df.head().to_string())

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"\nSaved to: {OUT_PATH}")


if __name__ == "__main__":
    main()
