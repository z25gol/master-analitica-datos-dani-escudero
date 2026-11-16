import pandas as pd

from ingestion.normalizer import normalize_id, normalize_text, read_table_file
from database.db_manager import connection, export_parquet


COLUMN_MAP = {
    "Código": "customer_id",
    "Nombre Fiscal": "legal_name",
    "Nombre": "customer_name",
    "Poblacion": "city",
    "F.Alta": "registration_date",
    "F.Pago": "payment_terms",
}

PARENT_GROUPS = {
    "CARREFOUR": "001077 001078 001079 001080 001081 001082 001085 001086",
    "DIA": "001202 001203 001220",
    "ALCAMPO": "001366 001367 001368 001369 001371",
    "EL CORTE INGLES": """
        001372 001374 001375 001376 001378 001379 001380 001381 001382 001383
        001384 001385 001386 001387 001388 001389 001390 001391 001392 001393
        001394 001395 001396 001397 001398 001399 001400 001401 001402 001403
        001404 001406 001407 001408 001409 001410 001411 001412 001414 001415
        001417 001419 001420 001421 001422 001424 001425 001427 001428 001429
        001430 001431 001432 001433 001434 001435 001436 001437 001438 001439
        001440 001442 001443 001444 001445 001446 001447 001448 001449 001450
        001451 001452 001453 001454 001455 001456 001457 001458 001459 001460
        001461 001462 001463 001464 001465 001466 001467 001468 001469 001470
        001471 001472 001473 001474 001475 001476 001478 001479 001480 001481
        001483 001484 001485 001486 001487 001488 001489 001490 001491 001492
        001493 001494 001495 001497 001498 001499 001500 001501 001503 001504
        001505 001508 001509 001510 001511 001512 001513 001514 001516 001517
        001518 001519 001520 001523 001524 001525 001526 001528 001529 001530
        001531 001532 001533 001535 001536 001537 001538 001539 001540 001544
        001545 001546 001547 001548 001550 001551 001552 001553 001554 001556
        001558 001559 001562 001564 001565 001567 001568 001569 001570 001571
        001572 001573 001574 001575 001576 001577 001578 001579 001580 001581
        001582 001583 001584 001585 001586 001587 001588 001589 001590 001591
        001592 001593 001594 001595 001596 001597 001598 001599 001600 001601
        001602 001603
    """,
    "SUPERMERCADOS MAS Y MAS": "003024 003025",
    "SUPERMERCADOS FAMILIA": " ".join(f"{i:06d}" for i in range(3027, 3042)),
    "CASH BAREA": "003605 003606 003607 003608",
    "TRANSGOURMET": " ".join(f"{i:06d}" for i in range(3615, 3685)),
    "PALADAR GOURMET": "003985 003986",
    "FEITOMAR": "003808 003815",
    "DE LA TIERRA DEL CAUDAL": "004187 004190",
    "EUGENIO CANO CANALEJO": "003936 004729",
    "SIDRERIA CASA PABLO": "004346 004354",
    "SABOR IBERICO": "004444 004445",
    "BUJ Y AMPUDIA": "004104 004481",
    "CEFURA": "001617 004441",
    "AL PESO": "004550 004551 004552",
}

PARENT_BY_ID = {
    customer_id: parent
    for parent, ids in PARENT_GROUPS.items()
    for customer_id in ids.split()
}


def load_customers(file_path):

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
    # CUSTOMER ID
    # ==========================

    df = df.dropna(subset=["customer_id"])
    df["customer_id"] = normalize_id(df["customer_id"])
    df = df.drop_duplicates(subset="customer_id")

    # ==========================
    # FECHA ALTA
    # ==========================

    if pd.api.types.is_datetime64_any_dtype(df["registration_date"]):
        df["registration_date"] = df["registration_date"].dt.strftime("%d-%m-%Y")
    else:
        df["registration_date"] = df["registration_date"].astype("string").str.strip()

    # ==========================
    # NORMALIZACIÓN
    # ==========================

    text_columns = [
        "legal_name",
        "customer_name",
        "city",
        "payment_terms",
    ]

    for col in text_columns:

        df[col] = df[col].apply(
            normalize_text
        )

    # ==========================
    # PARENT CUSTOMER
    # ==========================

    df["parent_customer_name"] = (
        df["customer_id"]
        .map(PARENT_BY_ID)
        .fillna(df["customer_name"])
    )

    df = df[[
        "customer_id",
        "legal_name",
        "parent_customer_name",
        "customer_name",
        "city",
        "registration_date",
        "payment_terms",
    ]]

    # ==========================
    # SQLITE + PARQUET
    # ==========================

    with connection() as conn:
        conn.execute("DELETE FROM customers")
        df.to_sql("customers", conn, if_exists="append", index=False)

    export_parquet(df, "customers")

    return df