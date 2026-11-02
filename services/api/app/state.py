from contextlib import contextmanager
from datetime import datetime,timezone
import sqlite3,json
from .config import ROOT,STATE

def now():return datetime.now(timezone.utc).isoformat()
def initialize():
    STATE.mkdir(parents=True,exist_ok=True)
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript((ROOT/'contracts/state.sqlite.sql').read_text(encoding='utf-8'))
        db.executescript('''
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scope_owners (scope_id TEXT REFERENCES scopes(scope_id),owner TEXT,PRIMARY KEY(scope_id,owner));
        CREATE TABLE IF NOT EXISTS cohort_owners (cohort_id TEXT REFERENCES cohorts(cohort_id),owner TEXT,PRIMARY KEY(cohort_id,owner));
        CREATE TABLE IF NOT EXISTS review_owners (review_id TEXT REFERENCES review_items(id) ON DELETE CASCADE,owner TEXT,PRIMARY KEY(review_id,owner));
        CREATE TABLE IF NOT EXISTS job_owners (job_id TEXT REFERENCES jobs(job_id),owner TEXT,PRIMARY KEY(job_id,owner));
        CREATE TABLE IF NOT EXISTS snapshot_owners (snapshot_id TEXT REFERENCES snapshots(snapshot_id),owner TEXT,PRIMARY KEY(snapshot_id,owner));
        CREATE TABLE IF NOT EXISTS import_keys (fingerprint TEXT PRIMARY KEY,snapshot_id TEXT REFERENCES snapshots(snapshot_id));
        CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL);
        ''')
        db.execute('INSERT OR IGNORE INTO schema_migrations VALUES (1,?)',(now(),))

@contextmanager
def connection():
    STATE.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(STATE/'state.sqlite',timeout=10)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback();raise
    finally:db.close()

def job_update(job,state,progress=None,error=None):
    with connection() as db:
        # Progress writers may already be in flight when the HTTP cancel commits.
        # Terminal states must remain terminal in that same atomic UPDATE.
        db.execute("UPDATE jobs SET state=?,progress_json=?,error_code=?,finished_at=? WHERE job_id=? AND state IN ('queued','running')",(state,json.dumps(progress or {},ensure_ascii=False),error,now() if state in ('succeeded','failed','cancelled') else None,job))

def job_cancelled(job):
    with connection() as db:
        row=db.execute('SELECT state FROM jobs WHERE job_id=?',(job,)).fetchone()
    return row is None or row['state']=='cancelled'
