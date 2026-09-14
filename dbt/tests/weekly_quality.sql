select * from {{ ref('weekly_summaries') }}
where sessions<=0 or duration_seconds<=0 or observed_days<1 or observed_days>7
or distance_observed_sessions<0 or distance_observed_sessions>sessions
or (distance_observed_sessions=0 and distance_m is not null)
or (distance_observed_sessions>0 and (distance_m is null or distance_m<0))
