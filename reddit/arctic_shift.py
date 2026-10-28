"""Import de l'historique d'un subreddit depuis l'archive Arctic Shift (sans clé d'API).

API : https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md
Pas de garantie de disponibilité ; scores figés au moment de l'archivage.

Exemples :
    python -m reddit.arctic_shift --subreddit algobetting               # tout l'historique (reprend où il s'était arrêté)
    python -m reddit.arctic_shift --subreddit algobetting --after 2025-01-01 --no-comments
"""

import argparse
import calendar
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from reddit.db import DEFAULT_DB, max_created, open_db, save_comments, save_posts

BASE_URL = "https://arctic-shift.photon-reddit.com/api"
USER_AGENT = "value-betting-research/0.1"
POST_FIELDS = "id,subreddit,title,selftext,author,score,num_comments,created_utc,url,link_flair_text"
COMMENT_FIELDS = "id,link_id,parent_id,subreddit,author,body,score,created_utc"
PAGE_SIZE = 100


def get(endpoint, params, retries=4):
    url = f"{BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
            if payload.get("error"):
                raise RuntimeError(f"Arctic Shift : {payload['error']}")
            return payload["data"]
        except urllib.error.HTTPError as e:
            if e.code < 500:  # requête invalide : inutile de réessayer
                raise RuntimeError(f"Arctic Shift HTTP {e.code} : {e.read().decode(errors='replace')[:300]}") from e
            if attempt == retries:
                raise
            wait = 2 ** (attempt + 1)
            print(f"  erreur ({e}), nouvel essai dans {wait}s")
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == retries:
                raise
            wait = 2 ** (attempt + 1)
            print(f"  erreur ({e}), nouvel essai dans {wait}s")
            time.sleep(wait)


def paginate(endpoint, params, after):
    """Parcourt les résultats par ordre chronologique, page par page, à partir de `after` (epoch)."""
    cursor = after
    while True:
        query = {**params, "sort": "asc", "limit": PAGE_SIZE}
        if cursor:  # l'API refuse les epochs trop petits (ex. 0) : sans `after`, on part du début
            query["after"] = int(cursor)
        page = get(endpoint, query)
        if not page:
            return
        yield page
        if len(page) < PAGE_SIZE:
            return
        last = int(max(item["created_utc"] for item in page))
        # Plusieurs éléments peuvent partager la même seconde que la fin de page : on repart une seconde
        # avant pour ne pas les perdre (les doublons sont absorbés par l'insertion idempotente). Si cela ne
        # fait pas avancer le curseur (page entière dans la même seconde), on avance quand même.
        cursor = last - 1 if last - 1 > cursor else max(last, cursor + 1)
        time.sleep(0.5)


def strip_prefix(fullname):
    return fullname.split("_", 1)[1] if fullname and "_" in fullname else fullname


def post_row(p, now):
    return {
        "id": p["id"],
        "subreddit": p.get("subreddit"),
        "title": p.get("title"),
        "selftext": p.get("selftext"),
        "author": p.get("author"),
        "score": p.get("score"),
        "num_comments": p.get("num_comments"),
        "created_utc": p.get("created_utc"),
        "url": p.get("url"),
        "permalink": f"https://www.reddit.com/r/{p.get('subreddit')}/comments/{p['id']}/",
        "flair": p.get("link_flair_text"),
        "source": "arctic_shift",
        "fetched_at": now,
    }


def comment_row(c, now):
    return {
        "id": c["id"],
        "post_id": strip_prefix(c.get("link_id")),
        "parent_id": c.get("parent_id"),
        "subreddit": c.get("subreddit"),
        "author": c.get("author"),
        "body": c.get("body"),
        "score": c.get("score"),
        "created_utc": c.get("created_utc"),
        "source": "arctic_shift",
        "fetched_at": now,
    }


def import_kind(conn, kind, subreddit, after):
    endpoint, fields, to_row, save = {
        "posts": ("posts/search", POST_FIELDS, post_row, save_posts),
        "comments": ("comments/search", COMMENT_FIELDS, comment_row, save_comments),
    }[kind]
    total = 0
    for page in paginate(endpoint, {"subreddit": subreddit, "fields": fields}, after):
        now = time.time()
        save(conn, [to_row(item, now) for item in page])
        conn.commit()
        total += len(page)
        last = time.strftime("%Y-%m-%d", time.gmtime(max(i["created_utc"] for i in page)))
        print(f"  {kind} : {total} reçus (jusqu'au {last})")
    return total


def parse_date(value):
    return calendar.timegm(time.strptime(value, "%Y-%m-%d")) if value else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subreddit", default="algobetting")
    parser.add_argument("--after", help="date de début AAAA-MM-JJ (par défaut : reprise après le dernier élément stocké)")
    parser.add_argument("--no-comments", action="store_true")
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    conn = open_db(args.db)
    kinds = ["posts"] if args.no_comments else ["posts", "comments"]
    for kind in kinds:
        after = parse_date(args.after) or max_created(conn, kind, args.subreddit, "arctic_shift") or 0
        print(f"r/{args.subreddit} — {kind} depuis {time.strftime('%Y-%m-%d', time.gmtime(after))}")
        import_kind(conn, kind, args.subreddit, after)
    conn.close()


if __name__ == "__main__":
    main()
