from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

# Absolute path to this project (must match this laptop's location)
PROJECT_ROOT = "/home/madhav/Documents/codehemangstyle/supply-chain-risk-intelligence"

# PATH that makes `python3` and `dbt` resolvable from BashOperator subprocesses
PATH_EXPORT = 'export PATH="$HOME/.local/bin:/usr/bin:/bin:$PATH"'

# Ensures the SNOWFLAKE_* variables from .env are present for every task
LOAD_ENV = "cd {root} && set -a && . ./.env && set +a".format(root=PROJECT_ROOT)

# Default arguments for the DAG
default_args = {
    'owner': 'madhav',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition - runs daily at 06:00
dag = DAG(
    'supply_chain_risk_pipeline',
    default_args=default_args,
    description='Supply Chain Late Delivery Risk Intelligence Pipeline - Python ingestion > dbt build > dbt test',
    schedule_interval='0 6 * * *',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['supply_chain', 'dbt', 'snowflake'],
)

# Task 1 - Load that day's raw data to Snowflake
# DATA_DATE={{ ds }} makes each scheduled run ingest data/<logical-date>/,
# so every daily run processes that specific day's snapshot.
load_to_snowflake = BashOperator(
    task_id='load_raw_data_to_snowflake',
    bash_command=LOAD_ENV + "\n"
    + PATH_EXPORT + "\n"
    + 'echo "=== Loading raw data for {{ ds }} ==="\n'
    + "cd {root}\n".format(root=PROJECT_ROOT)
    + 'echo "=== Source: data/{{ ds }}/ ==="\n'
    + 'DATA_DATE={{ ds }} python3 ingestion/load_to_snowflake.py\n',
    dag=dag,
)

# Task 2 - dbt build (runs all models)
dbt_build = BashOperator(
    task_id='dbt_build',
    bash_command=PATH_EXPORT + "\n"
    + "cd {root}\n".format(root=PROJECT_ROOT)
    + "export DBT_PROFILES_DIR=$HOME/.dbt\n"
    + 'echo "=== Running dbt build for {{ ds }} ==="\n'
    + "dbt build --project-dir {root} --profiles-dir $HOME/.dbt\n".format(root=PROJECT_ROOT),
    dag=dag,
)

# Task 3 - dbt test (runs all data quality tests)
dbt_test = BashOperator(
    task_id='dbt_test',
    bash_command=PATH_EXPORT + "\n"
    + "cd {root}\n".format(root=PROJECT_ROOT)
    + "export DBT_PROFILES_DIR=$HOME/.dbt\n"
    + 'echo "=== Running dbt test for {{ ds }} ==="\n'
    + "dbt test --project-dir {root} --profiles-dir $HOME/.dbt\n".format(root=PROJECT_ROOT),
    dag=dag,
)

# Task 4 - Verify row counts in Snowflake
verify_counts = BashOperator(
    task_id='verify_row_counts',
    bash_command=LOAD_ENV + "\n"
    + PATH_EXPORT + "\n"
    + "cd {root}\n".format(root=PROJECT_ROOT)
    + '''python3 -c "
import snowflake.connector
import os
conn = snowflake.connector.connect(
    account=os.environ['SNOWFLAKE_ACCOUNT'],
    user=os.environ['SNOWFLAKE_USER'],
    password=os.environ['SNOWFLAKE_PASSWORD'],
    role=os.environ.get('SNOWFLAKE_ROLE', 'ACCOUNTADMIN'),
    warehouse=os.environ['SNOWFLAKE_WAREHOUSE'],
    database=os.environ['SNOWFLAKE_DATABASE'],
)
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM SUPPLY_CHAIN_DB.RAW.RAW_SUPPLY_CHAIN')
raw_sc = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM SUPPLY_CHAIN_DB.RAW.RAW_WEB_TRAFFIC')
raw_wt = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM SUPPLY_CHAIN_DB.STAGING.STG_ORDERS')
stg = cur.fetchone()[0]
print('RAW_SUPPLY_CHAIN rows: ' + str(raw_sc))
print('RAW_WEB_TRAFFIC rows: ' + str(raw_wt))
print('STG_ORDERS rows: ' + str(stg))
assert raw_sc > 0 and stg > 0, 'Pipeline loaded zero rows - check upstream ingestion'
assert raw_sc == stg, 'Raw (' + str(raw_sc) + ') vs staging (' + str(stg) + ') mismatch'
print('ROW COUNTS VERIFIED SUCCESSFULLY!')
conn.close()
"
''',
    dag=dag,
)

# Pipeline order: load -> dbt build -> dbt test -> verify
load_to_snowflake >> dbt_build >> dbt_test >> verify_counts