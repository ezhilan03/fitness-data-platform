-- Grain: one user / local Monday-start week / activity type.
-- No calendar fill: unobserved days do not become zero-activity days.
INSERT INTO weekly_summaries
SELECT user_id, week_start, activity, COUNT(*), COUNT(DISTINCT local_date),
       SUM(duration_seconds), SUM(distance_m), COUNT(distance_m), :as_of
FROM current_sessions GROUP BY user_id, week_start, activity
