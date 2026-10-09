-- Classement des communes par pouvoir d'achat immobilier.
-- Seuil de 20 ventes : en dessous, la médiane est trop instable pour classer.

select
    departement,
    code_commune,
    commune,
    type_local,
    nb_ventes,
    prix_m2_moyen,
    prix_m2_median,
    revenu_median,
    surface_achetable_m2,

    rank() over (
        partition by type_local
        order by surface_achetable_m2 desc
    ) as rang_surface_achetable_idf,

    rank() over (
        partition by departement, type_local
        order by surface_achetable_m2 desc
    ) as rang_surface_achetable_departement

from {{ ref('stg_pouvoir_achat') }}

where revenu_median is not null
  and prix_m2_median is not null
  and nb_ventes >= {{ var('min_ventes', 20) }}
