-- This test fails if late_delivery_risk=1 does not match delivery_status='Late delivery'
-- Confirmed from data: risk=1 always maps to 'Late delivery' exactly

select
    order_item_id,
    late_delivery_risk,
    delivery_status
from {{ ref('stg_orders') }}
where late_delivery_risk = 1
  and delivery_status != 'Late delivery'