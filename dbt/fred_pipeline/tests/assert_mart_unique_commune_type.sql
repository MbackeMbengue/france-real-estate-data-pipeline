-- Une seule ligne par commune et type de logement dans le mart.
select
    code_commune,
    type_local,
    count(*) as nb_lignes
from {{ ref('mart_pouvoir_achat') }}
group by code_commune, type_local
having count(*) > 1
