"""Strict lexical CSV ingestion; inferred analytical types are a separate view."""

import csv
import io
import re
import warnings
from pathlib import PurePath
import numpy as np
import pandas as pd
from charset_normalizer import from_bytes
from fastapi import HTTPException
from app.core.config import settings

DATE_PREFIX = re.compile(r"^(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})")


def parse_csv(content: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    if not filename.lower().endswith(".csv"):
        raise HTTPException(415, "Choose a .csv file.")
    if not content or len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"CSV must be nonempty and at most {settings.max_upload_mb} MB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        match = from_bytes(content).best()
        if match is None:
            raise HTTPException(422, "Could not identify the file encoding. Save the CSV as UTF-8.")
        text = str(match)
    if "\x00" in text:
        raise HTTPException(422, "Binary content is not a CSV file.")
    try:
        try:
            dialect = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text, newline=""), dialect=dialect, strict=True)
        header = next(reader)
        if not header or any(not c.strip() or len(c) > 200 for c in header):
            raise ValueError("Column names must be nonempty and at most 200 characters.")
        if len(set(header)) != len(header):
            raise ValueError("Duplicate column names are not supported. Rename them before importing.")
        if len(header) > settings.max_columns:
            raise ValueError(f"At most {settings.max_columns} columns are supported.")
        records = []
        for line, row in enumerate(reader, 2):
            if len(row) != len(header):
                raise ValueError(
                    f"Record {line} has {len(row)} fields; expected {len(header)}. No rows were discarded."
                )
            records.append(row)
            if len(records) > settings.max_rows:
                raise ValueError(
                    f"At most {settings.max_rows:,} rows are supported. Split this file before importing."
                )
        if not records:
            raise ValueError("CSV contains a header but no data rows.")
    except (csv.Error, ValueError, StopIteration) as exc:
        raise HTTPException(422, str(exc) or "CSV could not be parsed.") from exc
    raw = pd.DataFrame(records, columns=header, dtype=str)
    kinds, notes = {}, []
    for col in header:
        series = raw[col].loc[raw[col].str.strip().ne("")]
        if series.empty:
            kinds[col] = "empty"
        elif series.str.lower().isin(["true", "false"]).all():
            kinds[col] = "boolean"
        else:
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric.notna().all() and np.isfinite(numeric.to_numpy(dtype=float)).all():
                kinds[col] = "numeric"
            elif series.map(lambda x: bool(DATE_PREFIX.match(x))).all():
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    dates = pd.to_datetime(series, errors="coerce", format="mixed", utc=True)
                kinds[col] = "datetime" if dates.notna().all() else "categorical"
                if kinds[col] == "datetime":
                    notes.append(
                        f"{col}: inferred dates are normalized to UTC for analysis. Review ambiguous day/month conventions; original text is preserved."
                    )
            else:
                kinds[col] = "categorical"
                if numeric.notna().any():
                    notes.append(
                        f"{col}: mixed values retained as text; numeric calculations are unavailable."
                    )
            if numeric.notna().any() and not np.isfinite(numeric.dropna().to_numpy(dtype=float)).all():
                notes.append(f"{col}: non-finite or out-of-range numbers retained as text.")
    return raw, kinds, notes


def typed_frame(raw: pd.DataFrame, kinds: dict[str, str]) -> pd.DataFrame:
    frame = raw.copy()
    for col, kind in kinds.items():
        frame[col] = frame[col].mask(frame[col].str.strip().eq(""))
        if kind == "numeric":
            frame[col] = pd.to_numeric(frame[col], errors="raise").astype(float)
        elif kind == "datetime":
            frame[col] = pd.to_datetime(frame[col], errors="raise", format="mixed", utc=True)
        elif kind == "boolean":
            frame[col] = frame[col].str.lower().map({"true": True, "false": False}).astype("boolean")
    return frame


def safe_name(filename: str) -> str:
    return PurePath(filename.replace("\\", "/")).name[:180]
