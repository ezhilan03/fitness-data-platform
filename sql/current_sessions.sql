-- First choose the latest known revision per source event. A correction is
-- invisible until both source availability and local receipt precede the cutoff.
WITH source_versions AS (
 SELECT *, ROW_NUMBER() OVER (
   PARTITION BY user_id, source, event_id ORDER BY revision DESC
 ) AS revision_rank
 FROM revisions WHERE available_at <= :as_of AND received_at <= :as_of
), canonical_sessions AS (
 SELECT *, ROW_NUMBER() OVER (
   PARTITION BY user_id, session_id
   ORDER BY CASE source WHEN 'manual' THEN 0 WHEN 'watch' THEN 1 ELSE 2 END,
            event_id
 ) AS source_rank
 FROM source_versions WHERE revision_rank = 1
)
SELECT user_id, source, event_id, revision, session_id, activity,
       started_at, ended_at, timezone, local_date, week_start,
       duration_seconds, distance_m
FROM canonical_sessions WHERE source_rank = 1
