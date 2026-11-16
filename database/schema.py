from database.db_manager import connection


def create_tables():

    with connection() as conn:
        _create_tables(conn.cursor())


def _create_tables(cursor):

    # SALES

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (

        period TEXT,
        year INTEGER,
        month INTEGER,

        customer_id TEXT,
        product_id TEXT,

        units REAL,
        kg REAL,
        avg_price REAL,
        amount REAL,

        source_file TEXT
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_period ON sales (period)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_year_month ON sales (year, month)")

    # Migrate legacy 'YYYY-MM' and 'YYYY-MM-DD' periods to 'DD-MM-YYYY' (last day of month)
    cursor.execute("""
    UPDATE sales
    SET period = strftime('%d-%m-%Y', date(period || '-01', '+1 month', '-1 day'))
    WHERE length(period) = 7
    """)

    cursor.execute("""
    UPDATE sales
    SET period = strftime('%d-%m-%Y', period)
    WHERE length(period) = 10 AND substr(period, 5, 1) = '-'
    """)

    # CUSTOMERS

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (

        customer_id TEXT PRIMARY KEY,

        legal_name TEXT,
        parent_customer_name TEXT,
        customer_name TEXT,

        city TEXT,

        registration_date TEXT,
        fiscal_period TEXT,

        payment_terms TEXT,
        sales_rep TEXT
    )
    """)

    # PRODUCTS

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (

        product_id TEXT PRIMARY KEY,

        reference_code TEXT,
        product_name TEXT,
        product_type TEXT,

        units_per_case REAL,

        product_group TEXT,
        shelf_life_days REAL,
        product_family TEXT,

        exportation_type TEXT,
        order_format TEXT
    )
    """)