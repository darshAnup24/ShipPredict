with orders as (

    select * from {{ ref('fct_orders') }}

),

final as (

    select
        -- Time dimensions
        order_month,
        order_year,

        -- Dimensions
        market,
        order_region,
        customer_segment,
        department_name,
        shipping_mode,
        payment_type,

        -- Order counts
        count(distinct order_id)                            as total_orders,
        count(order_item_id)                                as total_order_items,

        -- Revenue metrics
        sum(sales)                                          as total_sales,
        avg(sales)                                          as avg_sales_per_item,
        sum(order_item_total)                               as total_order_value,
        sum(benefit_per_order)                              as total_benefit,
        sum(order_profit_per_order)                         as total_profit,

        -- Profitability
        avg(order_item_profit_ratio)                        as avg_profit_ratio,
        sum(order_item_discount)                            as total_discount_given,
        avg(order_item_discount_rate)                       as avg_discount_rate,

        -- Loss orders
        sum(case when order_profitability = 'Loss'
            then 1 else 0 end)                              as total_loss_orders,
        sum(case when order_profitability = 'Profit'
            then 1 else 0 end)                              as total_profit_orders,

        -- Units sold
        sum(order_item_quantity)                            as total_units_sold,
        avg(order_item_quantity)                            as avg_units_per_order,

        -- Late delivery impact on revenue
        sum(case when late_delivery_risk = 1
            then sales else 0 end)                          as sales_at_risk,
        sum(case when late_delivery_risk = 0
            then sales else 0 end)                          as sales_on_time

    from orders
    group by
        order_month,
        order_year,
        market,
        order_region,
        customer_segment,
        department_name,
        shipping_mode,
        payment_type

)

select * from final