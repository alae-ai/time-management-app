-- Multi-user upgrade: users, sessions, API tokens, and per-user data ownership.
--
-- Existing rows are assigned to an inactive ``legacy-user``. The first admin created
-- through /api/auth/setup claims those rows, so upgrading an existing single-user
-- database does not lose any tasks or blocks.

PRAGMA foreign_keys = OFF;
BEGIN;

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  email         TEXT NOT NULL COLLATE NOCASE UNIQUE,
  name          TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  is_admin      INTEGER NOT NULL DEFAULT 0,
  is_active     INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  last_login_at TEXT
);

INSERT OR IGNORE INTO users
  (id, email, name, password_hash, is_admin, is_active, created_at, updated_at)
VALUES
  ('legacy-user', 'legacy@local.invalid', 'Legacy data', '!', 0, 0,
   strftime('%Y-%m-%dT%H:%M:%S', 'now'), strftime('%Y-%m-%dT%H:%M:%S', 'now'));

CREATE TABLE IF NOT EXISTS sessions (
  id           TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash   TEXT NOT NULL UNIQUE,
  created_at   TEXT NOT NULL,
  expires_at   TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  user_agent   TEXT,
  ip           TEXT
);

CREATE TABLE IF NOT EXISTS api_tokens (
  id           TEXT PRIMARY KEY,
  user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  token_hash   TEXT NOT NULL UNIQUE,
  created_at   TEXT NOT NULL,
  last_used_at TEXT,
  expires_at   TEXT
);

CREATE TABLE tasks_new (
  id            TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  project       TEXT,
  notes         TEXT NOT NULL DEFAULT '',
  deadline_date TEXT,
  deadline_min  INTEGER,
  done          INTEGER NOT NULL DEFAULT 0,
  done_at       TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  CHECK (deadline_date IS NULL OR deadline_date GLOB
         '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  CHECK (deadline_min IS NULL OR deadline_min BETWEEN 0 AND 1439)
);

INSERT INTO tasks_new
  (id, user_id, title, project, notes, deadline_date, deadline_min, done,
   done_at, created_at, updated_at)
SELECT
  id, 'legacy-user', title, project, notes, deadline_date, deadline_min, done,
  done_at, created_at, updated_at
FROM tasks;

DROP TABLE tasks;
ALTER TABLE tasks_new RENAME TO tasks;

CREATE TABLE blocks_new (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title      TEXT NOT NULL,
  kind       TEXT NOT NULL CHECK (kind IN ('appointment', 'session')),
  task_id    TEXT REFERENCES tasks(id) ON DELETE CASCADE,
  date       TEXT NOT NULL,
  start_min  INTEGER,
  end_min    INTEGER,
  notes      TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK ((start_min IS NULL AND end_min IS NULL) OR
         (start_min BETWEEN 0 AND 1439 AND end_min BETWEEN 1 AND 1440
          AND end_min > start_min)),
  CHECK (kind = 'session' OR task_id IS NULL)
);

INSERT INTO blocks_new
  (id, user_id, title, kind, task_id, date, start_min, end_min, notes,
   created_at, updated_at)
SELECT
  id, 'legacy-user', title, kind, task_id, date, start_min, end_min, notes,
  created_at, updated_at
FROM blocks;

DROP TABLE blocks;
ALTER TABLE blocks_new RENAME TO blocks;

CREATE TABLE app_settings_new (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key     TEXT NOT NULL,
  value   TEXT NOT NULL,
  PRIMARY KEY (user_id, key)
);

INSERT INTO app_settings_new (user_id, key, value)
SELECT 'legacy-user', key, value FROM app_settings;

DROP TABLE app_settings;
ALTER TABLE app_settings_new RENAME TO app_settings;

CREATE TABLE conversations_new (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title      TEXT NOT NULL DEFAULT 'New chat',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

INSERT INTO conversations_new (id, user_id, title, created_at, updated_at)
SELECT id, 'legacy-user', title, created_at, updated_at FROM conversations;

DROP TABLE conversations;
ALTER TABLE conversations_new RENAME TO conversations;

CREATE INDEX IF NOT EXISTS idx_tasks_user_deadline ON tasks(user_id, deadline_date);
CREATE INDEX IF NOT EXISTS idx_blocks_user_date ON blocks(user_id, date);
CREATE INDEX IF NOT EXISTS idx_blocks_user_task ON blocks(user_id, task_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);

COMMIT;
PRAGMA foreign_keys = ON;
