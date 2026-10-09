select
    cast(departement as string)          as departement,
    cast(code_commune as string)         as code_commune,
    commune,
    type_local,
    cast(code_commune_insee as string)   as code_commune_insee,
    nom_commune_insee,
    cast(nb_ventes as int64)             as nb_ventes,
    cast(prix_m2_moyen as float64)       as prix_m2_moyen,
    cast(prix_m2_median as float64)      as prix_m2_median,
    cast(revenu_median as float64)       as revenu_median,
    cast(surface_achetable_m2 as float64) as surface_achetable_m2

from {{ source('fred_analytics', 'pouvoir_achat') }}
