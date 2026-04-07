"""Storage schema."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL UNIQUE,
  run_type TEXT NOT NULL,
  risk_flag TEXT,
  spx_regime_score REAL,
  sector_opportunity_score REAL,
  cyclical_opportunity_score REAL,
  payload_path TEXT
);

CREATE TABLE IF NOT EXISTS agent_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  agent_name TEXT NOT NULL,
  score_name TEXT NOT NULL,
  score_value REAL,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS rankings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  ranking_type TEXT NOT NULL,
  item TEXT NOT NULL,
  score REAL,
  label TEXT,
  rank_order INTEGER,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  level TEXT,
  category TEXT,
  item TEXT,
  message TEXT,
  score REAL,
  state_hash TEXT,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS baskets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  basket_name TEXT NOT NULL,
  weighting TEXT,
  item TEXT NOT NULL,
  weight REAL,
  rationale TEXT,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS transitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  item TEXT NOT NULL,
  transition_type TEXT NOT NULL,
  previous_value TEXT,
  current_value TEXT,
  summary TEXT,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);
"""
