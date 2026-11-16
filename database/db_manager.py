import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

# The packaged .exe may live in a read-only folder, so its data goes to the user profile
if getattr(sys, "frozen", False):
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LaUnion" / "GestorVentas"
else:
    DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DB_PATH = DATA_DIR / "sqlite" / "sales.db"
PARQUET_DIR = DATA_DIR / "parquet"


def get_connection():

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    return sqlite3.connect(DB_PATH)


@contextmanager
def connection():
    """Commit on success, roll back on error and always close."""

    conn = get_connection()

    try:
        with conn:
            yield conn
    finally:
        conn.close()


def export_parquet(df, name):

    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    df.to_parquet(PARQUET_DIR / f"{name}.parquet", index=False)