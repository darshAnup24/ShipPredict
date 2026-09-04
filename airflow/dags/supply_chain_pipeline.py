from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Default arguments for the DAG
default_args = {
    'owner': 'prajwal_gorkhar',
    'depends_on_past': False,
    'email': ['pgorkhar@asu.edu'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    'supply_chain_risk_pipeline',
    default_args=default_args,
    description='Supply Chain Late Delivery Risk Intelligence Pipeline - Python ingestion > dbt build > dbt test',
    schedule_interval='0 6 * * *',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['supply_chain', 'dbt', 'snowflake'],
)

# Task 1 - Load raw data to Snowflake
load_to_snowflake = BashOperator(
    task_id='load_raw_data_to_snowflake',
    bash_command='cd /Users/prajwalshekar/supply-chain-risk-intelligence && python3 ingestion/load_to_snowflake.py',
    dag=dag,
)

# Task 2 - dbt build (runs all models)
dbt_build = BashOperator(
    task_id='dbt_build',
    bash_command='''
        cd /Users/prajwalshekar/supply-chain-risk-intelligence &&
        export DBT_PROFILES_DIR=~/.dbt &&
        dbt build --project-dir . --profiles-dir ~/.dbt
    ''',
    dag=dag,
)

# Task 3 - dbt test (runs all 86 tests)
dbt_test = BashOperator(
    task_id='dbt_test',
    bash_command='''
        cd /Users/prajwalshekar/supply-chain-risk-intelligence &&
        export DBT_PROFILES_DIR=~/.dbt &&
        dbt test --project-dir . --profiles-dir ~/.dbt
    ''',
    dag=dag,
)

# Task 4 - Verify row counts in Snowflake
verify_counts = BashOperator(
    task_id='verify_row_counts',
    bash_command='''
        python3 -c "
import snowflake.connector
import os
conn = snowflake.connector.connect(
    account='svibshq-xeb14052',
    user='PGORKHAR22',
    password=os.environ.get('SNOWFLAKE_PASSWORD', ''),
    role='ACCOUNTADMIN',
    warehouse='SUPPLY_CHAIN_WH',
    database='SUPPLY_CHAIN_DB'
)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM SUPPLY_CHAIN_DB.RAW.RAW_SUPPLY_CHAIN')
raw_count = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM SUPPLY_CHAIN_DB.STAGING.STG_ORDERS')
stg_count = cur.fetchone()[0]
print(f'RAW_SUPPLY_CHAIN rows: {raw_count}')
print(f'STG_ORDERS rows: {stg_count}')
assert raw_count == 180519, f'Expected 180519 rows, got {raw_count}'
assert stg_count == 180519, f'Expected 180519 rows, got {stg_count}'
print('ALL ROW COUNTS VERIFIED SUCCESSFULLY!')
conn.close()
"
    ''',
    dag=dag,
)

# Pipeline order: load -> dbt build -> dbt test -> verify
load_to_snowflake >> dbt_build >> dbt_test >> verify_counts