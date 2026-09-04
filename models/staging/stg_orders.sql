with source as (

    select * from {{ source('raw', 'raw_supply_chain') }}

),

renamed as (

    select
        -- Primary keys
        ORDER_ITEM_ID                           as order_item_id,
        ORDER_ID                                as order_id,
        ORDER_CUSTOMER_ID                       as customer_id,

        -- Order dates (casting from VARCHAR to TIMESTAMP)
        TO_TIMESTAMP(ORDER_DATE, 'MM/DD/YYYY HH24:MI')      as order_date,
        TO_TIMESTAMP(SHIPPING_DATE, 'MM/DD/YYYY HH24:MI')   as shipping_date,

        -- Delivery fields (TARGET VARIABLE)
        LATE_DELIVERY_RISK                      as late_delivery_risk,
        DELIVERY_STATUS                         as delivery_status,
        SHIPPING_MODE                           as shipping_mode,
        DAYS_FOR_SHIPPING_REAL                  as days_for_shipping_real,
        DAYS_FOR_SHIPMENT_SCHEDULED             as days_for_shipment_scheduled,
        DAYS_FOR_SHIPPING_REAL - DAYS_FOR_SHIPMENT_SCHEDULED as days_late,

        -- Order details
        TYPE                                    as payment_type,
        ORDER_STATUS                            as order_status,
        ORDER_ITEM_QUANTITY                     as order_item_quantity,

        -- Financial metrics
        SALES                                   as sales,
        ORDER_ITEM_TOTAL                        as order_item_total,
        ORDER_PROFIT_PER_ORDER                  as order_profit_per_order,
        BENEFIT_PER_ORDER                       as benefit_per_order,
        SALES_PER_CUSTOMER                      as sales_per_customer,
        ORDER_ITEM_DISCOUNT                     as order_item_discount,
        ORDER_ITEM_DISCOUNT_RATE                as order_item_discount_rate,
        ORDER_ITEM_PRODUCT_PRICE                as order_item_product_price,
        ORDER_ITEM_PROFIT_RATIO                 as order_item_profit_ratio,

        -- Product identifiers
        PRODUCT_CARD_ID                         as product_card_id,
        PRODUCT_CATEGORY_ID                     as product_category_id,
        ORDER_ITEM_CARDPROD_ID                  as order_item_cardprod_id,

        -- Geography
        MARKET                                  as market,
        ORDER_REGION                            as order_region,
        ORDER_COUNTRY                           as order_country,
        ORDER_STATE                             as order_state,
        ORDER_CITY                              as order_city,

        -- Customer location
        CUSTOMER_CITY                           as customer_city,
        CUSTOMER_STATE                          as customer_state,
        CUSTOMER_COUNTRY                        as customer_country,
        CUSTOMER_SEGMENT                        as customer_segment,

        -- Department
        DEPARTMENT_ID                           as department_id,
        DEPARTMENT_NAME                         as department_name

    from source

)

select * from renamed