{{ config(materialized='incremental', incremental_strategy='delete+insert',
          unique_key=['user_id','week_start','activity'],
          post_hook='delete from {{ this }} where sessions = 0') }}
-- Aggregate the current-session baseline, then only write changed groups.
-- Source reads are still full scans; no scan reduction or scale claim is made.
with aggregated as (
 select user_id,week_start,activity,count(*) as sessions,
        count(distinct local_date) as observed_days,
        sum(duration_seconds) as duration_seconds,
        sum(distance_m) as distance_m,
        count(distance_m) as distance_observed_sessions
 from {{ ref('current_sessions') }} group by user_id,week_start,activity
)
{% if is_incremental() %}
, changed as (
 select * from aggregated except select * from {{ this }}
), removed as (
 -- Tombstones include obsolete keys so delete+insert removes old week groups.
 -- They are deleted by the post-hook in the incremental materialization.
 select old.user_id,old.week_start,old.activity,0 as sessions,0 as observed_days,
        0 as duration_seconds,cast(null as double) as distance_m,0 as distance_observed_sessions
 from {{ this }} old where not exists (
  select 1 from aggregated a where a.user_id=old.user_id
   and a.week_start=old.week_start and a.activity=old.activity
 )
)
select * from changed union all select * from removed
{% else %}
select * from aggregated
{% endif %}
