# Cadrage — Surprise

## Vision

Constituer automatiquement une base d'activités de couple à Paris pour composer des
soirées surprises originales et mémorables. Priorité à l'insolite, au romantique non
basique et à la nouveauté (nouveaux lieux, restaurants concept, événements éphémères).

Exemples d'activités visées : balade insolite, escape game, lancer de hache, expo,
musée, massage à deux, comedy club, théâtre, concert, bar, food truck, lecture de
poésie, concert dans une église…

## Phases du projet

1. **Collecte** — identifier les sources et construire les collecteurs *(ce document)*
2. **Stockage & modèle de données**
3. **Catégorisation** — vibe, tags, score d'originalité
4. Composition de soirées *(hors périmètre pour l'instant)*

## Données à récupérer par activité

| Champ | Notes |
|---|---|
| Lieu | adresse, arrondissement, coordonnées GPS |
| Durée | estimée si absente |
| Prix | min/max, gratuit, prix par personne ou par couple |
| Créneaux horaires | occurrences datées ou horaires d'ouverture |
| Lien site | site officiel du lieu / de l'événement |
| Lien réservation | + réservation en ligne possible (oui/non) |
| Réservation payante | oui/non (acompte, billet) |
| Image | avec origine et licence |
| Description | reformulée, jamais copiée |
| Temporalité | temporaire ou permanent |
| Provenance | source, URL, date de collecte, licence |

## Décisions actées

| Sujet | Décision |
|---|---|
| Usage | **Produit public** → sources licites uniquement, provenance tracée |
| Fréquence | Collecte **quotidienne** (nocturne) |
| Fenêtre | Événements des **6 prochaines semaines** + lieux permanents (revérifiés mensuellement) |
| Stack | **Python** (httpx, Playwright, Pydantic) + cron cloud (GitHub Actions) |
| LLM | API Claude, **budget modéré** — extraction, enrichissement, reformulation |
| Curation | **File de modération** : le pipeline propose, un humain valide avant publication |
| Modèle économique | Non défini — on stocke le potentiel d'affiliation par source pour garder l'option |
| MVP | Que Faire à Paris + OpenAgenda + extraction LLM sur un média |
| Stockage | **Supabase** (PostgreSQL + PostGIS) — schéma dans `supabase/migrations/` |

## Sources

### Niveau 1 — Open data / APIs (socle structuré)

| Source | Accès | Licence / contraintes |
|---|---|---|
| Que Faire à Paris (Ville de Paris) | API opendata.paris.fr | ODbL : attribution + partage à l'identique de la base |
| OpenAgenda | API | Licence variable selon l'agenda |
| DATAtourisme | API / flux | Licence Ouverte Etalab |
| Paris Musées | API / open data | À vérifier |

### Niveau 2 — Billetteries & activités (via affiliation / API partenaires)

Fever (dont Candlelight), GetYourGuide (Partner API), Ticketmaster / Fnac Spectacles
(Awin), Billetreduc, Shotgun, Dice, Eventbrite, Wecandoo, Funbooker, Airbnb Expériences.

Pas de scraping contraire aux CGU : on passe par les programmes d'affiliation ou
partenariats. Plusieurs pages exposent du JSON-LD `schema.org/Event`, exploitable là où
c'est autorisé.

### Niveau 3 — Médias de curation (signal de découverte uniquement)

Paris ZigZag, Sortiraparis, Time Out Paris, Le Bonbon, Paris Secret, My Little Paris,
Le Fooding, Télérama Sortir — y compris via leurs **newsletters** (boîte mail dédiée).

Règle : le LLM n'en extrait que l'**entité** (nom du lieu / de l'événement, date). La
fiche est ensuite reconstruite depuis le **site officiel** du lieu. Aucun texte ni image
des médias n'est republié.

### Niveau 4 — Compléments

- Google Places API : horaires, photos sous licence, géocodage
- Ajout manuel par lien (Instagram, TikTok, article) → extraction LLM
- À terme : soumission directe par les lieux partenaires

## Pipeline de collecte

```
Collecteurs (1 par source)
  → Stockage brut (payload tel quel, horodaté)
  → Normalisation (format commun Pydantic)
  → Filtres durs
  → Déduplication (même lieu/événement vu sur plusieurs sources)
  → Enrichissement (site officiel, résa, prix, créneaux, reformulation — LLM)
  → File de modération
  → [Phase 3 : catégorisation, vibe, tags, score d'originalité]
```

Deux natures de fiches, rafraîchies différemment :
- **Lieu permanent** (bar caché, lancer de hache) — horaires d'ouverture
- **Événement daté** (concert, expo temporaire, lecture) — occurrences

## Filtres

| Filtre | Type | Traitement |
|---|---|---|
| Paris intra-muros | **Dur** | Rejet à la collecte |
| Jeune public / famille | **Dur** | Rejet à la collecte |
| Soirée | **Souple** | Marqué ; évalué sur les **créneaux** (un lieu ouvert 10h–23h est éligible) |
| Trop basique | **Souple** | Marqué ; remplacé en phase 3 par un score d'originalité filtrable |

Filtres souples = on garde la donnée, on ne perd rien d'irrécupérable.

## Contraintes légales (produit public)

- Respect des CGU et du `robots.txt` ; privilégier APIs, open data, affiliation
- Attribution des sources ODbL ; redistribution sous même licence si la base est publiée
- Descriptions reformulées ; images uniquement de sources licites, licence stockée
- Provenance conservée pour chaque champ important

## Modèle de données

```
sources        référentiel des sources (niveau, licence, affiliation possible)
raw_records    payload brut par source, dédupliqué par hash — permet de tout retraiter
venues         lieu à Paris intra-muros (contrainte SQL), arrondissement calculé, geo PostGIS
activities     fiche activité, permanent|temporary, statut proposed|approved|rejected
occurrences    créneaux datés d'une activité
offers         prix, unité (personne/couple/groupe), réservation, lien affilié
provenance     relie une entité et ses champs au raw_record d'origine
```

- RLS : le public ne lit que les activités `approved` (et leurs lieux, créneaux, offres).
  `raw_records` et `provenance` restent privés ; les collecteurs écrivent avec la clé service.
- Les modèles Pydantic des collecteurs (`src/surprise/models.py`) reflètent ce schéma et
  appliquent les filtres durs dès la normalisation.

## Questions ouvertes

- Média du MVP : **Paris ZigZag** (orienté insolite) ou **Sortiraparis** (volume) ?
- Modèle économique
