# Collecteur Reddit

Récupère les posts et commentaires d'un subreddit (par défaut r/algobetting) via l'API officielle de Reddit, et les stocke dans `data/reddit.sqlite`.

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

Réseau : autoriser `www.reddit.com` et `oauth.reddit.com` dans la politique réseau de l'environnement.

## 3. Lancer

```
pip install -r requirements.txt
python -m reddit.collector --subreddit algobetting --listing top --time-filter all --limit 500
python -m reddit.collector --subreddit algobetting --search "closing line value" --time-filter all
python -m reddit.collector --subreddit BettingModels --listing new --limit 100
```

Les relances sont idempotentes : les posts et commentaires déjà présents sont mis à jour.
