# dbt - fred_pipeline

Transformations BigQuery du projet FRED.

```
source fred_analytics.pouvoir_achat   (chargée par Airflow)
        │
        ▼
staging/stg_pouvoir_achat   (vue : typage, tests de base)
        │
        ▼
marts/mart_pouvoir_achat    (table : classement IDF et par département)
```

## Profil

Exemple de `~/.dbt/profiles.yml` (authentification gcloud locale) :

```yaml
fred_pipeline:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: fred-pipeline
      dataset: fred_analytics
      location: EU
      threads: 4
```

## Commandes

```bash
dbt build                       # modèles + tests
dbt build --vars '{min_ventes: 30}'
```
