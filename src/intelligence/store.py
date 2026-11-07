"""Independent, local SQLite snapshot contract; shared via read-only consumers."""
from pathlib import Path
from contextlib import contextmanager
import json
import sqlite3
from datetime import datetime, timezone

def canonical_time(value):
    value=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if value.tzinfo is None:
        raise ValueError('Timestamp timezone required')
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')

class Store:
    def __init__(self, root: Path):
        self.path = Path(root) / "data/db/intelligence_v1.sqlite"

    @contextmanager
    def reader(self):
        conn=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=15)
        conn.row_factory=sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS snapshots (
                  id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, retrieved_at TEXT NOT NULL,
                  source TEXT NOT NULL, source_url TEXT NOT NULL, kind TEXT NOT NULL,
                  sha256 TEXT NOT NULL, payload TEXT NOT NULL,
                  UNIQUE(symbol, retrieved_at, sha256));
                CREATE TABLE IF NOT EXISTS metric_history (
                  run_at TEXT NOT NULL, symbol TEXT NOT NULL, payload TEXT NOT NULL,
                  PRIMARY KEY(run_at, symbol));
                CREATE TABLE IF NOT EXISTS runs (
                  run_at TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS preferences (
                  key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            ''')
            yield conn
            conn.commit()
        finally:
            conn.close()

    def put_snapshot(self, symbol, retrieved_at, source, source_url, kind, sha256, payload):
        retrieved_at=canonical_time(retrieved_at)
        with self.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO snapshots(symbol,retrieved_at,source,source_url,kind,sha256,payload) VALUES(?,?,?,?,?,?,?)",
                         (symbol, retrieved_at, source, source_url, kind, sha256, payload))

    def latest_snapshots(self, as_of=None):
        if not self.path.exists():
            return {}
        as_of=canonical_time(as_of) if as_of else None
        with self.reader() as conn:
            rows = conn.execute("SELECT * FROM snapshots WHERE (? IS NULL OR retrieved_at<=?) ORDER BY retrieved_at,id", (as_of, as_of)).fetchall()
        return {r["symbol"]: dict(r) for r in rows}

    def save_run(self, run_at, summary, metrics):
        run_at=canonical_time(run_at)
        with self.connection() as conn:
            conn.execute("INSERT OR REPLACE INTO runs VALUES(?,?)", (run_at, json.dumps(summary, allow_nan=False)))
            for row in metrics:
                conn.execute("INSERT OR REPLACE INTO metric_history VALUES(?,?,?)", (run_at, row["symbol"], json.dumps(row, allow_nan=False)))

    def latest_run(self, as_of=None):
        if not self.path.exists():
            return None
        as_of=canonical_time(as_of) if as_of else None
        with self.reader() as conn:
            row = conn.execute("SELECT run_at,payload FROM runs WHERE (? IS NULL OR run_at<=?) ORDER BY run_at DESC LIMIT 1", (as_of,as_of)).fetchone()
        return {"run_at": row["run_at"], **json.loads(row["payload"])} if row else None

    def previous_metrics(self, before):
        if not self.path.exists():
            return {}
        before=canonical_time(before)
        with self.reader() as conn:
            rows = conn.execute("SELECT payload FROM metric_history WHERE run_at=(SELECT MAX(run_at) FROM metric_history WHERE run_at<?)", (before,)).fetchall()
        return {r["symbol"]: r for r in (json.loads(row[0]) for row in rows)}

    def get_shortlist(self):
        if not self.path.exists():
            return []
        with self.reader() as conn:
            row = conn.execute("SELECT payload FROM preferences WHERE key='shortlist'").fetchone()
        return json.loads(row[0]) if row else []

    def set_shortlist(self, symbols):
        from .universe import load_universe
        symbols = list(dict.fromkeys(symbols))
        if len(symbols) > 10:
            raise ValueError("Shortlist: massimo 10 strumenti")
        allowed = set(load_universe(self.path.parents[2]).symbol)
        if not set(symbols) <= allowed:
            raise ValueError("Strumento fuori dal research universe")
        with self.connection() as conn:
            conn.execute("INSERT OR REPLACE INTO preferences VALUES('shortlist',?)", (json.dumps(symbols),))

    def save_rankings(self, run_at, horizon, records):
        from .opportunities import MODEL_VERSION
        with self.connection() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS opportunity_history (
                run_at TEXT NOT NULL,horizon TEXT NOT NULL,model_version TEXT NOT NULL,
                symbol TEXT NOT NULL,payload TEXT NOT NULL,
                PRIMARY KEY(run_at,horizon,model_version,symbol))''')
            conn.executemany('INSERT OR REPLACE INTO opportunity_history VALUES(?,?,?,?,?)',
                [(canonical_time(run_at),horizon,MODEL_VERSION,r['symbol'],json.dumps(r,allow_nan=False)) for r in records])

    def previous_rankings(self, before, horizon):
        from .opportunities import MODEL_VERSION
        if not self.path.exists():return {}
        with self.reader() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='opportunity_history'").fetchone():return {}
            rows=conn.execute('''SELECT payload FROM opportunity_history WHERE horizon=? AND model_version=?
                AND run_at=(SELECT MAX(run_at) FROM opportunity_history WHERE run_at<? AND horizon=? AND model_version=?)''',
                (horizon,MODEL_VERSION,canonical_time(before),horizon,MODEL_VERSION)).fetchall()
        return {r['symbol']:r for r in (json.loads(row[0]) for row in rows)}
