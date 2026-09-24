# surprise
## Collecteurs

```bash
uv run pytest
# Que Faire à Paris : résumé des fiches retenues / rejetées (6 prochaines semaines)
uv run python -m surprise.collectors.que_faire_a_paris
# … en local dans data/surprise.db (SQLite, ignoré par git)
uv run python -m surprise.collectors.que_faire_a_paris --store local
# … ou les payloads bruts dans Supabase (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
uv run python -m surprise.collectors.que_faire_a_paris --store supabase
```

Si `opendata.paris.fr` ne résout pas (DNS d'entreprise), passer par le miroir Opendatasoft :

```bash
OPENDATA_PARIS_URL=https://parisdata.opendatasoft.com uv run python -m surprise.collectors.que_faire_a_paris
```

## Modération

Interface locale pour relire les activités collectées (`--store local`) et les valider ou les rejeter :

```bash
uv run python -m surprise.admin
```

Ouvre http://127.0.0.1:8000 (`--port` pour changer, `--db` pour une autre base). Raccourcis : `j`/`k` naviguer,
`v` valider, `r` rejeter, `a` remettre en attente, `o` ouvrir la fiche source. Les décisions sont conservées
d'une collecte à l'autre ; une fiche modifiée par la source après décision est marquée « Modifiée ».
