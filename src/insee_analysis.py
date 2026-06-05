import pandas as pd
from pathlib import Path
from rich.console import Console
from rich.table import Table


console = Console() # Console Rich partagee pour tous les affichages.

# Chemin du fichier INSEE contenant les indicateurs de précarité par commune.
FILE = Path(
    "data/raw/indicateurs-territoriaux-de-precarite-par-commune-epci-departement-et-region.csv"
)

# Lecture du fichier INSEE.
df = pd.read_csv(FILE, sep=";", low_memory=False, encoding="utf-8")

# Affichage des dimensions du fichier INSEE.
console.print(f"\nNombre de lignes : {len(df):,}")
console.print(f"Nombre de colonnes : {len(df.columns)}")

# Affichage des colonnes du fichier INSEE.
table = Table(title="Colonnes du fichier INSEE")
table.add_column("Nom de colonne")

# Affiche chaque nom de colonne dans une ligne du tableau.
for col in df.columns:
    table.add_row(col)

console.print(table)

console.print("\nAperçu :")
console.print(df.head())

console.print("\nNiveaux géographiques :")
console.print(df["Niveau géographique"].value_counts())

console.print("\nCommunes du 91 :")
communes_91 = df[
    df["ID"].astype(str).str.startswith("91")
]

console.print(f"Nombre de communes dans le 91 : {len(communes_91):,}")
# Affichage des 20 premières communes du 91 avec leur revenu médian.
console.print(communes_91[["ID", "NOM", "Revenu médian (Insee FiLoSoFi 2021)"]].head(20))