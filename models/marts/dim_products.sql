with products as (

    select * from {{ ref('stg_products') }}

),

order_stats as (

    select
        product_card_id,
        count(order_item_id)                as total_orders,
        sum(sales)                          as total_sales,
        sum(order_item_quantity)            as total_units_sold,
        avg(order_item_discount_rate)       as avg_discount_rate,
        avg(order_item_profit_ratio)        as avg_profit_ratio,
        sum(case when late_delivery_risk = 1
            then 1 else 0 end)              as total_late_deliveries,
        count(order_item_id) - sum(case when late_delivery_risk = 1
            then 1 else 0 end)              as total_ontime_deliveries
    from {{ ref('fct_orders') }}
    group by product_card_id

),

final as (

    select
        -- Primary key
        p.product_card_id,

        -- Product details
        p.product_name,
        p.product_price,
        p.product_status,

        -- Category
        p.product_category_id,
        p.category_id,
        p.category_name,

        -- Department
        p.department_id,
        p.department_name,

        -- Order metrics
        o.total_orders,
        o.total_sales,
        o.total_units_sold,
        o.avg_discount_rate,
        o.avg_profit_ratio,
        o.total_late_deliveries,
        o.total_ontime_deliveries,

        -- Derived
        round(o.total_late_deliveries / nullif(o.total_orders, 0) * 100, 2)
                                            as late_delivery_pct,

        case
            when p.product_price >= 500 then 'Premium'
            when p.product_price >= 100 then 'Mid Range'
            else 'Budget'
        end                                 as product_price_tier

    from products p
    left join order_stats o on p.product_card_id = o.product_card_id

)

select * from final