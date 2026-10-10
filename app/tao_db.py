"""Additive, idempotent Tao migration. Existing KKV JSON and tables stay intact."""
from . import db


def initialize():
    with db.connection() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS tao_schema_migrations(
          version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tao_cases(
          id TEXT PRIMARY KEY, data TEXT NOT NULL, version INTEGER NOT NULL,
          status TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL,
          owner_id TEXT NOT NULL REFERENCES users(id),
          client_user_id TEXT REFERENCES users(id), approved_version INTEGER);
        CREATE TABLE IF NOT EXISTS tao_versions(
          case_id TEXT NOT NULL REFERENCES tao_cases(id), version INTEGER NOT NULL,
          data TEXT NOT NULL, calculation TEXT NOT NULL, created TEXT NOT NULL,
          author TEXT NOT NULL REFERENCES users(id), approved_at TEXT,
          approver TEXT REFERENCES users(id), confirmations TEXT,
          PRIMARY KEY(case_id,version));
        CREATE TABLE IF NOT EXISTS tao_documents(
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES tao_cases(id),
          filename TEXT NOT NULL, stored_name TEXT NOT NULL, size INTEGER NOT NULL,
          sha256 TEXT NOT NULL, author TEXT NOT NULL REFERENCES users(id), created TEXT NOT NULL,
          reviewed_at TEXT, reviewer TEXT REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS tao_audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES tao_cases(id),
          actor TEXT NOT NULL REFERENCES users(id), action TEXT NOT NULL,
          details TEXT NOT NULL, created TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS tao_documents_case ON tao_documents(case_id);
        CREATE INDEX IF NOT EXISTS tao_audit_case ON tao_audit(case_id,id);
        ''')
        con.execute('INSERT OR IGNORE INTO tao_schema_migrations VALUES(?,?)', (1, db.now()))


def audit(con, cid, uid, action, details=''):
    con.execute('INSERT INTO tao_audit(case_id,actor,action,details,created) VALUES(?,?,?,?,?)',
                (cid, uid, action, details, db.now()))
