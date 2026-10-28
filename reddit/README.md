# Collecteur Reddit

Récupère les posts et commentaires d'un subreddit (par défaut r/algobetting) et les stocke dans `data/reddit.sqlite` (tables `posts` et `comments`, colonne `source` = `api`, `arctic_shift` ou `rss`).

Trois sources, utilisables séparément :

| Script | Source | Clé requise | Usage |
|---|---|---|---|
| `reddit/arctic_shift.py` | archive Arctic Shift | non | historique complet (posts + commentaires), scores figés à l'archivage |
| `reddit/rss.py` | flux RSS public de Reddit | non | suivi des nouveaux posts (~1 requête/min/IP, sans score ni commentaires) |
| `reddit/collector.py` | API officielle (PRAW) | oui | données à jour, scores, commentaires — nécessite une approbation de Reddit |

Domaines à autoriser dans la politique réseau de l'environnement : `arctic-shift.photon-reddit.com`, `www.reddit.com` (et `oauth.reddit.com` pour l'API).

Les conditions d'utilisation de Reddit encadrent la collecte automatisée : usage interne, non commercial, à faible volume, sans republier le contenu brut.

## Sans clé : Arctic Shift + RSS

```
python -m reddit.arctic_shift --subreddit algobetting          # 1re fois : tout l'historique ; ensuite : reprend où il s'était arrêté
python -m reddit.arctic_shift --subreddit BettingModels --after 2025-01-01
python -m reddit.rss --subreddit algobetting --subreddit BettingModels --watch 15
```

Le RSS n'écrase jamais un post déjà présent (venant d'Arctic Shift ou de l'API), qui contient plus d'informations.

# API officielle

## 1. Obtenir l'accès à l'API

Depuis fin 2025 (Responsible Builder Policy), on ne peut plus créer d'app soi-même sur reddit.com/prefs/apps : il faut **demander l'accès**.

1. Lire la Responsible Builder Policy et la Data API Terms de Reddit.
2. Remplir la demande d'accès aux données (Data Access Request), accessible depuis la page des apps ou le centre d'aide développeurs de Reddit :
   - rôle : *app non supportée par Devvit* (intégration externe) ;
   - usage : recherche personnelle / non commerciale, lecture seule, volume faible ;
   - une URL publique du projet (par ex. ce dépôt GitHub).
3. Une fois l'accès accordé, créer une app de type **script** et noter le `client_id` (sous le nom de l'app) et le `client_secret`.

## 2. Configurer

Variables d'environnement (à mettre dans les secrets de l'environnement, jamais dans le dépôt) :

```
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=script:value-betting-research:v0.1 (by u/VOTRE_PSEUDO)
# optionnel, pour une app "script" liée à votre compte :
REDDIT_USERNAME=...
REDDIT_PASSWORD=...
```

## 3. Lancer

```
pip install -r requirements.txt
python -m reddit.collector --subreddit algobetting --listing top --time-filter all --limit 500
python -m reddit.collector --subreddit algobetting --search "closing line value" --time-filter all
python -m reddit.collector --subreddit BettingModels --listing new --limit 100
```

Les relances sont idempotentes : les posts et commentaires déjà présents sont mis à jour.
