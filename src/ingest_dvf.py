"""Ingestion et nettoyage des données DVF (Demandes de Valeurs Foncières).

Points d'attention sur le format DVF brut (fichier ``valeursfoncieres-AAAA.txt``) :

- Une même vente (mutation) est répartie sur PLUSIEURS lignes : une par local,
  par lot ou par parcelle. La ``Valeur fonciere`` est celle de la mutation
  entière et elle est répétée sur chaque ligne. Diviser cette valeur par la
  surface d'une seule ligne gonfle donc le prix au m² (appartement + parking,
  immeuble de plusieurs logements, maison sur plusieurs parcelles...).
- Le fichier contient aussi des échanges, adjudications, expropriations, etc.

Le nettoyage ci-dessous reconstitue donc les mutations et ne garde que les
ventes portant sur UN SEUL logement (appartement ou maison), éventuellement
accompagné de dépendances (cave, parking). C'est l'approche habituelle pour
calculer un prix au m² fiable à partir de DVF.
"""

import os
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------

# Liste de départements séparés par des virgules (ex. "75,77,91").
# DEPARTMENT_CODE reste accepté pour compatibilité avec l'ancienne version.
DEPARTMENT_CODES = [
    code.strip()
    for code in os.getenv(
        "DEPARTMENT_CODES", os.getenv("DEPARTMENT_CODE", "91")
    ).split(",")
    if code.strip()
]

YEAR = os.getenv("DVF_YEAR", "2025")
RAW_FILE = Path(os.getenv("DVF_RAW_FILE", f"data/raw/dvf_{YEAR}.txt"))
PROCESSED_DIR = Path("data/processed")

HABITATION_TYPES = ["Appartement", "Maison"]
DEPENDANCE_TYPE = "Dépendance"

# Bornes de prix au m² en dehors desquelles une vente est considérée comme
# atypique (erreur de saisie, vente entre proches, bien très dégradé...).
PRIX_M2_MIN = 500
PRIX_M2_MAX = 15_000

# Colonnes qui identifient une mutation dans le fichier DVF public
# (il n'y a pas d'identifiant de mutation explicite dans ce format).
MUTATION_KEY = [
    "Date mutation",
    "No disposition",
    "Valeur fonciere",
    "Code departement",
    "Code commune",
]

# Colonnes qui identifient un local à l'intérieur d'une mutation. Un même local
# peut apparaître plusieurs fois (une ligne par parcelle / nature de culture).
LOCAL_KEY = MUTATION_KEY + [
    "Type local",
    "Surface reelle bati",
    "Nombre pieces principales",
    "No voie",
    "Voie",
]

USECOLS = sorted(set(LOCAL_KEY + ["Nature mutation", "Commune"]))

console = Console()


# ---------------------------------------------------------------------------
# Fonctions de transformation (pures, testées dans tests/test_ingest_dvf.py)
# ---------------------------------------------------------------------------


def to_number(series: pd.Series) -> pd.Series:
    """Convertit une colonne DVF en nombre (les décimales utilisent une virgule)."""
    return pd.to_numeric(
        series.astype("string").str.replace(",", ".", regex=False),
        errors="coerce",
    )


def build_code_insee(departement: pd.Series, commune: pd.Series) -> pd.Series:
    """Construit le code commune INSEE (5 caractères) à partir de DVF.

    Métropole : "91" + "174" -> "91174".
    Outre-mer (département sur 3 caractères) : "971" + "101" -> "97101".
    """
    dep = departement.astype("string").str.strip().str.zfill(2)
    com = (
        commune.astype("string")
        .str.strip()
        .str.replace(r"\..*$", "", regex=True)  # "228.0" -> "228"
        .str.zfill(3)
    )
    outre_mer = dep.str.len() == 3
    return (dep + com).where(~outre_mer, dep.str[:2] + com)


def clean_dvf(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Retourne une ligne par vente d'un logement unique, avec son prix au m².

    Renvoie aussi un dictionnaire de comptages pour suivre l'effet de chaque
    étape de nettoyage.
    """
    stats: dict[str, int] = {"lignes_brutes": len(df)}

    df = df[df["Nature mutation"] == "Vente"].copy()
    stats["lignes_ventes"] = len(df)

    df["Valeur fonciere"] = to_number(df["Valeur fonciere"])
    df["Surface reelle bati"] = to_number(df["Surface reelle bati"])
    df = df[df["Valeur fonciere"].notna() & (df["Valeur fonciere"] > 0)]

    df["mutation_id"] = df.groupby(MUTATION_KEY, dropna=False).ngroup()
    stats["mutations"] = df["mutation_id"].nunique()

    locaux = df[df["Type local"].notna()].drop_duplicates(
        subset=LOCAL_KEY + ["mutation_id"]
    )

    # Une mutation est exploitable si elle contient exactement un logement et,
    # en dehors des dépendances, aucun autre local (commerce, bureau...).
    is_habitation = locaux["Type local"].isin(HABITATION_TYPES)
    is_other = ~is_habitation & (locaux["Type local"] != DEPENDANCE_TYPE)
    par_mutation = (
        locaux.assign(_hab=is_habitation, _other=is_other)
        .groupby("mutation_id")[["_hab", "_other"]]
        .sum()
    )
    mutations_ok = par_mutation[
        (par_mutation["_hab"] == 1) & (par_mutation["_other"] == 0)
    ].index
    stats["mutations_logement_unique"] = len(mutations_ok)

    ventes = locaux[
        is_habitation & locaux["mutation_id"].isin(mutations_ok)
    ].copy()
    ventes = ventes[
        ventes["Surface reelle bati"].notna() & (ventes["Surface reelle bati"] > 0)
    ]

    ventes["prix_m2"] = ventes["Valeur fonciere"] / ventes["Surface reelle bati"]
    stats["ventes_avant_outliers"] = len(ventes)

    ventes = ventes[ventes["prix_m2"].between(PRIX_M2_MIN, PRIX_M2_MAX)].copy()
    stats["ventes_finales"] = len(ventes)

    ventes["departement"] = ventes["Code departement"].astype("string").str.strip()
    ventes["code_commune"] = build_code_insee(
        ventes["Code departement"], ventes["Code commune"]
    )
    return ventes.reset_index(drop=True), stats


def aggregate_by_commune(ventes: pd.DataFrame) -> pd.DataFrame:
    """Agrège les ventes par commune (code INSEE) et type de logement."""
    return (
        ventes.groupby(["departement", "code_commune", "Type local"])
        .agg(
            Commune=("Commune", "first"),
            nb_ventes=("prix_m2", "size"),
            prix_m2_moyen=("prix_m2", "mean"),
            prix_m2_median=("prix_m2", "median"),
        )
        .reset_index()
    )


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------


def display_cleaning_stats(stats: dict[str, int], label: str) -> None:
    labels = {
        "lignes_brutes": "Lignes DVF du département",
        "lignes_ventes": "Lignes de type « Vente »",
        "mutations": "Ventes distinctes (mutations)",
        "mutations_logement_unique": "Ventes d'un logement unique",
        "ventes_avant_outliers": "… avec surface renseignée",
        "ventes_finales": f"… avec prix entre {PRIX_M2_MIN} et {PRIX_M2_MAX:,} €/m²",
    }
    table = Table(title=f"Nettoyage - {label}")
    table.add_column("Étape", style="bold")
    table.add_column("Nombre", justify="right")
    for key, text in labels.items():
        table.add_row(text, f"{stats[key]:,}")
    console.print(table)


def display_price_stats(ventes: pd.DataFrame) -> None:
    stats = ventes.groupby("Type local")["prix_m2"].describe()
    table = Table(title="Statistiques du prix au m²")
    table.add_column("Type local", style="bold")
    for col in ["Ventes", "Moyenne", "Médiane", "Min", "Max"]:
        table.add_column(col, justify="right")
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


def display_top_communes(prix_commune: pd.DataFrame) -> None:
    top = (
        prix_commune[prix_commune["nb_ventes"] >= 20]
        .sort_values("prix_m2_median", ascending=False)
        .head(20)
    )
    table = Table(title="Top 20 communes les plus chères (médiane, ≥ 20 ventes)")
    table.add_column("Commune", style="bold", no_wrap=True)
    table.add_column("Type local", no_wrap=True)
    table.add_column("Ventes", justify="right")
    table.add_column("Médiane m²", justify="right")
    table.add_column("Moyenne m²", justify="right")
    for _, row in top.iterrows():
        table.add_row(
            str(row["Commune"]),
            str(row["Type local"]),
            f"{row['nb_ventes']:,}",
            f"{row['prix_m2_median']:,.0f} €/m²",
            f"{row['prix_m2_moyen']:,.0f} €/m²",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def main() -> None:
    console.print(
        Panel.fit(
            f"Ingestion DVF {YEAR} - départements {', '.join(DEPARTMENT_CODES)}",
            title="France Real Estate Data Pipeline",
            style="bold blue",
        )
    )

    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {RAW_FILE} (voir README, section Données)"
        )

    console.rule("1. Lecture du fichier brut")
    # Lecture unique du fichier national, en texte, et seulement des colonnes
    # utiles : les codes (départements, communes) gardent leurs zéros initiaux.
    raw = pd.read_csv(RAW_FILE, sep="|", dtype=str, usecols=USECOLS)
    raw["Code departement"] = raw["Code departement"].str.strip()
    console.print(f"Lignes lues : {len(raw):,}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    for code in DEPARTMENT_CODES:
        console.rule(f"2. Département {code}")
        df_dept = raw[raw["Code departement"] == code]
        if df_dept.empty:
            console.print(f"[yellow]Aucune ligne pour le département {code}[/]")
            continue

        ventes, stats = clean_dvf(df_dept)
        display_cleaning_stats(stats, code)
        display_price_stats(ventes)

        prix_commune = aggregate_by_commune(ventes)
        display_top_communes(prix_commune)

        out_clean = PROCESSED_DIR / f"dvf_{code}_{YEAR}_clean.parquet"
        out_prix = PROCESSED_DIR / f"prix_commune_{code}.parquet"
        ventes.drop(columns=["mutation_id"]).to_parquet(out_clean, index=False)
        prix_commune.to_parquet(out_prix, index=False)
        console.print(f"[green]Écrit : {out_clean}, {out_prix}[/]")


if __name__ == "__main__":
    main()
