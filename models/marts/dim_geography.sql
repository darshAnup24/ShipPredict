with orders as (

    select * from {{ ref('fct_orders') }}

),

geography as (

    select distinct
        -- Keys
        order_region,
        order_country,
        order_state,
        order_city,
        market

    from orders

),

order_stats as (

    select
        order_region,
        count(distinct order_id)            as total_orders,
        count(order_item_id)                as total_order_items,
        sum(sales)                          as total_sales,
        sum(benefit_per_order)              as total_benefit,
        sum(case when late_delivery_risk = 1
            then 1 else 0 end)              as total_late_deliveries,
        count(order_item_id) - sum(case when late_delivery_risk = 1
            then 1 else 0 end)              as total_ontime_deliveries,
        avg(days_late)                      as avg_days_late
    from orders
    group by order_region

),

final as (

    select
        -- Geography hierarchy
        g.market,
        g.order_region,
        g.order_country,
        g.order_state,
        g.order_city,

        -- Order metrics
        o.total_orders,
        o.total_order_items,
        o.total_sales,
        o.total_benefit,
        o.total_late_deliveries,
        o.total_ontime_deliveries,
        o.avg_days_late,

        -- Derived
        round(o.total_late_deliveries / nullif(o.total_order_items, 0) * 100, 2)
                                            as late_delivery_pct

    from geography g
    left join order_stats o on g.order_region = o.order_region

)

select * from final