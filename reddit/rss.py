"""Suivi des nouveaux posts d'un subreddit via le flux RSS public de Reddit (sans compte).

Le flux est limité à environ 1 requête par minute et par IP, et ne contient ni score ni commentaires.
Les posts déjà présents en base (venant de l'API ou d'Arctic Shift) ne sont pas écrasés.

Exemples :
    python -m reddit.rss --subreddit algobetting
    python -m reddit.rss --subreddit algobetting --subreddit BettingModels --watch 15   # toutes les 15 min
"""

import argparse
import calendar
import html
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from reddit.db import DEFAULT_DB, open_db, save_posts

FEED_URL = "https://www.reddit.com/r/{subreddit}/new/.rss?limit=100"
USER_AGENT = "value-betting-research/0.1"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
MIN_INTERVAL = 65  # secondes entre deux requêtes, pour rester sous la limite du flux


def fetch_feed(subreddit):
    req = urllib.request.Request(FEED_URL.format(subreddit=subreddit), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return ET.fromstring(resp.read())


def html_to_text(content):
    text = re.sub(r"<br\s*/?>|</p>", "\n", content or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    # Le contenu RSS se termine par « submitted by /u/x [link] [comments] » : on le retire.
    text = re.sub(r"\s*submitted by\s+/u/\S+.*$", "", text, flags=re.S)
    return text.strip()


def parse_time(value):
    # Format Atom : 2026-10-28T08:45:12+00:00
    return calendar.timegm(time.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")) if value else None


def entry_row(entry, subreddit, now):
    fullname = entry.findtext("a:id", namespaces=ATOM) or ""
    author = entry.findtext("a:author/a:name", namespaces=ATOM) or ""
    link = entry.find("a:link", ATOM)
    permalink = link.get("href") if link is not None else None
    return {
        "id": fullname.removeprefix("t3_"),
        "subreddit": subreddit,
        "title": entry.findtext("a:title", namespaces=ATOM),
        "selftext": html_to_text(entry.findtext("a:content", namespaces=ATOM)),
        "author": author.removeprefix("/u/") or None,
        "created_utc": parse_time(entry.findtext("a:published", namespaces=ATOM)
                                  or entry.findtext("a:updated", namespaces=ATOM)),
        "url": permalink,
        "permalink": permalink,
        "source": "rss",
        "fetched_at": now,
    }


def poll(conn, subreddit):
    feed = fetch_feed(subreddit)
    now = time.time()
    rows = [entry_row(e, subreddit, now) for e in feed.findall("a:entry", ATOM)]
    rows = [r for r in rows if r["id"]]
    before = conn.total_changes
    save_posts(conn, rows, replace=False)
    conn.commit()
    return len(rows), conn.total_changes - before


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subreddit", action="append", help="répétable (défaut : algobetting)")
    parser.add_argument("--watch", type=float, metavar="MINUTES", help="relancer en boucle toutes les N minutes")
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    subreddits = args.subreddit or ["algobetting"]

    conn = open_db(args.db)
    while True:
        for i, sub in enumerate(subreddits):
            if i:
                time.sleep(MIN_INTERVAL)
            try:
                seen, new = poll(conn, sub)
                print(f"{time.strftime('%H:%M:%S')} r/{sub} : {seen} posts dans le flux, {new} nouveaux")
            except urllib.error.HTTPError as e:
                print(f"{time.strftime('%H:%M:%S')} r/{sub} : HTTP {e.code} (limite atteinte ?), on réessaiera")
        if not args.watch:
            break
        time.sleep(max(args.watch * 60, MIN_INTERVAL))
    conn.close()


if __name__ == "__main__":
    main()
