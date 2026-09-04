with orders as (

    select * from {{ ref('fct_orders') }}

),

final as (

    select
        -- Time dimensions
        order_month,
        order_year,

        -- Shipping mode
        shipping_mode,

        -- Market and region
        market,
        order_region,

        -- Customer segment
        customer_segment,

        -- Department
        department_name,

        -- KPIs
        count(distinct order_id)                            as total_orders,
        count(order_item_id)                                as total_order_items,

        -- Delivery performance counts
        sum(late_delivery_risk)                             as total_late,
        count(order_item_id) - sum(late_delivery_risk)      as total_not_late,

        -- Late delivery rate
        round(sum(late_delivery_risk) /
            nullif(count(order_item_id), 0) * 100, 2)      as late_delivery_rate_pct,

        -- Shipping days metrics
        avg(days_for_shipping_real)                         as avg_actual_shipping_days,
        avg(days_for_shipment_scheduled)                    as avg_scheduled_shipping_days,
        avg(days_late)                                      as avg_days_late,

        -- Financial metrics
        sum(sales)                                          as total_sales,
        sum(benefit_per_order)                              as total_benefit,
        avg(order_item_profit_ratio)                        as avg_profit_ratio,

        -- Delivery performance breakdown
        sum(case when delivery_performance = 'Late'
            then 1 else 0 end)                              as count_late,
        sum(case when delivery_performance = 'On Time'
            then 1 else 0 end)                              as count_on_time,
        sum(case when delivery_performance = 'Early'
            then 1 else 0 end)                              as count_early

    from orders
    group by
        order_month,
        order_year,
        shipping_mode,
        market,
        order_region,
        customer_segment,
        department_name

)

select * from final