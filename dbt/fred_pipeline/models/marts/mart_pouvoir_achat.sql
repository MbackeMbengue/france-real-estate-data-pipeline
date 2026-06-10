{{ config(materialized='table') }}

select
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
    ) as rang_surface_achetable

from {{ source('fred_analytics', 'pouvoir_achat_91') }}

where revenu_median is not null
  and prix_m2_moyen is not null
  and surface_achetable_m2 is not null