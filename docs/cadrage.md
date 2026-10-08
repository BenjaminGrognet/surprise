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
| Image | avec son origine |
| Description | courte, tirée du texte de la source ou rédigée par Claude |
| Temporalité | temporaire ou permanent |
| Provenance | source, URL, date de collecte |

## Décisions actées

| Sujet | Décision |
|---|---|
| Usage | **Produit public** → provenance tracée |
| Fréquence | Collecte **quotidienne** (nocturne) |
| Fenêtre | Événements des **6 prochaines semaines** + lieux permanents (revérifiés mensuellement) |
| Stack | **Python** (httpx, Playwright, Pydantic) + cron cloud (GitHub Actions) |
| LLM | API Claude, **budget modéré** — extraction, enrichissement, reformulation |
| Curation | **File de modération** : le pipeline propose, un humain valide avant publication |
| Modèle économique | Non défini — on stocke le potentiel d'affiliation par source pour garder l'option |
| MVP | Que Faire à Paris + OpenAgenda + **Paris ZigZag** (média retenu, orienté insolite) |
| Stockage | **Supabase** (PostgreSQL + PostGIS) — schéma dans `supabase/migrations/` |
| Formules | **Secret Date** (un couple) et, depuis le 6 octobre 2026, **Secret Squad** (une bande de 2 à 10 : EVJF, EVG, anniversaire, un pote…) — même mécanique, base commune, le parcours filtre selon la formule |

## Sources

### Niveau 1 — Open data / APIs (socle structuré)

| Source | Accès |
|---|---|
| Que Faire à Paris (Ville de Paris) | API opendata.paris.fr |
| OpenAgenda | API |
| DATAtourisme | API / flux |
| Paris Musées | API / open data |

### Niveau 2 — Billetteries & activités (via affiliation / API partenaires)

Fever (dont Candlelight), GetYourGuide (Partner API), Ticketmaster / Fnac Spectacles
(Awin), Billetreduc, Shotgun, Dice, Eventbrite, Wecandoo, Funbooker, Airbnb Expériences.

Programmes d'affiliation et partenariats. Plusieurs pages exposent du JSON-LD
`schema.org/Event`.

### Niveau 3 — Médias de curation

Paris ZigZag, Sortiraparis, Time Out Paris, Le Bonbon, Paris Secret, My Little Paris,
Le Fooding, Télérama Sortir — y compris via leurs **newsletters** (boîte mail dédiée).

On en garde l'**entité** (nom du lieu / de l'événement, date), la photo et le texte de
l'article ; la fiche est complétée depuis le **site officiel** du lieu.

Paris ZigZag : le collecteur lit les sitemaps et garde les **blocs pratiques** (nom, lien
officiel, lieu, adresse, dates, tarifs, horaires), avec la photo et le texte de l'article.
Les articles sans bloc pratique (~60 %) restent à extraire par LLM.

### Niveau 4 — Compléments

- Google Places API : horaires, photos, géocodage
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
| Hors cible (sport municipal, seniors, santé, solidarité) | **Dur** | Rejet à la collecte ; payload brut conservé, retraitable |
| Soirée | **Souple** | Marqué ; évalué sur les **créneaux** (un lieu ouvert 10h–23h est éligible) |
| Trop basique | **Souple** | Marqué ; remplacé en phase 3 par un score d'originalité filtrable |

Filtres souples = on garde la donnée, on ne perd rien d'irrécupérable.

## Collecte

- Respect du `robots.txt` et du rythme de chaque site ; privilégier APIs, open data, partenariats
- Provenance conservée pour chaque champ important

## Modèle de données

```
sources        référentiel des sources (niveau, affiliation possible)
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

- Modèle économique
