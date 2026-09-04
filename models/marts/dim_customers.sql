with customers as (

    select * from {{ ref('stg_customers') }}

),

orders as (

    select
        customer_id,
        count(distinct order_id)            as total_orders,
        count(order_item_id)                as total_order_items,
        sum(sales)                          as total_sales,
        sum(benefit_per_order)              as total_benefit,
        avg(order_item_profit_ratio)        as avg_profit_ratio,
        sum(case when late_delivery_risk = 1
            then 1 else 0 end)              as total_late_deliveries,
        count(order_item_id) - sum(case when late_delivery_risk = 1
            then 1 else 0 end)              as total_ontime_deliveries,
        min(order_date)                     as first_order_date,
        max(order_date)                     as last_order_date
    from {{ ref('fct_orders') }}
    group by customer_id

),

final as (

    select
        -- Primary key
        c.customer_id,

        -- Customer details
        c.customer_first_name,
        c.customer_last_name,
        c.customer_segment,

        -- Location
        c.customer_city,
        c.customer_state,
        c.customer_country,
        c.customer_zipcode,

        -- Order metrics
        o.total_orders,
        o.total_order_items,
        o.total_sales,
        o.total_benefit,
        o.avg_profit_ratio,
        o.total_late_deliveries,
        o.total_ontime_deliveries,
        o.first_order_date,
        o.last_order_date,

        -- Derived
        round(o.total_late_deliveries / nullif(o.total_order_items, 0) * 100, 2)
                                            as late_delivery_pct,

        case
            when o.total_sales >= 1000 then 'High Value'
            when o.total_sales >= 500  then 'Mid Value'
            else 'Low Value'
        end                                 as customer_value_tier

    from customers c
    left join orders o on c.customer_id = o.customer_id

)

select * from final