"""Collecte des posts et commentaires Reddit (API officielle, via PRAW) vers SQLite.

Identifiants lus dans les variables d'environnement :
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
    (optionnel) REDDIT_USERNAME, REDDIT_PASSWORD pour une app de type "script"

Exemples :
    python -m reddit.collector --subreddit algobetting --listing top --time-filter year --limit 200
    python -m reddit.collector --subreddit algobetting --search "closing line value"
"""

import argparse
import os
import sqlite3
import sys
import time

import praw

DEFAULT_DB = "data/reddit.sqlite"

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
    fetched_at REAL
);
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT REFERENCES posts(id),
    parent_id TEXT,
    author TEXT,
    body TEXT,
    score INTEGER,
    created_utc REAL,
    fetched_at REAL
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
"""


def make_client():
    missing = [k for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT") if not os.environ.get(k)]
    if missing:
        sys.exit(f"Variables d'environnement manquantes : {', '.join(missing)}")
    kwargs = {
        "client_id": os.environ["REDDIT_CLIENT_ID"],
        "client_secret": os.environ["REDDIT_CLIENT_SECRET"],
        "user_agent": os.environ["REDDIT_USER_AGENT"],
    }
    if os.environ.get("REDDIT_USERNAME") and os.environ.get("REDDIT_PASSWORD"):
        kwargs["username"] = os.environ["REDDIT_USERNAME"]
        kwargs["password"] = os.environ["REDDIT_PASSWORD"]
    reddit = praw.Reddit(**kwargs)
    reddit.read_only = "username" not in kwargs
    return reddit


def open_db(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def save_post(conn, post, now):
    conn.execute(
        "INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            post.id,
            post.subreddit.display_name,
            post.title,
            post.selftext,
            str(post.author) if post.author else None,
            post.score,
            post.num_comments,
            post.created_utc,
            post.url,
            f"https://www.reddit.com{post.permalink}",
            post.link_flair_text,
            now,
        ),
    )


def save_comments(conn, post, now, more_limit):
    post.comments.replace_more(limit=more_limit)
    rows = [
        (
            c.id,
            post.id,
            c.parent_id,
            str(c.author) if c.author else None,
            c.body,
            c.score,
            c.created_utc,
            now,
        )
        for c in post.comments.list()
    ]
    conn.executemany("INSERT OR REPLACE INTO comments VALUES (?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def iter_posts(sub, args):
    if args.search:
        return sub.search(args.search, sort="relevance", time_filter=args.time_filter, limit=args.limit)
    if args.listing == "top":
        return sub.top(time_filter=args.time_filter, limit=args.limit)
    return getattr(sub, args.listing)(limit=args.limit)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subreddit", default="algobetting")
    parser.add_argument("--listing", choices=["hot", "new", "top", "rising"], default="top")
    parser.add_argument("--time-filter", choices=["hour", "day", "week", "month", "year", "all"], default="year")
    parser.add_argument("--search", help="requête de recherche dans le subreddit (remplace --listing)")
    parser.add_argument("--limit", type=int, default=100, help="nombre de posts (max ~1000 par listing côté Reddit)")
    parser.add_argument("--no-comments", action="store_true", help="ne pas récupérer les commentaires")
    parser.add_argument("--more-limit", type=int, default=0, help="nombre de 'load more comments' à déplier par post")
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    reddit = make_client()
    conn = open_db(args.db)
    sub = reddit.subreddit(args.subreddit)

    n_posts = n_comments = 0
    for post in iter_posts(sub, args):
        now = time.time()
        save_post(conn, post, now)
        n_posts += 1
        if not args.no_comments:
            n_comments += save_comments(conn, post, now, args.more_limit)
        conn.commit()
        print(f"[{n_posts}] {post.score:>5}  {post.title[:90]}")

    conn.close()
    print(f"\n{n_posts} posts et {n_comments} commentaires enregistrés dans {args.db}")


if __name__ == "__main__":
    main()
