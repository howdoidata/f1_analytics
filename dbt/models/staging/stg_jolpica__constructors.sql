select
    constructorId as constructor_id,
    name,
    nationality,
    url
from {{ source('jolpica', 'constructors') }}
