# surprise
## Collecteurs

```bash
uv run pytest
# Que Faire à Paris : résumé des fiches retenues / rejetées (6 prochaines semaines)
uv run python -m surprise.collectors.que_faire_a_paris
# … et enregistrement des payloads bruts dans Supabase (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
uv run python -m surprise.collectors.que_faire_a_paris --store
```
