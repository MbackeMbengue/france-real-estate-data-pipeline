"""Exploration du fichier INSEE des indicateurs territoriaux de précarité.

Script d'exploration, hors pipeline : il affiche la structure du fichier et
les revenus médians des communes d'un département.

    DEPARTMENT_CODE=91 python src/insee_analysis.py
"""

import os
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

DEPARTMENT_CODE = os.getenv("DEPARTMENT_CODE", "91")
FILE = Path(
    "data/raw/indicateurs-territoriaux-de-precarite-par-commune-epci-departement-et-region.csv"
)
REVENU_COL = "Revenu médian (Insee FiLoSoFi 2021)"

console = Console()


def main() -> None:
    df = pd.read_csv(FILE, sep=";", low_memory=False, encoding="utf-8", dtype={"ID": str})

    console.print(f"\nNombre de lignes : {len(df):,}")
    console.print(f"Nombre de colonnes : {len(df.columns)}")

    table = Table(title="Colonnes du fichier INSEE")
    table.add_column("Nom de colonne")
    for col in df.columns:
        table.add_row(col)
    console.print(table)

    console.print("\nNiveaux géographiques :")
    console.print(df["Niveau géographique"].value_counts())

    communes = df[
        (df["Niveau géographique"] == "Commune")
        & df["ID"].str.startswith(DEPARTMENT_CODE)
    ]
    console.print(f"\nCommunes du {DEPARTMENT_CODE} : {len(communes):,}")
    console.print(communes[["ID", "NOM", REVENU_COL]].head(20))


if __name__ == "__main__":
    main()
