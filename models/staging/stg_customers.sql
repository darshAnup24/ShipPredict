with source as (

    select * from {{ source('raw', 'raw_supply_chain') }}

),

customers as (

    select distinct
        -- Primary key
        CUSTOMER_ID                     as customer_id,

        -- Customer name
        CUSTOMER_FNAME                  as customer_first_name,
        CUSTOMER_LNAME                  as customer_last_name,

        -- Segmentation
        CUSTOMER_SEGMENT                as customer_segment,

        -- Location
        CUSTOMER_CITY                   as customer_city,
        CUSTOMER_STATE                  as customer_state,
        CUSTOMER_COUNTRY                as customer_country,
        CUSTOMER_ZIPCODE                as customer_zipcode

    from source

)

select * from customers