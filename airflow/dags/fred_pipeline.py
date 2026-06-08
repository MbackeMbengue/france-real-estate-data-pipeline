from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="fred_pipeline",
    start_date=datetime(2026, 6, 1),
    schedule=None,
    catchup=False,
    tags=["fred", "data-engineering"],
) as dag:

    run_ingest_dvf = BashOperator(
        task_id="run_ingest_dvf",
        bash_command="cd /opt/airflow && python src/ingest_dvf.py",
    )

    run_pouvoir_achat = BashOperator(
        task_id="run_pouvoir_achat",
        bash_command="cd /opt/airflow && python src/pouvoir_achat.py",
    )

    run_ingest_dvf >> run_pouvoir_achat