from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()

# Chemins des fichiers utilises par le pipeline.
PRIX_FILE = Path("data/processed/prix_commune_91.parquet")
INSEE_FILE = Path(
    "data/raw/indicateurs-territoriaux-de-precarite-par-commune-epci-departement-et-region.csv"
)
OUTPUT_FILE = Path("data/processed/pouvoir_achat_91.parquet")

REVENU_COL = "Revenu médian (Insee FiLoSoFi 2021)"


def normalize_city_name(value: str) -> str:
    """Normalise les noms de communes 
    pour faciliter la jointure entre DVF et INSEE."""
    if pd.isna(value):
        return ""

    return (
        str(value)
        .upper()
        .replace("É", "E")
        .replace("È", "E")
        .replace("Ê", "E")
        .replace("Ë", "E")
        .replace("À", "A")
        .replace("Â", "A")
        .replace("Ä", "A")
        .replace("Î", "I")
        .replace("Ï", "I")
        .replace("Ô", "O")
        .replace("Ö", "O")
        .replace("Ù", "U")
        .replace("Û", "U")
        .replace("Ü", "U")
        .replace("Ç", "C")
        .replace("'", " ")
        .replace("-", " ")
        .strip()
    )


def display_top_surface(df: pd.DataFrame) -> None:
    """Affiche les communes du 91 avec la meilleure surface
       achetable pour un revenu médian donné."""
    top = (
        df[df["nb_ventes"] >= 20]
        .sort_values("surface_achetable_m2", ascending=False)
        .head(15)
    ) # On se limite aux communes avec au moins 20 ventes pour éviter les outliers extrêmes.

    # Affichage d'un tableau avec les communes, types de biens, prix au m², revenu médian et surface achetable.
    table = Table(title="Top communes - meilleure surface achetable")
    table.add_column("Commune", style="bold", no_wrap=True)
    table.add_column("Type")
    table.add_column("Ventes", justify="right")
    table.add_column("Prix m²", justify="right")
    table.add_column("Revenu médian", justify="right")
    table.add_column("Surface", justify="right")

    for _, row in top.iterrows():
        table.add_row(
            row["Commune"],
            row["Type local"],
            f"{row['nb_ventes']:,}",
            f"{row['prix_m2_moyen']:,.0f} €/m²",
            f"{row[REVENU_COL]:,.0f} €",
            f"{row['surface_achetable_m2']:,.1f} m²",
        )

    console.print(table)


def main() -> None:
    """Point d'entrée du script de calcul du pouvoir d'achat immobilier."""
    console.print(
        Panel.fit(
            "Calcul du pouvoir d'achat immobilier - Essonne 91",
            title="FRED Phase 2",
            style="bold blue",
        )
    )

    prix_commune = pd.read_parquet(PRIX_FILE)

    insee = pd.read_csv(INSEE_FILE, sep=";", encoding="utf-8")

    insee_91 = insee[
        (insee["Niveau géographique"] == "Commune")
        & (insee["ID"].astype(str).str.startswith("91"))
    ][["ID", "NOM", REVENU_COL]].copy()

    prix_commune["commune_key"] = prix_commune["Commune"].apply(normalize_city_name)
    insee_91["commune_key"] = insee_91["NOM"].apply(normalize_city_name)

    final = prix_commune.merge(
        insee_91,
        on="commune_key",
        how="left",
    )

    # Calcul de la surface achetable
    final["surface_achetable_m2"] = (
        final[REVENU_COL] / final["prix_m2_moyen"]
    )

    matched = final[REVENU_COL].notna().sum()
    total = len(final)

    console.print(
        Panel.fit(
            f"Lignes DVF : {total:,}\n"
            f"Lignes avec revenu INSEE : {matched:,}\n"
            f"Taux de correspondance : {matched / total:.1%}",
            title="Qualité de jointure",
            style="green",
        )
    )

    display_top_surface(final)

    final = final.rename(
        columns={
            "Commune": "commune",
            "Type local": "type_local",
            "ID": "code_commune_insee",
            "NOM": "nom_commune_insee",
            REVENU_COL: "revenu_median",
        }
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final.to_parquet(OUTPUT_FILE, index=False)


if __name__ == "__main__":
    main()