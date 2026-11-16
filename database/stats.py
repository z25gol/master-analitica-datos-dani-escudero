from database.db_manager import connection


def get_database_stats():

    with connection() as conn:

        def count(table):
            return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

        customers = count("customers")
        products = count("products")
        sales = count("sales")

        # DD-MM-YYYY text doesn't sort chronologically, so order by year/month
        latest = conn.execute(
            "SELECT period FROM sales ORDER BY year DESC, month DESC LIMIT 1"
        ).fetchone()

    return {
        "customers": customers,
        "products": products,
        "sales": sales,
        "last_period": latest[0] if latest else None
    }