import pandas as pd
import pytest

from ingest_dvf import aggregate_by_commune, build_code_insee, clean_dvf


def row(**overrides):
    base = {
        "Date mutation": "15/03/2025",
        "No disposition": "000001",
        "Nature mutation": "Vente",
        "Valeur fonciere": "300000,00",
        "No voie": "1",
        "Voie": "RUE DE LA PAIX",
        "Commune": "EVRY-COURCOURONNES",
        "Code departement": "91",
        "Code commune": "228",
        "Type local": "Appartement",
        "Surface reelle bati": "60",
        "Nombre pieces principales": "3",
    }
    base.update(overrides)
    return base


def test_simple_sale():
    ventes, _ = clean_dvf(pd.DataFrame([row()]))
    assert len(ventes) == 1
    assert ventes.loc[0, "prix_m2"] == pytest.approx(5000)
    assert ventes.loc[0, "code_commune"] == "91228"


def test_same_local_on_several_parcels_counted_once():
    # Une maison sur deux parcelles : deux lignes identiques côté local.
    df = pd.DataFrame(
        [
            row(**{"Type local": "Maison", "Surface reelle bati": "100"}),
            row(**{"Type local": "Maison", "Surface reelle bati": "100"}),
        ]
    )
    ventes, _ = clean_dvf(df)
    assert len(ventes) == 1
    assert ventes.loc[0, "prix_m2"] == pytest.approx(3000)


def test_dependance_is_allowed():
    df = pd.DataFrame(
        [row(), row(**{"Type local": "Dépendance", "Surface reelle bati": None})]
    )
    ventes, _ = clean_dvf(df)
    assert len(ventes) == 1
    assert ventes.loc[0, "Type local"] == "Appartement"


def test_multi_logements_mutation_is_excluded():
    # Immeuble de deux appartements vendu 300 000 € au total : la valeur est
    # répétée sur chaque ligne, le prix au m² par ligne serait faux.
    df = pd.DataFrame(
        [
            row(**{"Surface reelle bati": "60"}),
            row(**{"Surface reelle bati": "40", "Nombre pieces principales": "2"}),
        ]
    )
    ventes, stats = clean_dvf(df)
    assert ventes.empty
    assert stats["mutations"] == 1
    assert stats["mutations_logement_unique"] == 0


def test_mutation_with_commercial_local_is_excluded():
    df = pd.DataFrame(
        [
            row(),
            row(
                **{
                    "Type local": "Local industriel. commercial ou assimilé",
                    "Surface reelle bati": "50",
                }
            ),
        ]
    )
    ventes, _ = clean_dvf(df)
    assert ventes.empty


def test_non_sale_and_outliers_are_excluded():
    df = pd.DataFrame(
        [
            row(**{"Nature mutation": "Echange"}),
            row(**{"No disposition": "2", "Valeur fonciere": "1000"}),  # 17 €/m²
            row(**{"No disposition": "3", "Valeur fonciere": "6000000"}),  # 100k €/m²
        ]
    )
    ventes, _ = clean_dvf(df)
    assert ventes.empty


def test_build_code_insee():
    dep = pd.Series(["91", "1", "971", "2A"])
    com = pd.Series(["5", "053", "101", "4"])
    assert build_code_insee(dep, com).tolist() == ["91005", "01053", "97101", "2A004"]


def test_aggregate_by_commune_uses_code():
    df = pd.DataFrame(
        [
            row(),
            row(**{"No disposition": "2", "Valeur fonciere": "240000"}),
            row(**{"No disposition": "3", "Valeur fonciere": "180000"}),
        ]
    )
    ventes, _ = clean_dvf(df)
    agg = aggregate_by_commune(ventes)
    assert len(agg) == 1
    assert agg.loc[0, "nb_ventes"] == 3
    assert agg.loc[0, "prix_m2_median"] == pytest.approx(4000)
