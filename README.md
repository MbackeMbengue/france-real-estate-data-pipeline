# FRED - France Real Estate Data Pipeline

Pipeline de data engineering sur les transactions immobilières françaises
(DVF) croisées avec les revenus INSEE, pour mesurer le **pouvoir d'achat
immobilier par commune** en Île-de-France.

> Question métier : combien de m² une année de revenu médian permet-elle
> d'acheter dans chaque commune ?

## Architecture

```
DVF (data.gouv.fr) ─┐
                    ├─► Python (pandas) ─► Parquet ─► GCS ─► BigQuery ─► dbt ─► mart
INSEE (FiLoSoFi) ───┘        ▲                                              │
                             └──────────── orchestré par Airflow ───────────┘
Infrastructure GCP (bucket, dataset) : Terraform
```

| Étape | Outil | Fichier |
|---|---|---|
| Ingestion et nettoyage DVF | Python, pandas | `src/ingest_dvf.py` |
| Jointure INSEE et indicateur | Python, pandas | `src/pouvoir_achat.py` |
| Orchestration | Airflow 2.9 (Docker) | `airflow/dags/fred_pipeline.py` |
| Data lake / entrepôt | GCS, BigQuery | `terraform/` |
| Modélisation et tests SQL | dbt | `dbt/fred_pipeline/` |
| Qualité du code | pytest, ruff, GitHub Actions | `tests/`, `.github/workflows/ci.yml` |

## Données

| Source | Fichier attendu |
|---|---|
| [Demandes de valeurs foncières (DVF)](https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/), millésime 2025 | `data/raw/dvf_2025.txt` |
| Indicateurs territoriaux de précarité par commune, data.gouv.fr (revenu médian INSEE FiLoSoFi 2021) | `data/raw/indicateurs-territoriaux-de-precarite-par-commune-epci-departement-et-region.csv` |

Les fichiers bruts ne sont pas versionnés (voir `.gitignore`).

## Choix de nettoyage DVF

Dans le fichier DVF public, **une vente occupe plusieurs lignes** (une par
local, lot ou parcelle) et la valeur foncière de la vente entière est répétée
sur chacune. Diviser cette valeur par la surface d'une seule ligne surestime
fortement le prix au m² (appartement + parking, immeuble de plusieurs
logements, maison sur plusieurs parcelles).

Le pipeline :

1. ne garde que les mutations de nature « Vente » ;
2. reconstitue chaque vente (date, n° de disposition, valeur, commune) ;
3. dédoublonne les locaux répétés sur plusieurs parcelles ;
4. ne garde que les ventes d'**un seul logement** (appartement ou maison),
   éventuellement avec des dépendances, et sans local commercial ;
5. calcule le prix au m² et écarte les valeurs hors 500 - 15 000 €/m² ;
6. agrège par **code commune INSEE** et type de logement (moyenne et médiane).

La jointure avec l'INSEE se fait sur le code commune (et non sur le nom).
Pour Paris, Lyon et Marseille, les arrondissements DVF sont rattachés à la
commune si l'INSEE ne fournit pas le détail par arrondissement.

**Indicateur** : `surface_achetable_m2 = revenu médian annuel / prix médian au m²`.

## Lancer le projet

### En local (Python)

```bash
pip install -r requirements-dev.txt
DEPARTMENT_CODES=91,75 python src/ingest_dvf.py
DEPARTMENT_CODES=91,75 python src/pouvoir_achat.py
pytest
```

### Infrastructure GCP

```bash
cd terraform
terraform init
terraform apply -var project_id=fred-pipeline \
  -var bucket_name=fred-pipeline-data-lake \
  -var bigquery_dataset=fred_analytics
```

### Airflow

```bash
cd airflow
docker compose up --build
```

Interface sur http://localhost:8080, DAG `fred_pipeline_idf`. Les
départements à traiter sont un paramètre du DAG (par défaut toute
l'Île-de-France). Le DAG utilise les identifiants `gcloud` de la machine hôte.

### dbt

Voir `dbt/fred_pipeline/README.md` pour le profil BigQuery, puis :

```bash
cd dbt/fred_pipeline
dbt build
```

## Limites connues

- Le fichier `dashboard/v_pouvoir_achat_idf.csv` a été produit avec l'ancienne
  version du nettoyage et doit être régénéré.
- Le revenu médian (2021) et les prix (2025) ne portent pas sur la même année.
- L'indicateur ne tient compte ni de l'apport, ni du crédit, ni des frais de
  notaire : c'est un indicateur comparatif entre communes, pas une capacité
  d'emprunt.
