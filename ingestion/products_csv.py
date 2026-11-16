import pandas as pd

from ingestion.normalizer import normalize_id, normalize_text, read_table_file
from database.db_manager import connection, export_parquet


COLUMN_MAP = {
    "Código": "product_id",
    "Referencia": "reference_code",
    "Descripción": "product_name",
    "Tipo": "product_type",
    "Un/Caja": "units_per_case",
    "Grupo": "product_group",
    "Caduc.": "shelf_life_days",
    "Familia": "product_family",
    "T.Ex.": "exportation_type",
    "Formato Ped": "order_format",
}

ALLOWED_TYPES = {"ELABORADOS PROPIOS", "ELABORADOS EXTERNOS"}
EXTRA_PRODUCT_IDS = {"000354"}


def load_products(file_path):

    # ==========================
    # LECTURA
    # ==========================

    df = read_table_file(file_path, "Código")

    # ==========================
    # LIMPIEZA COLUMNAS
    # ==========================

    df.columns = df.columns.astype(str).str.strip()

    # ==========================
    # VALIDACIÓN
    # ==========================

    missing = [
        col
        for col in COLUMN_MAP
        if col not in df.columns
    ]

    if missing:

        raise ValueError(
            f"Faltan columnas: {missing}"
        )

    df = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)

    # ==========================
    # PRODUCT ID
    # ==========================

    df = df.dropna(subset=["product_id"])
    df["product_id"] = normalize_id(df["product_id"])
    df = df.drop_duplicates(subset="product_id")

    # ==========================
    # NUMÉRICOS
    # ==========================

    for col in ["units_per_case", "shelf_life_days"]:

        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ==========================
    # NORMALIZACIÓN
    # ==========================

    text_columns = [
        "reference_code",
        "product_name",
        "product_type",
        "product_group",
        "product_family",
        "exportation_type",
        "order_format"
    ]

    for col in text_columns:

        df[col] = df[col].apply(
            normalize_text
        )

    # ==========================
    # FILTRO PRODUCTOS
    # ==========================

    df = df[
        (
            df["product_type"].isin(ALLOWED_TYPES)
            & df["product_family"].fillna("").ne("")
        )
        | df["product_id"].isin(EXTRA_PRODUCT_IDS)
    ]

    # ==========================
    # SQLITE + PARQUET
    # ==========================

    with connection() as conn:
        conn.execute("DELETE FROM products")
        df.to_sql("products", conn, if_exists="append", index=False)

    export_parquet(df, "products")

    return df
