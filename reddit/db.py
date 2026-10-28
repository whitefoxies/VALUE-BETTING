"""Base SQLite partagée par les différents collecteurs Reddit."""

import os
import sqlite3

DEFAULT_DB = "data/reddit.sqlite"

POST_COLUMNS = (
    "id", "subreddit", "title", "selftext", "author", "score", "num_comments",
    "created_utc", "url", "permalink", "flair", "source", "fetched_at",
)
COMMENT_COLUMNS = (
    "id", "post_id", "parent_id", "subreddit", "author", "body", "score", "created_utc", "source", "fetched_at",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    subreddit TEXT,
    title TEXT,
    selftext TEXT,
    author TEXT,
    score INTEGER,
    num_comments INTEGER,
    created_utc REAL,
    url TEXT,
    permalink TEXT,
    flair TEXT,
    source TEXT,      -- 'api', 'arctic_shift' ou 'rss'
    fetched_at REAL
);
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT REFERENCES posts(id),
    parent_id TEXT,
    subreddit TEXT,
    author TEXT,
    body TEXT,
    score INTEGER,
    created_utc REAL,
    source TEXT,
    fetched_at REAL
);
CREATE INDEX IF NOT EXISTS idx_posts_sub_created ON posts(subreddit, created_utc);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
"""


def open_db(path=DEFAULT_DB):
    if path != ":memory:":
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def _insert(conn, table, columns, rows, replace):
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    sql = f"{verb} INTO {table} ({','.join(columns)}) VALUES ({','.join('?' * len(columns))})"
    conn.executemany(sql, [tuple(r.get(c) for c in columns) for r in rows])


def save_posts(conn, rows, replace=True):
    """rows : liste de dicts indexés par POST_COLUMNS.

    replace=False garde les lignes déjà présentes (utile pour le RSS, plus pauvre que les autres sources).
    """
    _insert(conn, "posts", POST_COLUMNS, rows, replace)


def save_comments(conn, rows, replace=True):
    _insert(conn, "comments", COMMENT_COLUMNS, rows, replace)


def max_created(conn, table, subreddit, source):
    """Date de l'élément le plus récent déjà stocké depuis cette source (pour reprendre une collecte)."""
    assert table in ("posts", "comments")
    sql = f"SELECT MAX(created_utc) FROM {table} WHERE subreddit = ? COLLATE NOCASE AND source = ?"
    return conn.execute(sql, (subreddit, source)).fetchone()[0]
