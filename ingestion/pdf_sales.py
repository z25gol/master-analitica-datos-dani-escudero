import calendar
import re
from pathlib import Path

import pandas as pd
import pdfplumber

from database.db_manager import connection, export_parquet


MONTH_MAP = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12
}


class PeriodExistsError(ValueError):

    def __init__(self, period):
        super().__init__(f"El periodo {period} ya existe")
        self.period = period


def extract_period(pdf_file):

    filename = Path(pdf_file).stem.upper()

    month = None
    year = None

    for month_name, month_num in MONTH_MAP.items():

        if month_name in filename:

            month = month_num
            break

    year_match = re.search(r"(20\d{2})", filename)

    if year_match:
        year = int(year_match.group(1))

    if month is None or year is None:

        raise ValueError(
            f"No se pudo obtener periodo de {pdf_file}"
        )

    last_day = calendar.monthrange(year, month)[1]

    period = f"{last_day:02d}-{month:02d}-{year}"

    return year, month, period


def clean_numeric(value):

    if value is None:
        return 0

    value = str(value)

    value = value.replace(".", "")
    value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return 0


def load_sales(pdf_file, replace_existing=False):

    year, month, period = extract_period(pdf_file)

    with connection() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM sales WHERE period = ?", (period,)
        ).fetchone()[0]

    if existing and not replace_existing:
        raise PeriodExistsError(period)

    # Parse before touching the DB so a bad PDF never wipes an existing period
    sales_df = _parse_pdf(pdf_file, year, month, period)

    if sales_df.empty:
        raise ValueError("No se encontraron líneas de venta. Comprueba que el PDF es un resumen de ventas.")

    with connection() as conn:
        conn.execute("DELETE FROM sales WHERE period = ?", (period,))
        sales_df.to_sql("sales", conn, if_exists="append", index=False)
        history = pd.read_sql("SELECT * FROM sales ORDER BY year, month", conn)

    export_parquet(history, "sales")

    return sales_df


def _parse_pdf(pdf_file, year, month, period):

    source_file = Path(pdf_file).name

    rows = []

    current_customer_id = None

    # ----------------------------------
    # LEER PDF
    # ----------------------------------

    with pdfplumber.open(pdf_file) as pdf:

        for page in pdf.pages:

            text = page.extract_text()

            if not text:
                continue

            lines = text.split("\n")

            for line in lines:

                line = line.strip()

                if (
                    not line
                    or line.startswith("De ")
                    or "Resumen de Ventas" in line
                    or line == "Artículo"
                    or "Unid." in line
                    or line.startswith("Total Cliente")
                ):
                    continue

                # CLIENTE

                customer_match = re.match(
                    r"^(\d{6})\s+[A-Z0-9ÁÉÍÓÚÜÑ.,/\-& ]+$",
                    line
                )

                if customer_match:

                    if not re.search(
                        r"[\d.,]+\s+[\d.,]+$",
                        line
                    ):

                        current_customer_id = (
                            customer_match.group(1)
                        )

                        continue

                # PRODUCTO CON UNIDADES

                m = re.match(
                    r"^(\d{6})\s+.*?\s+([\d.]+)\s+(0,00)\s+(0,00)\s+([\d,]+)\s+([\d.,]+)$",
                    line
                )

                if m:

                    rows.append({
                        "year": year,
                        "month": month,
                        "period": period,
                        "customer_id": current_customer_id,
                        "product_id": m.group(1),
                        "units": clean_numeric(m.group(2)),
                        "kg": clean_numeric(m.group(3)),
                        "avg_price": clean_numeric(m.group(5)),
                        "amount": clean_numeric(m.group(6)),
                        "source_file": source_file
                    })

                    continue

                # PRODUCTO A GRANEL

                m = re.match(
                    r"^(\d{6})\s+.*?\s+([\d.,]+)\s+(0,00)\s+([\d,]+)\s+([\d.,]+)$",
                    line
                )

                if m:

                    rows.append({
                        "year": year,
                        "month": month,
                        "period": period,
                        "customer_id": current_customer_id,
                        "product_id": m.group(1),
                        "units": 0,
                        "kg": clean_numeric(m.group(2)),
                        "avg_price": clean_numeric(m.group(4)),
                        "amount": clean_numeric(m.group(5)),
                        "source_file": source_file
                    })

    return pd.DataFrame(rows)
