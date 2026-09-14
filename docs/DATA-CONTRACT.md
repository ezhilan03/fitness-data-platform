# v1 workout contract

One JSON object per line. All fields are required; unknown fields are rejected. Schema validation precedes the transaction; any identity conflict during insertion rolls back the entire batch.

| Field | Meaning |
|---|---|
| user_id | Synthetic, case-sensitive subject identifier |
| source | manual, watch or phone |
| event_id | Stable identity within subject and source |
| revision | Positive integer from the source; higher values supersede lower ones |
| session_id | Explicit canonical workout ID shared only by known representations of the same workout |
| activity | run, walk or strength |
| started_at / ended_at | Offset-aware ISO timestamps, whole seconds; offset must agree with declared timezone |
| timezone | IANA zone used for local day/week assignment |
| available_at | When this complete revision became available at source; cannot precede workout end or exceed receipt time |
| distance / distance_unit | Finite nonnegative value with m, km or mi; both null if not observed |

The local ingestion layer assigns received_at and stores a canonical payload hash plus normalized fields. Revision identity is `(user_id, source, event_id, revision)`. Reuse with a different payload fails. Event identity cannot migrate to a different canonical session. A source cannot assign multiple event IDs to the same canonical session.

The current-session grain is `(user_id, session_id)` at a specified knowledge cutoff. The weekly grain is `(user_id, local Monday week_start, activity)`. Duration is elapsed UTC seconds, greater than zero and no more than 24 hours under this demo contract. Distance is at most 1,000,000 metres under the input contract; this is a technical bound, not health guidance.

The weekly distance sum includes observed distances only; `distance_observed_sessions` identifies coverage. If every distance is missing, the sum remains null. `observed_days` is not adherence, completion, or a claim of complete device coverage.

Corrections remain source-authoritative by revision number, even when received out of order. Invalid source revision histories must be addressed upstream; this demo cannot infer the truth from conflicting devices.
