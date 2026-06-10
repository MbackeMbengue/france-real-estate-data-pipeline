from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


PROJECT_ID = "fred-pipeline"
DATASET = "fred_analytics"
BUCKET = "fred-pipeline-data-lake"

DEPARTMENTS = {
    "75": "Paris",
    "77": "Seine-et-Marne",
    "78": "Yvelines",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val d'Oise",
}


def create_fred_dag(department_code: str, department_name: str) -> DAG:
    with DAG(
        dag_id=f"fred_pipeline_{department_code}",
        start_date=datetime(2026, 6, 1),
        schedule=None,
        catchup=False,
        tags=["fred", "data-engineering", department_code],
    ) as dag:

        run_ingest_dvf = BashOperator(
            task_id="run_ingest_dvf",
            bash_command=(
                f"cd /opt/airflow && "
                f'DEPARTMENT_CODE="{department_code}" '
                f'DEPARTMENT_NAME="{department_name}" '
                f"python src/ingest_dvf.py"
            ),
        )

        run_pouvoir_achat = BashOperator(
            task_id="run_pouvoir_achat",
            bash_command=(
                f"cd /opt/airflow && "
                f'DEPARTMENT_CODE="{department_code}" '
                f'DEPARTMENT_NAME="{department_name}" '
                f"python src/pouvoir_achat.py"
            ),
        )

        upload_to_gcs = BashOperator(
            task_id="upload_to_gcs",
            bash_command=(
                f"gcloud storage cp "
                f"/opt/airflow/data/processed/*{department_code}*.parquet "
                f"gs://{BUCKET}/processed/"
            ),
        )

        load_prix_commune = BashOperator(
            task_id="load_prix_commune_bigquery",
            bash_command=(
                f"bq load --replace "
                f"--source_format=PARQUET "
                f"{PROJECT_ID}:{DATASET}.prix_commune_{department_code} "
                f"gs://{BUCKET}/processed/prix_commune_{department_code}.parquet"
            ),
        )

        load_pouvoir_achat = BashOperator(
            task_id="load_pouvoir_achat_bigquery",
            bash_command=(
                f"bq load --replace "
                f"--source_format=PARQUET "
                f"{PROJECT_ID}:{DATASET}.pouvoir_achat_{department_code} "
                f"gs://{BUCKET}/processed/pouvoir_achat_{department_code}.parquet"
            ),
        )

        run_ingest_dvf >> run_pouvoir_achat >> upload_to_gcs
        upload_to_gcs >> [load_prix_commune, load_pouvoir_achat]

    return dag


for code, name in DEPARTMENTS.items():
    globals()[f"fred_pipeline_{code}"] = create_fred_dag(code, name)