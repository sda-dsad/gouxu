PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS snapshots (
 snapshot_id TEXT PRIMARY KEY, data_mode TEXT NOT NULL CHECK(data_mode IN ('synthetic','public_real_subset','authorized_private')),
 revision TEXT, manifest_json TEXT NOT NULL, quality_state TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scopes (
 scope_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
 metric_version TEXT NOT NULL, filter_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cohorts (
 cohort_id TEXT PRIMARY KEY, scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
 name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS scope_immutable BEFORE UPDATE ON scopes BEGIN
 SELECT RAISE(ABORT,'scope is immutable; create a new scope'); END;
CREATE TABLE IF NOT EXISTS review_items (
 id TEXT PRIMARY KEY, scope_id TEXT NOT NULL REFERENCES scopes(scope_id), target_type TEXT NOT NULL CHECK(target_type IN ('query','item','compare')),
 target_id TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL CHECK(status IN ('pending','reviewed')),
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
 job_id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('queued','running','succeeded','failed','cancelled')),
 parameters_json TEXT NOT NULL, progress_json TEXT, error_code TEXT, created_at TEXT NOT NULL, finished_at TEXT
);
