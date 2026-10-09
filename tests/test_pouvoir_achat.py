import pandas as pd
import pytest

from pouvoir_achat import compute_pouvoir_achat, parent_commune


def test_parent_commune():
    assert parent_commune("75108") == "75056"
    assert parent_commune("69383") == "69123"
    assert parent_commune("13201") == "13055"
    assert parent_commune("91228") == "91228"


def test_join_on_code_and_median_indicator():
    prix = pd.DataFrame(
        {
            "departement": ["91", "75"],
            "code_commune": ["91228", "75108"],
            "Commune": ["EVRY-COURCOURONNES", "PARIS 08"],
            "Type local": ["Appartement", "Appartement"],
            "nb_ventes": [50, 30],
            "prix_m2_moyen": [3200.0, 12000.0],
            "prix_m2_median": [3000.0, 11000.0],
        }
    )
    insee = pd.DataFrame(
        {
            "code_commune_insee": ["91228", "75056"],
            "nom_commune_insee": ["Évry-Courcouronnes", "Paris"],
            "revenu_median": [21000.0, 33000.0],
        }
    )
    out = compute_pouvoir_achat(prix, insee).set_index("code_commune")
    assert out.loc["91228", "surface_achetable_m2"] == pytest.approx(7.0)
    assert out.loc["75108", "code_commune_insee"] == "75056"
    assert out.loc["75108", "surface_achetable_m2"] == pytest.approx(3.0)
