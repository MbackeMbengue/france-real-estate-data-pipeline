from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


PROJECT_ID = "fred-pipeline"
DATASET = "fred_analytics"
BUCKET = "fred-pipeline-data-lake"


with DAG(
    dag_id="fred_pipeline",
    start_date=datetime(2026, 6, 1),
    schedule=None,
    catchup=False,
    tags=["fred", "data-engineering"],
) as dag:

    run_pouvoir_achat = BashOperator(
        task_id="run_pouvoir_achat",
        bash_command="cd /opt/airflow && python src/pouvoir_achat.py",
    )

    upload_to_gcs = BashOperator(
        task_id="upload_to_gcs",
        bash_command=f"""
        gcloud storage cp /opt/airflow/data/processed/*.parquet gs://{BUCKET}/processed/
        """,
    )

    load_prix_commune = BashOperator(
        task_id="load_prix_commune_bigquery",
        bash_command=f"""
        bq load --replace \
          --source_format=PARQUET \
          {PROJECT_ID}:{DATASET}.prix_commune_91 \
          gs://{BUCKET}/processed/prix_commune_91.parquet
        """,
    )

    load_pouvoir_achat = BashOperator(
        task_id="load_pouvoir_achat_bigquery",
        bash_command=f"""
        bq load --replace \
          --source_format=PARQUET \
          {PROJECT_ID}:{DATASET}.pouvoir_achat_91 \
          gs://{BUCKET}/processed/pouvoir_achat_91.parquet
        """,
    )

    run_pouvoir_achat >> upload_to_gcs
    upload_to_gcs >> [load_prix_commune, load_pouvoir_achat]