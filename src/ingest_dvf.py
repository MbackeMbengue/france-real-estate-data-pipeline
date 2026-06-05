from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


RAW_FILE = Path("data/raw/dvf_2025.txt")
OUTPUT_RAW_91 = Path("data/processed/dvf_91_2025.parquet")
OUTPUT_CLEAN_91 = Path("data/processed/dvf_91_2025_clean.parquet")
OUTPUT_PRIX_COMMUNE = Path("data/processed/prix_commune_91.parquet")

console = Console()


def display_dimensions(df: pd.DataFrame, df_91: pd.DataFrame) -> None:
    table = Table(title="Dimensions des données")
    table.add_column("Jeu de données", style="bold")
    table.add_column("Lignes", justify="right")
    table.add_column("Colonnes", justify="right")

    table.add_row("DVF brut 2025", f"{df.shape[0]:,}", f"{df.shape[1]:,}")
    table.add_row("DVF Essonne 91", f"{df_91.shape[0]:,}", f"{df_91.shape[1]:,}")

    console.print(table)


def display_type_local_counts(df_91: pd.DataFrame) -> None:
    table = Table(title="Répartition des types de biens")
    table.add_column("Type local", style="bold")
    table.add_column("Nombre de lignes", justify="right")

    counts = df_91["Type local"].value_counts(dropna=False)

    for type_local, count in counts.items():
        table.add_row(str(type_local), f"{count:,}")

    console.print(table)


def display_price_stats(df_clean: pd.DataFrame) -> None:
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
    top_communes = prix_commune[prix_commune["nb_ventes"] >= 20].sort_values(
        "prix_m2_moyen",
        ascending=False
    ).head(20)

    table = Table(title="Top 20 communes les plus chères")
    table.add_column("Commune", style="bold", no_wrap=True)
    table.add_column("Type local",no_wrap=True)
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
    console.print(
        Panel.fit(
            "Pipeline local d'ingestion DVF 2025 - Essonne 91",
            title="France Real Estate Data Pipeline",
            style="bold blue",
        )
    )

    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable : {RAW_FILE}")

    console.rule("1. Lecture du fichier brut")
    df = pd.read_csv(RAW_FILE, sep="|", low_memory=False)

    console.rule("2. Filtrage du département 91")
    df_91 = df[df["Code departement"] == "91"].copy()

    display_dimensions(df, df_91)
    display_type_local_counts(df_91)

    console.rule("3. Nettoyage des données")

    df_91["Valeur fonciere"] = (
        df_91["Valeur fonciere"]
        .astype(str)
        .str.replace(",", ".", regex=False)
    )

    df_91["Valeur fonciere"] = pd.to_numeric(
        df_91["Valeur fonciere"],
        errors="coerce",
    )

    df_91_clean = df_91[
        df_91["Type local"].isin(["Appartement", "Maison"])
    ].copy()

    df_91_clean = df_91_clean[
        df_91_clean["Surface reelle bati"].notna()
        & (df_91_clean["Surface reelle bati"] > 0)
        & df_91_clean["Valeur fonciere"].notna()
        & (df_91_clean["Valeur fonciere"] > 0)
    ].copy()

    df_91_clean["prix_m2"] = (
        df_91_clean["Valeur fonciere"] / df_91_clean["Surface reelle bati"]
    )

    before_outliers = len(df_91_clean)

    df_91_clean = df_91_clean[
        (df_91_clean["prix_m2"] >= 500)
        & (df_91_clean["prix_m2"] <= 15_000)
    ].copy()

    after_outliers = len(df_91_clean)

    console.print(
        Panel.fit(
            f"Biens avant filtrage outliers : {before_outliers:,}\n"
            f"Biens après filtrage outliers : {after_outliers:,}\n"
            f"Lignes supprimées : {before_outliers - after_outliers:,}",
            title="Filtrage des valeurs aberrantes",
            style="green",
        )
    )

    display_avg_price_by_type(df_91_clean)
    display_price_stats(df_91_clean)

    console.rule("4. Création de la table analytique par commune")

    prix_commune = (
        df_91_clean
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

    OUTPUT_RAW_91.parent.mkdir(parents=True, exist_ok=True)

    df_91.to_parquet(OUTPUT_RAW_91, index=False)
    df_91_clean.to_parquet(OUTPUT_CLEAN_91, index=False)
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