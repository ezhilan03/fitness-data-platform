select user_id,session_id from {{ ref('current_sessions') }}
group by user_id,session_id having count(*)<>1
