-- This test fails if any order has shipping days outside 0-6
-- Confirmed from data analysis: min=0, max=6

select
    order_item_id,
    days_for_shipping_real
from {{ ref('stg_orders') }}
where days_for_shipping_real < 0
   or days_for_shipping_real > 6