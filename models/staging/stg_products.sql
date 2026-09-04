with source as (

    select * from {{ source('raw', 'raw_supply_chain') }}

),

products as (

    select distinct
        -- Primary key
        PRODUCT_CARD_ID                 as product_card_id,

        -- Product details
        PRODUCT_NAME                    as product_name,
        PRODUCT_PRICE                   as product_price,
        PRODUCT_STATUS                  as product_status,

        -- Category
        PRODUCT_CATEGORY_ID             as product_category_id,
        CATEGORY_ID                     as category_id,
        CATEGORY_NAME                   as category_name,

        -- Department
        DEPARTMENT_ID                   as department_id,
        DEPARTMENT_NAME                 as department_name

    from source

)

select * from products