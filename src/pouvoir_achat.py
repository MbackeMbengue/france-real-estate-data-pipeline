"""Calcul d'un indicateur de pouvoir d'achat immobilier par commune.

Indicateur : ``surface_achetable_m2`` = revenu médian annuel (INSEE FiLoSoFi)
divisé par le prix MÉDIAN au m² (DVF). Il se lit « nombre de m² qu'une année
de revenu médian permet d'acheter dans la commune ». La médiane est utilisée
plutôt que la moyenne car elle est peu sensible aux ventes atypiques.

La jointure DVF ↔ INSEE se fait sur le code commune INSEE, pas sur le nom.
"""

import os
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

DEPARTMENT_CODES = [
    code.strip()
    for code in os.getenv(
        "DEPARTMENT_CODES", os.getenv("DEPARTMENT_CODE", "91")
    ).split(",")
    if code.strip()
]

PROCESSED_DIR = Path("data/processed")
INSEE_FILE = Path(
    "data/raw/indicateurs-territoriaux-de-precarite-par-commune-epci-departement-et-region.csv"
)
REVENU_COL = "Revenu médian (Insee FiLoSoFi 2021)"

# Paris, Lyon et Marseille sont découpés en arrondissements dans DVF. Si le
# fichier INSEE ne fournit que la commune entière, on se rabat sur celle-ci.
ARRONDISSEMENT_PARENTS = {
    "751": "75056",  # Paris 75101-75120
    "6938": "69123",  # Lyon 69381-69389
    "132": "13055",  # Marseille 13201-13216
}

console = Console()


def parent_commune(code: str) -> str:
    """Code de la commune « mère » d'un arrondissement, sinon le code lui-même."""
    for prefix, parent in ARRONDISSEMENT_PARENTS.items():
        if code.startswith(prefix) and code != parent:
            return parent
    return code


def load_insee_communes(path: Path) -> pd.DataFrame:
    insee = pd.read_csv(path, sep=";", encoding="utf-8", dtype={"ID": str})
    insee = insee[insee["Niveau géographique"] == "Commune"]
    return (
        insee[["ID", "NOM", REVENU_COL]]
        .rename(
            columns={
                "ID": "code_commune_insee",
                "NOM": "nom_commune_insee",
                REVENU_COL: "revenu_median",
            }
        )
        .assign(code_commune_insee=lambda d: d["code_commune_insee"].str.zfill(5))
        .drop_duplicates("code_commune_insee")
    )


def compute_pouvoir_achat(
    prix_commune: pd.DataFrame, insee: pd.DataFrame
) -> pd.DataFrame:
    """Joint les prix DVF aux revenus INSEE et calcule la surface achetable."""
    known = set(insee["code_commune_insee"])
    df = prix_commune.copy()
    df["code_commune_insee"] = [
        code if code in known else parent_commune(code)
        for code in df["code_commune"].astype(str)
    ]
    df = df.merge(insee, on="code_commune_insee", how="left")
    df["surface_achetable_m2"] = df["revenu_median"] / df["prix_m2_median"]
    return df.rename(columns={"Commune": "commune", "Type local": "type_local"})[
        [
            "departement",
            "code_commune",
            "commune",
            "type_local",
            "code_commune_insee",
            "nom_commune_insee",
            "nb_ventes",
            "prix_m2_moyen",
            "prix_m2_median",
            "revenu_median",
            "surface_achetable_m2",
        ]
    ]


def display_top_surface(df: pd.DataFrame) -> None:
    top = (
        df[df["nb_ventes"] >= 20]
        .sort_values("surface_achetable_m2", ascending=False)
        .head(15)
    )
    table = Table(title="Top communes - surface achetable (≥ 20 ventes)")
    table.add_column("Commune", style="bold", no_wrap=True)
    table.add_column("Type")
    table.add_column("Ventes", justify="right")
    table.add_column("Médiane m²", justify="right")
    table.add_column("Revenu médian", justify="right")
    table.add_column("Surface", justify="right")
    for _, row in top.iterrows():
        table.add_row(
            str(row["commune"]),
            str(row["type_local"]),
            f"{row['nb_ventes']:,}",
            f"{row['prix_m2_median']:,.0f} €/m²",
            f"{row['revenu_median']:,.0f} €",
            f"{row['surface_achetable_m2']:,.1f} m²",
        )
    console.print(table)


def main() -> None:
    console.print(
        Panel.fit(
            f"Pouvoir d'achat immobilier - départements {', '.join(DEPARTMENT_CODES)}",
            title="FRED",
            style="bold blue",
        )
    )
    insee = load_insee_communes(INSEE_FILE)

    for code in DEPARTMENT_CODES:
        prix_file = PROCESSED_DIR / f"prix_commune_{code}.parquet"
        if not prix_file.exists():
            console.print(f"[yellow]{prix_file} absent, département ignoré[/]")
            continue

        final = compute_pouvoir_achat(pd.read_parquet(prix_file), insee)

        matched = final["revenu_median"].notna().sum()
        total = len(final)
        console.print(
            Panel.fit(
                f"Lignes DVF : {total:,}\n"
                f"Lignes avec revenu INSEE : {matched:,}\n"
                f"Taux de correspondance : {matched / total:.1%}",
                title=f"Qualité de jointure - {code}",
                style="green" if matched == total else "yellow",
            )
        )
        display_top_surface(final)

        out = PROCESSED_DIR / f"pouvoir_achat_{code}.parquet"
        final.to_parquet(out, index=False)
        console.print(f"[green]Écrit : {out}[/]")


if __name__ == "__main__":
    main()
