import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def data_dir():
    p = Path(os.environ.get('KKV_DATA_DIR', Path(__file__).resolve().parent.parent / 'data')).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def connection():
    con = sqlite3.connect(data_dir() / 'kkv.sqlite3', timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def initialize():
    with connection() as con:
        con.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(
          id TEXT PRIMARY KEY, name TEXT NOT NULL, username TEXT NOT NULL UNIQUE,
          password TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
          created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(
          token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          csrf TEXT NOT NULL, expires TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cases(
          id TEXT PRIMARY KEY, data TEXT NOT NULL, version INTEGER NOT NULL,
          status TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL,
          owner_id TEXT NOT NULL REFERENCES users(id),
          client_user_id TEXT REFERENCES users(id), approved_version INTEGER);
        CREATE TABLE IF NOT EXISTS versions(
          case_id TEXT NOT NULL REFERENCES cases(id), version INTEGER NOT NULL,
          data TEXT NOT NULL, calculation TEXT NOT NULL, created TEXT NOT NULL,
          author TEXT NOT NULL REFERENCES users(id), approved_at TEXT,
          approver TEXT REFERENCES users(id), confirmations TEXT,
          PRIMARY KEY(case_id,version));
        CREATE TABLE IF NOT EXISTS documents(
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
          filename TEXT NOT NULL, stored_name TEXT NOT NULL, size INTEGER NOT NULL,
          sha256 TEXT NOT NULL, author TEXT NOT NULL REFERENCES users(id), created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT REFERENCES cases(id),
          actor TEXT REFERENCES users(id), action TEXT NOT NULL, details TEXT NOT NULL,
          created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS intake(
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
          author TEXT NOT NULL REFERENCES users(id), message TEXT NOT NULL,
          created TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0);
        ''')


def audit(con, case_id, actor, action, details=''):
    con.execute('INSERT INTO audit(case_id,actor,action,details,created) VALUES(?,?,?,?,?)',
                (case_id, actor, action, details, now()))


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
