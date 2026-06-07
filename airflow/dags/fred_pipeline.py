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

    start = BashOperator(
        task_id="start_pipeline",
        bash_command="echo 'FRED Pipeline Started'",
    )

    end = BashOperator(
        task_id="end_pipeline",
        bash_command="echo 'FRED Pipeline Finished'",
    )

    start >> end