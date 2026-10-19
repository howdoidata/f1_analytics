select
    driverId as driver_id,
    givenName as given_name,
    familyName as family_name,
    dateOfBirth as dob,
    nationality,
    try_cast(permanentNumber as double) as number,
    code,
    url
from {{ source('jolpica', 'drivers') }}
