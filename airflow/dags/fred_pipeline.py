"""DAG FRED : DVF + INSEE -> Parquet -> GCS -> BigQuery.

Un seul DAG pour toute l'Île-de-France :
- le fichier DVF national n'est lu qu'une fois (ingest_dvf traite tous les
  départements demandés en un passage) ;
- les fichiers Parquet de tous les départements sont chargés dans deux tables
  BigQuery uniques (``prix_commune`` et ``pouvoir_achat``) grâce à une URI
  avec joker. La colonne ``departement`` permet de filtrer en aval (dbt).

Les départements traités sont un paramètre du DAG : on peut relancer un seul
département depuis l'UI Airflow (« Trigger DAG w/ config »).
"""

from datetime import datetime

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator

PROJECT_ID = "fred-pipeline"
DATASET = "fred_analytics"
BUCKET = "fred-pipeline-data-lake"

IDF_DEPARTMENTS = "75,77,78,91,92,93,94,95"

ENV = 'DEPARTMENT_CODES="{{ params.departements }}" DVF_YEAR="{{ params.annee }}"'

with DAG(
    dag_id="fred_pipeline_idf",
    start_date=datetime(2026, 6, 1),
    schedule=None,
    catchup=False,
    tags=["fred", "data-engineering"],
    params={
        "departements": Param(
            IDF_DEPARTMENTS,
            type="string",
            description="Codes département séparés par des virgules",
        ),
        "annee": Param("2025", type="string", description="Millésime DVF"),
    },
) as dag:
    run_ingest_dvf = BashOperator(
        task_id="run_ingest_dvf",
        bash_command=f"cd /opt/airflow && {ENV} python src/ingest_dvf.py",
    )

    run_pouvoir_achat = BashOperator(
        task_id="run_pouvoir_achat",
        bash_command=f"cd /opt/airflow && {ENV} python src/pouvoir_achat.py",
    )

    upload_to_gcs = BashOperator(
        task_id="upload_to_gcs",
        bash_command=(
            "gcloud storage cp /opt/airflow/data/processed/*.parquet "
            f"gs://{BUCKET}/processed/"
        ),
    )

    loads = [
        BashOperator(
            task_id=f"load_{table}_bigquery",
            bash_command=(
                "bq load --replace --source_format=PARQUET "
                f"{PROJECT_ID}:{DATASET}.{table} "
                f'"gs://{BUCKET}/processed/{table}_*.parquet"'
            ),
        )
        for table in ("prix_commune", "pouvoir_achat")
    ]

    run_ingest_dvf >> run_pouvoir_achat >> upload_to_gcs >> loads
