PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS revisions (
 user_id TEXT NOT NULL, source TEXT NOT NULL, event_id TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision > 0), session_id TEXT NOT NULL,
 activity TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT NOT NULL,
 timezone TEXT NOT NULL, local_date TEXT NOT NULL, week_start TEXT NOT NULL,
 duration_seconds INTEGER NOT NULL CHECK(duration_seconds > 0),
 distance_m REAL CHECK(distance_m IS NULL OR distance_m >= 0),
 available_at TEXT NOT NULL, received_at TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL,
 PRIMARY KEY(user_id, source, event_id, revision)
);
CREATE INDEX IF NOT EXISTS revisions_knowledge ON revisions(received_at, available_at);
CREATE TABLE IF NOT EXISTS erased_users (user_hash TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS weekly_summaries (
 user_id TEXT NOT NULL, week_start TEXT NOT NULL, activity TEXT NOT NULL,
 sessions INTEGER NOT NULL, observed_days INTEGER NOT NULL,
 duration_seconds INTEGER NOT NULL, distance_m REAL,
 distance_observed_sessions INTEGER NOT NULL, as_of TEXT NOT NULL,
 PRIMARY KEY(user_id,week_start,activity)
);
