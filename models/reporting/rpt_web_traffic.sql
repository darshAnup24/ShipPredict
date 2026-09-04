with web_traffic as (

    select * from {{ ref('stg_web_traffic') }}

),

final as (

    select
        -- Time dimensions
        visit_month,
        visit_hour,

        -- Dimensions
        department_name,
        category_name,
        product_name,

        -- Traffic metrics
        count(*)                                            as total_visits,
        count(distinct ip_address)                          as unique_visitors,

        -- Hour buckets
        case
            when visit_hour between 0 and 5   then 'Late Night'
            when visit_hour between 6 and 11  then 'Morning'
            when visit_hour between 12 and 17 then 'Afternoon'
            when visit_hour between 18 and 23 then 'Evening'
        end                                                 as time_of_day

    from web_traffic
    group by
        visit_month,
        visit_hour,
        department_name,
        category_name,
        product_name

)

select * from final