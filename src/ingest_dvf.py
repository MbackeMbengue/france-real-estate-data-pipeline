import os
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


DEPARTMENT_CODE = os.getenv("DEPARTMENT_CODE", "91")
DEPARTMENT_NAME = os.getenv("DEPARTMENT_NAME", "Essonne")


# Chemins des fichiers utilisés par le pipeline.
# RAW_FILE correspond au fichier DVF source, tandis que les autres chemins
# contiennent les exports générés après filtrage, nettoyage et aggregation.
RAW_FILE = Path("data/raw/dvf_2025.txt")
OUTPUT_RAW_91 = Path(f"data/processed/dvf_{DEPARTMENT_CODE}_2025.parquet")
OUTPUT_CLEAN_91 = Path(f"data/processed/dvf_{DEPARTMENT_CODE}_2025_clean.parquet")
OUTPUT_PRIX_COMMUNE = Path(f"data/processed/prix_commune_{DEPARTMENT_CODE}.parquet")

# Console Rich partagee par toutes les fonctions d'affichage.
console = Console()


def display_dimensions(df: pd.DataFrame, df_dept: pd.DataFrame) -> None:
    """Affiche le nombre de lignes et de colonnes avant/apres filtrage."""
    table = Table(title="Dimensions des données")
    table.add_column("Jeu de données", style="bold")
    table.add_column("Lignes", justify="right")
    table.add_column("Colonnes", justify="right")

    table.add_row("DVF brut 2025", f"{df.shape[0]:,}", f"{df.shape[1]:,}")
    table.add_row(f"DVF {DEPARTMENT_NAME} {DEPARTMENT_CODE}", f"{df_dept.shape[0]:,}", f"{df_dept.shape[1]:,}")

    console.print(table)


def display_type_local_counts(df_dept: pd.DataFrame) -> None:
    """Affiche la repartition des lignes par type de bien immobilier."""
    table = Table(title="Répartition des types de biens")
    table.add_column("Type local", style="bold")
    table.add_column("Nombre de lignes", justify="right")

    # dropna=False permet aussi de compter les lignes sans type local renseigne.
    counts = df_dept["Type local"].value_counts(dropna=False)

    for type_local, count in counts.items():
        table.add_row(str(type_local), f"{count:,}")

    console.print(table)


def display_price_stats(df_clean: pd.DataFrame) -> None:
    """Affiche les statistiques descriptives du prix au m2 par type de bien."""
    # describe() calcule automatiquement count, mean, min, max et les quartiles.
    stats = df_clean.groupby("Type local")["prix_m2"].describe()

    table = Table(title="Statistiques du prix au m²")
    table.add_column("Type local", style="bold")
    table.add_column("Nombre", justify="right")
    table.add_column("Moyenne", justify="right")
    table.add_column("Médiane", justify="right")
    table.add_column("Min", justify="right")
    table.add_column("Max", justify="right")

    for type_local, row in stats.iterrows():
        table.add_row(
            str(type_local),
            f"{row['count']:,.0f}",
            f"{row['mean']:,.0f} €/m²",
            f"{row['50%']:,.0f} €/m²",
            f"{row['min']:,.0f} €/m²",
            f"{row['max']:,.0f} €/m²",
        )

    console.print(table)


def display_avg_price_by_type(df_clean: pd.DataFrame) -> None:
    """Affiche le prix moyen au m2 pour chaque type de bien."""
    avg_prices = (
        df_clean.groupby("Type local")["prix_m2"]
        .mean()
        .sort_values(ascending=False)
    )

    table = Table(title="Prix moyen au m² par type de bien")
    table.add_column("Type local", style="bold")
    table.add_column("Prix moyen au m²", justify="right")

    for type_local, price in avg_prices.items():
        table.add_row(str(type_local), f"{price:,.0f} €/m²")

    console.print(table)


def display_top_communes(prix_commune: pd.DataFrame) -> None:
    """Affiche les communes les plus cheres parmi celles avec assez de ventes."""
    # On garde seulement les communes avec au moins 20 ventes pour eviter
    # qu'une commune avec tres peu de transactions domine le classement.
    top_communes = prix_commune[prix_commune["nb_ventes"] >= 20].sort_values(
        "prix_m2_moyen",
        ascending=False
    ).head(20)

    table = Table(title="Top 20 communes les plus chères")
    table.add_column("Commune", style="bold", no_wrap=True)
    table.add_column("Type local", no_wrap=True)
    table.add_column("Nb ventes", justify="right")
    table.add_column("Prix moyen m²", justify="right")
    table.add_column("Prix médian m²", justify="right")

    for _, row in top_communes.iterrows():
        table.add_row(
            str(row["Commune"]),
            str(row["Type local"]),
            f"{row['nb_ventes']:,}",
            f"{row['prix_m2_moyen']:,.0f} €/m²",
            f"{row['prix_m2_median']:,.0f} €/m²",
        )

    console.print(table)


def main() -> None:
    """Execute toutes les etapes du pipeline DVF pour le departement 91."""
    console.print(
        Panel.fit(
            f"Pipeline local d'ingestion DVF 2025 - {DEPARTMENT_NAME} {DEPARTMENT_CODE}",
            title="France Real Estate Data Pipeline",
            style="bold blue",
        )
    )

    # Arret explicite si le fichier source n'a pas encore été place dans data/raw.
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable : {RAW_FILE}")

    console.rule("1. Lecture du fichier brut")
    # Le fichier DVF est séparé par des pipes ("|"). low_memory=False aide Pandas
    # a inferer les types de colonnes de facon plus stable sur un gros fichier.
    df = pd.read_csv(RAW_FILE, sep="|", low_memory=False)

    console.rule(f"2. Filtrage du département {DEPARTMENT_NAME}")
    # On copie le sous-ensemble pour pouvoir le modifier ensuite sans declencher
    # d'avertissement Pandas lie aux vues de DataFrame.
    df_dept = df[df["Code departement"] == DEPARTMENT_CODE].copy()

    display_dimensions(df, df_dept)
    display_type_local_counts(df_dept)

    console.rule("3. Nettoyage des données")

    # Dans les fichiers DVF francais, les decimales sont souvent encodees avec
    # une virgule. On remplace la virgule par un point avant conversion numerique.
    df_dept["Valeur fonciere"] = (
        df_dept["Valeur fonciere"]
        .astype(str)
        .str.replace(",", ".", regex=False)
    )

    # Les valeurs invalides deviennent NaN grace a errors="coerce".
    # Elles seront ensuite filtrees avec les autres lignes inutilisables.
    df_dept["Valeur fonciere"] = pd.to_numeric(
        df_dept["Valeur fonciere"],
        errors="coerce",
    )

    # Pour ce prototype, on limite l'analyse aux logements classiques.
    # Les dependances, terrains ou locaux d'activite ne sont pas comparables.
    df_dept_clean = df_dept[
        df_dept["Type local"].isin(["Appartement", "Maison"])
    ].copy()

    # Le prix au m2 n'a de sens que si la surface et la valeur fonciere sont
    # presentes et strictement positives.
    df_dept_clean = df_dept_clean[
        df_dept_clean["Surface reelle bati"].notna()
        & (df_dept_clean["Surface reelle bati"] > 0)
        & df_dept_clean["Valeur fonciere"].notna()
        & (df_dept_clean["Valeur fonciere"] > 0)
    ].copy()

    df_dept_clean["prix_m2"] = (
        df_dept_clean["Valeur fonciere"] / df_dept_clean["Surface reelle bati"]
    )

    # On memorise la taille avant/apres filtrage pour mesurer l'effet du nettoyage.
    before_outliers = len(df_dept_clean)

    # Filtrage simple des valeurs aberrantes : un prix au m2 trop faible ou trop
    # eleve indique souvent une transaction atypique ou une donnee mal renseignee.
    df_dept_clean = df_dept_clean[
        (df_dept_clean["prix_m2"] >= 500)
        & (df_dept_clean["prix_m2"] <= 15_000)
    ].copy()

    after_outliers = len(df_dept_clean)

    console.print(
        Panel.fit(
            f"Biens avant filtrage outliers : {before_outliers:,}\n"
            f"Biens après filtrage outliers : {after_outliers:,}\n"
            f"Lignes supprimées : {before_outliers - after_outliers:,}",
            title="Filtrage des valeurs aberrantes",
            style="green",
        )
    )

    display_avg_price_by_type(df_dept_clean)
    display_price_stats(df_dept_clean)

    console.rule("4. Création de la table analytique par commune")

    # Cette table resume les transactions par commune et type de bien.
    # Elle servira de base pour les analyses ou visualisations suivantes.
    prix_commune = (
        df_dept_clean
        .groupby(["Commune", "Type local"])
        .agg(
            nb_ventes=("prix_m2", "count"),
            prix_m2_moyen=("prix_m2", "mean"),
            prix_m2_median=("prix_m2", "median"),
        )
        .reset_index()
    )

    display_top_communes(prix_commune)

    console.rule("5. Sauvegarde des fichiers Parquet")

    # Creation du dossier de sortie si c'est la premiere execution du pipeline.
    OUTPUT_RAW_91.parent.mkdir(parents=True, exist_ok=True)

    # Le format Parquet conserve les types de colonnes et se lit rapidement
    # dans les outils data comme Pandas, Spark, BigQuery ou DuckDB.
    df_dept.to_parquet(OUTPUT_RAW_91, index=False)
    df_dept_clean.to_parquet(OUTPUT_CLEAN_91, index=False)
    prix_commune.to_parquet(OUTPUT_PRIX_COMMUNE, index=False)

    console.print(
        Panel.fit(
            f"Fichiers générés :\n"
            f"- {OUTPUT_RAW_91}\n"
            f"- {OUTPUT_CLEAN_91}\n"
            f"- {OUTPUT_PRIX_COMMUNE}",
            title="Export terminé",
            style="bold green",
        )
    )

if __name__ == "__main__":
    main()
