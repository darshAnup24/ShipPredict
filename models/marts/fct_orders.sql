with orders as (

    select * from {{ ref('stg_orders') }}

),

final as (

    select
        -- Primary keys
        order_item_id,
        order_id,
        customer_id,
        product_card_id,

        -- Dates
        order_date,
        shipping_date,
        DATE_TRUNC('month', order_date)     as order_month,
        DATE_TRUNC('year', order_date)      as order_year,
        DAYOFWEEK(order_date)               as order_day_of_week,

        -- Target variable
        late_delivery_risk,
        delivery_status,
        shipping_mode,

        -- Delivery metrics
        days_for_shipping_real,
        days_for_shipment_scheduled,
        days_late,

        -- Risk flag derived
        case
            when days_late > 0 then 'Late'
            when days_late = 0 then 'On Time'
            when days_late < 0 then 'Early'
        end                                 as delivery_performance,

        -- Order details
        payment_type,
        order_status,
        order_item_quantity,

        -- Financial metrics
        sales,
        order_item_total,
        order_profit_per_order,
        benefit_per_order,
        sales_per_customer,
        order_item_discount,
        order_item_discount_rate,
        order_item_product_price,
        order_item_profit_ratio,

        -- Profitability flag
        case
            when benefit_per_order < 0 then 'Loss'
            when benefit_per_order = 0 then 'Break Even'
            else 'Profit'
        end                                 as order_profitability,

        -- Geography
        market,
        order_region,
        order_country,
        order_state,
        order_city,

        -- Customer
        customer_segment,
        customer_city,
        customer_state,
        customer_country,

        -- Department
        department_id,
        department_name

    from orders

)

select * from final