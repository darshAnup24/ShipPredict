with source as (

    select * from {{ source('raw', 'raw_web_traffic') }}

),

web_traffic as (

    select
        -- Visit identifiers
        IP_ADDRESS                                          as ip_address,
        URL                                                 as url,

        -- Timestamp (casting from VARCHAR to TIMESTAMP)
        TO_TIMESTAMP(DATE_TIMESTAMP, 'MM/DD/YYYY HH24:MI') as visit_timestamp,

        -- Time dimensions
        MONTH                                               as visit_month,
        HOUR                                                as visit_hour,

        -- Product browsed
        PRODUCT                                             as product_name,
        CATEGORY                                            as category_name,
        DEPARTMENT                                          as department_name

    from source

)

select * from web_traffic