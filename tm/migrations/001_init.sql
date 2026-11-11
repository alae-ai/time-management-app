CREATE TABLE IF NOT EXISTS tasks (
  id            TEXT PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS blocks (
  id         TEXT PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS app_settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
  id         TEXT PRIMARY KEY,
  title      TEXT NOT NULL DEFAULT 'New chat',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  id              TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
  content         TEXT NOT NULL DEFAULT '',
  meta_json       TEXT,
  created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_blocks_date ON blocks(date);
CREATE INDEX IF NOT EXISTS idx_blocks_task ON blocks(task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline_date);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
