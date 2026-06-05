# France Real Estate Data Pipeline

Projet Data Engineering autour des données immobilières françaises DVF.

## Objectif

Construire un pipeline complet permettant d'analyser le prix immobilier au m² en France et, à terme, le pouvoir d'achat immobilier par commune.

## Données utilisées

- DVF 2025 : demandes de valeurs foncières
- Département étudié pour le prototype : Essonne 91

## Pipeline actuel

1. Lecture du fichier DVF brut
2. Filtrage du département 91
3. Nettoyage des valeurs foncières
4. Calcul du prix au m²
5. Suppression des valeurs aberrantes
6. Agrégation par commune
7. Export en Parquet

## Technologies

- Python
- Pandas
- Rich
- PyArrow
- Parquet
- Git
- Docker à venir
- Airflow à venir
- BigQuery à venir
- dbt à venir