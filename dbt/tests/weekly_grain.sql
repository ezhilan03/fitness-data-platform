select user_id,week_start,activity from {{ ref('weekly_summaries') }}
group by user_id,week_start,activity having count(*)<>1
