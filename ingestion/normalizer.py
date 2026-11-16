import re
import unicodedata
from pathlib import Path

import pandas as pd


EXCEL_SUFFIXES = (".xlsx", ".xlsm")


def read_table_file(file_path, id_column):

    suffix = Path(file_path).suffix.lower()
    dtype = {id_column: str}

    if suffix in EXCEL_SUFFIXES:
        return pd.read_excel(file_path, dtype=dtype)

    if suffix != ".csv":
        raise ValueError(f"Formato no soportado: {suffix or 'sin extensión'}. Usa Excel (.xlsx) o CSV.")

    # sep=None sniffs ',' or ';'; utf-8-sig strips the BOM Excel adds to UTF-8 CSVs
    try:
        return pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8-sig", dtype=dtype)
    except UnicodeDecodeError:
        return pd.read_csv(file_path, sep=None, engine="python", encoding="latin1", dtype=dtype)


def normalize_id(series):

    return (
        series
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(6)
    )


def normalize_text(text):

    if pd.isna(text):
        return text

    text = str(text).strip().upper()

    text = unicodedata.normalize("NFD", text)

    text = "".join(
        c for c in text
        if unicodedata.category(c) != "Mn"
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()