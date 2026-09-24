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

Paris ZigZag (média de curation : nom, lieu, dates, lien officiel et photo de l'article, pas de texte) :

```bash
uv run python -m surprise.collectors.paris_zigzag --store local
```

Funbooker (annonces parisiennes), Paris-Friendly (bons plans, du plus récent au plus ancien) et Paris City Game
(annuaire d'activités) : faits, prix et photo de la page. `--limit N` arrête la collecte après N fiches :

```bash
uv run python -m surprise.collectors.funbooker --store local --limit 50
uv run python -m surprise.collectors.paris_friendly --store local --limit 50
uv run python -m surprise.collectors.paris_city_game --store local --limit 50
```

Si `opendata.paris.fr` ne résout pas (DNS d'entreprise), passer par le miroir Opendatasoft :

```bash
OPENDATA_PARIS_URL=https://parisdata.opendatasoft.com uv run python -m surprise.collectors.que_faire_a_paris
```

## Enrichissement

Images et descriptions courtes des activités collectées (seules les nouvelles sont traitées) :

```bash
uv run python -m surprise.enrich
```

- Image : photo de la source, sinon `og:image` du site officiel, sinon Google Places si `GOOGLE_PLACES_API_KEY`
  est définie (seul l'identifiant du lieu est stocké, la photo est chargée à l'affichage avec son crédit).
- Description : rédigée par Claude si `ANTHROPIC_API_KEY` est définie (modèle : `SURPRISE_LLM_MODEL`,
  `claude-opus-5-5` par défaut), à partir du texte de la source sous licence ou de l'extrait du site officiel.

## Modération

Interface locale pour relire les activités collectées (`--store local`) et les valider ou les rejeter :

```bash
uv run python -m surprise.admin
```

Ouvre http://127.0.0.1:8000 (`--port` pour changer, `--db` pour une autre base). Raccourcis : `j`/`k` naviguer,
`v` valider, `r` rejeter, `a` remettre en attente, `o` ouvrir la fiche source, `z` annuler. Filtre par source. Les décisions sont conservées
d'une collecte à l'autre ; une fiche modifiée par la source après décision est marquée « Modifiée ».
