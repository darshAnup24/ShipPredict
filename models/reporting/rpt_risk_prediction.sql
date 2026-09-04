with orders as (

    select * from {{ ref('fct_orders') }}

),

final as (

    select
        -- Time dimensions
        order_month,
        order_year,

        -- Risk features (most important for ML)
        shipping_mode,
        market,
        order_region,
        customer_segment,
        department_name,
        payment_type,

        -- Order counts
        count(distinct order_id)                            as total_orders,
        count(order_item_id)                                as total_order_items,

        -- Target variable summary
        sum(late_delivery_risk)                             as total_late,
        count(order_item_id) - sum(late_delivery_risk)      as total_not_late,
        round(sum(late_delivery_risk) /
            nullif(count(order_item_id), 0) * 100, 2)      as late_delivery_rate_pct,

        -- Shipping day metrics
        avg(days_for_shipping_real)                         as avg_actual_days,
        avg(days_for_shipment_scheduled)                    as avg_scheduled_days,
        avg(days_late)                                      as avg_days_late,

        -- Delivery performance breakdown
        sum(case when delivery_performance = 'Late'
            then 1 else 0 end)                              as count_late,
        sum(case when delivery_performance = 'On Time'
            then 1 else 0 end)                              as count_on_time,
        sum(case when delivery_performance = 'Early'
            then 1 else 0 end)                              as count_early,

        -- Financial risk
        sum(case when late_delivery_risk = 1
            then benefit_per_order else 0 end)              as benefit_at_risk,
        avg(order_item_discount_rate)                       as avg_discount_rate,
        avg(order_item_profit_ratio)                        as avg_profit_ratio

    from orders
    group by
        order_month,
        order_year,
        shipping_mode,
        market,
        order_region,
        customer_segment,
        department_name,
        payment_type

)

select * from final