import pandas as pd

from database.db_manager import connection


def check_database():

    with connection() as conn:

        customers = pd.read_sql("SELECT COUNT(*) AS total FROM customers", conn)
        products = pd.read_sql("SELECT COUNT(*) AS total FROM products", conn)
        sales = pd.read_sql("SELECT COUNT(*) AS total FROM sales", conn)

        periods = pd.read_sql(
            """
            SELECT
                period,
                COUNT(*) AS rows_loaded
            FROM sales
            GROUP BY year, month, period
            ORDER BY year, month
            """,
            conn
        )

    print("\nCUSTOMERS")
    print(customers)

    print("\nPRODUCTS")
    print(products)

    print("\nSALES")
    print(sales)

    print("\nPERIODOS")
    print(periods)