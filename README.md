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
