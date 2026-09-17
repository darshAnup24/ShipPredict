"""
Load raw DataCo supply chain CSV files into Snowflake RAW schema.

Expected files (relative to the project root):
  data/DataCoSupplyChainDataset.csv   (supply chain transactions)
  data/tokenized_access_logs.csv     (web clickstream access logs)

Credentials are read from environment variables (never hard-coded):
  SNOWFLAKE_ACCOUNT     e.g. xyz12345.us-east-1
  SNOWFLAKE_USER
  SNOWFLAKE_PASSWORD
  SNOWFLAKE_ROLE        default ACCOUNTADMIN
  SNOWFLAKE_WAREHOUSE   default SUPPLY_CHAIN_WH
  SNOWFLAKE_DATABASE    default SUPPLY_CHAIN_DB
  SNOWFLAKE_SCHEMA      default RAW

The load is idempotent: the target tables are truncated and recreated on
every run, so re-running produces the same correct state.
"""

import os

import pandas as pd
import snowflake.connector

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _data_dir() -> str:
    """Raw data folder. If DATA_DATE (YYYY-MM-DD) is set, prefer data/<DATE>/,
    otherwise fall back to the default data/ folder."""
    data_date = os.environ.get("DATA_DATE")
    if data_date:
        day_dir = os.path.join(PROJECT_ROOT, "data", data_date)
        if os.path.isdir(day_dir):
            return day_dir
        print(f"WARNING: date-specific data folder {day_dir} not found, falling back to data/")
    return os.path.join(PROJECT_ROOT, "data")

DATA_DIR = _data_dir()

SUPPLY_CHAIN_CSV = os.path.join(DATA_DIR, "DataCoSupplyChainDataset.csv")
WEB_TRAFFIC_CSV = os.path.join(DATA_DIR, "tokenized_access_logs.csv")

SUPPLY_CHAIN_TABLE = "RAW_SUPPLY_CHAIN"
WEB_TRAFFIC_TABLE = "RAW_WEB_TRAFFIC"

# Map raw CSV column headers to the exact UPPER_SNAKE_CASE names the dbt
# staging models reference in models/staging/sources.yml and stg_*.sql.
SUPPLY_CHAIN_COLUMN_MAP = {
    "Type": "TYPE",
    "Days for shipping (real)": "DAYS_FOR_SHIPPING_REAL",
    "Days for shipment (scheduled)": "DAYS_FOR_SHIPMENT_SCHEDULED",
    "Benefit per order": "BENEFIT_PER_ORDER",
    "Sales per customer": "SALES_PER_CUSTOMER",
    "Delivery Status": "DELIVERY_STATUS",
    "Late_delivery_risk": "LATE_DELIVERY_RISK",
    "Category Id": "CATEGORY_ID",
    "Category Name": "CATEGORY_NAME",
    "Customer City": "CUSTOMER_CITY",
    "Customer Country": "CUSTOMER_COUNTRY",
    "Customer Email": "CUSTOMER_EMAIL",
    "Customer Fname": "CUSTOMER_FNAME",
    "Customer Id": "CUSTOMER_ID",
    "Customer Lname": "CUSTOMER_LNAME",
    "Customer Password": "CUSTOMER_PASSWORD",
    "Customer Segment": "CUSTOMER_SEGMENT",
    "Customer State": "CUSTOMER_STATE",
    "Customer Street": "CUSTOMER_STREET",
    "Customer Zipcode": "CUSTOMER_ZIPCODE",
    "Department Id": "DEPARTMENT_ID",
    "Department Name": "DEPARTMENT_NAME",
    "Latitude": "LATITUDE",
    "Longitude": "LONGITUDE",
    "Market": "MARKET",
    "Order City": "ORDER_CITY",
    "Order Country": "ORDER_COUNTRY",
    "Order Customer Id": "ORDER_CUSTOMER_ID",
    "order date (DateOrders)": "ORDER_DATE",
    "Order Id": "ORDER_ID",
    "Order Item Cardprod Id": "ORDER_ITEM_CARDPROD_ID",
    "Order Item Discount": "ORDER_ITEM_DISCOUNT",
    "Order Item Discount Rate": "ORDER_ITEM_DISCOUNT_RATE",
    "Order Item Id": "ORDER_ITEM_ID",
    "Order Item Product Price": "ORDER_ITEM_PRODUCT_PRICE",
    "Order Item Profit Ratio": "ORDER_ITEM_PROFIT_RATIO",
    "Order Item Quantity": "ORDER_ITEM_QUANTITY",
    "Sales": "SALES",
    "Order Item Total": "ORDER_ITEM_TOTAL",
    "Order Profit Per Order": "ORDER_PROFIT_PER_ORDER",
    "Order Region": "ORDER_REGION",
    "Order State": "ORDER_STATE",
    "Order Status": "ORDER_STATUS",
    "Order Zipcode": "ORDER_ZIPCODE",
    "Product Card Id": "PRODUCT_CARD_ID",
    "Product Category Id": "PRODUCT_CATEGORY_ID",
    "Product Description": "PRODUCT_DESCRIPTION",
    "Product Image": "PRODUCT_IMAGE",
    "Product Name": "PRODUCT_NAME",
    "Product Price": "PRODUCT_PRICE",
    "Product Status": "PRODUCT_STATUS",
    "shipping date (DateOrders)": "SHIPPING_DATE",
    "Shipping Mode": "SHIPPING_MODE",
}

WEB_TRAFFIC_COLUMN_MAP = {
    "Product": "PRODUCT",
    "Category": "CATEGORY",
    "Date": "DATE_TIMESTAMP",
    "Month": "MONTH",
    "Hour": "HOUR",
    "Department": "DEPARTMENT",
    "ip": "IP_ADDRESS",
    "url": "URL",
}

# PII columns removed at ingestion (documented in the README)
SUPPLY_CHAIN_DROP_COLUMNS = [
    "Customer Email",
    "Customer Password",
    "Customer Street",
    "Product Description",
    "Product Image",
    "Order Zipcode",
]


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _connect():
    return snowflake.connector.connect(
        account=_env("SNOWFLAKE_ACCOUNT"),
        user=_env("SNOWFLAKE_USER"),
        password=_env("SNOWFLAKE_PASSWORD"),
        role=_env("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        warehouse=_env("SNOWFLAKE_WAREHOUSE", "SUPPLY_CHAIN_WH"),
        database=_env("SNOWFLAKE_DATABASE", "SUPPLY_CHAIN_DB"),
        schema=_env("SNOWFLAKE_SCHEMA", "RAW"),
    )


def _load_supply_chain() -> pd.DataFrame:
    df = pd.read_csv(SUPPLY_CHAIN_CSV, encoding="latin-1", low_memory=False)
    # Drop PII columns removed at ingestion (documented in the README)
    df = df.drop(columns=[c for c in SUPPLY_CHAIN_DROP_COLUMNS if c in df.columns])
    # Rename to exact dbt source column names; drop any unmapped columns
    df = df.rename(columns=SUPPLY_CHAIN_COLUMN_MAP)
    df = df[[c for c in df.columns if c in SUPPLY_CHAIN_COLUMN_MAP.values()]]
    # Keep date columns as text; dbt casts them to TIMESTAMP
    return df


def _load_web_traffic() -> pd.DataFrame:
    df = pd.read_csv(WEB_TRAFFIC_CSV, encoding="latin-1")
    df = df.rename(columns=WEB_TRAFFIC_COLUMN_MAP)
    df = df[[c for c in df.columns if c in WEB_TRAFFIC_COLUMN_MAP.values()]]
    return df


def _write_df(conn, df: pd.DataFrame, table: str) -> int:
    # Create (or replace) the target table with explicit types so dbt sees
    # NUMBER/FLOAT/VARCHAR consistently, then bulk-load via write_pandas.
    cur = conn.cursor()
    dtypes = {}
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            dtypes[col] = "TIMESTAMP"
        elif pd.api.types.is_integer_dtype(df[col]):
            dtypes[col] = "NUMBER"
        elif pd.api.types.is_float_dtype(df[col]):
            dtypes[col] = "FLOAT"
        else:
            dtypes[col] = "VARCHAR"

    ddl_cols = ", ".join(f'"{col}" {dtype}' for col, dtype in dtypes.items())
    cur.execute(f"CREATE OR REPLACE TABLE {table} ({ddl_cols})")
    cur.close()

    # Replace empty strings with None so the connector does not auto-coerce
    # blank text into 'None' / numbers; keep real NaN as NULL.
    df = df.replace(r"^\s*$", None, regex=True)

    from snowflake.connector.pandas_tools import write_pandas

    success, nchunks, nrows, _ = write_pandas(
        conn,
        df,
        table_name=table,
        database=conn.database,
        schema=conn.schema,
        quote_identifiers=False,
        chunk_size=100000,
    )
    if not success:
        raise RuntimeError(f"write_pandas failed for {table}")

    total = df.shape[0]
    print(f"Loaded {total} rows into {table}")
    return total


def main() -> None:
    conn = _connect()
    try:
        supply_chain = _load_supply_chain()
        web_traffic = _load_web_traffic()

        print(f"Supply chain columns ({len(supply_chain.columns)}): {list(supply_chain.columns)}")
        print(f"Web traffic columns ({len(web_traffic.columns)}): {list(web_traffic.columns)}")

        _write_df(conn, supply_chain, SUPPLY_CHAIN_TABLE)
        _write_df(conn, web_traffic, WEB_TRAFFIC_TABLE)
    finally:
        conn.close()

    print("Ingestion completed successfully.")


if __name__ == "__main__":
    main()
