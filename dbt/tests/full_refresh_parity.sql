with expected as (
 select user_id,week_start,activity,count(*) as sessions,count(distinct local_date) as observed_days,
 sum(duration_seconds) as duration_seconds,sum(distance_m) as distance_m,count(distance_m) as distance_observed_sessions
 from {{ ref('current_sessions') }} group by user_id,week_start,activity
), missing as (select * from expected except select * from {{ ref('weekly_summaries') }}),
extra as (select * from {{ ref('weekly_summaries') }} except select * from expected)
select * from missing union all select * from extra
