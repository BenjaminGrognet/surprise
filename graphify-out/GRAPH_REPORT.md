# Graph Report - surprise  (2026-09-29)

## Corpus Check
- 93 files · ~70,319 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: (none) 1, .css 1, .lock 1)

## Summary
- 1270 nodes · 3641 edges · 84 communities (67 shown, 17 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 190 edges (avg confidence: 0.92)
- Token cost: 137,322 input · 0 output

## Community Hubs (Navigation)
- Booking Engines & Runtime
- Local Store & Availability Cache
- Data Models & Categories
- Route/Candidate Composition
- Activity Tags & Candidate Scoring
- Paris ZigZag Collector
- Que Faire a Paris Collector
- Nights-Out Scoring & Rooms
- Time Out Collector
- Tags CLI & Description
- Stdlib/Runtime Utilities
- Explore Paris Collector
- Route Generation & Evening Planning
- Enrich Tests
- Enrichment Pipeline
- Availability Checkers
- Admin API Tests
- Paris Secret Collector
- Availability Tests
- Extraction Utilities & Descriptions
- Le Bonbon Collector
- Sortir a Paris Collector
- Shared Collector Helpers & Concerts Paris
- Paris ZigZag Tests
- Paris-Friendly Collector
- Local HTTP Server / Images API
- Escape Game Collector
- Nuits Couple Collector
- Venue Naming & Listing Helpers
- Que Faire a Paris Tests
- Cadrage: Legal & Source Tiers
- Account.js Client Auth
- Wecandoo Collector
- Facts Extraction
- GetYourGuide Collector
- Paris Jetaime Billetterie Collector
- Multi-Source Collector Tests
- Keywords CLI & Stdlib
- New Sources Tests
- Paris City Game Collector
- Billetreduc Collector
- Civitatis Collector
- Tiqets Collector
- Shotgun Collector
- Route Naming with Claude
- Generic Product-URL Collector Helpers
- Fever Collector
- Paris Jetaime Collector
- Admin Moderation UI (Filters/Cards)
- Visit Paris Region Collector
- Client Pages Overview (Admin/Account/Quiz)
- Dice Collector
- Local Store Tests
- Client.js Shared Helpers
- Generic Collector Client Helpers
- Models Tests
- Cadrage: ZigZag Rule & Booking Engines
- Event Date/Client Helpers
- Supabase Store
- Evening & Wishes Domain Model
- Module Overview (Keywords/Originality/Tags/Parcours)
- Images Tests
- Cadrage: Data Model & Pipeline & RLS
- Quiz.html Rendering
- Cadrage: Enrichment & Images Rules
- Model Computed Fields
- Nuxt Data Extraction
- Admin.html Moderation Actions
- Cadrage: Vision & Phases
- Models: Metro Towns & Renormalize
- Soiree.html Rendering
- Project Root (surprise)
- Collecteur civitatis (README)
- Collecteur concerts_paris (README)
- Collecteur escape_game (README)
- Collecteur explore_paris (README)
- Collecteur paris_city_game (README)
- Collecteur paris_friendly (README)
- Collecteur paris_jetaime (README)
- Collecteur paris_jetaime_billetterie (README)
- Collecteur selections_couple (README)
- Collecteur sortir_a_paris (README)
- Collecteur tiqets (README)
- Collecteur visit_paris_region (README)

## God Nodes (most connected - your core abstractions)
1. `Normalized` - 130 edges
2. `RawRecord` - 79 edges
3. `safe_url()` - 72 edges
4. `normalize_facts()` - 70 edges
5. `run()` - 67 edges
6. `LocalStore` - 63 edges
7. `utc_now()` - 50 edges
8. `Activity` - 35 edges
9. `sitemap()` - 29 edges
10. `ld_node()` - 28 edges

## Surprising Connections (you probably didn't know these)
- `test_availability_cache()` --uses--> `LocalStore`  [INFERRED]
  tests/test_local_store.py → src/surprise/local_store.py
- `test_latest_normalization_is_kept()` --uses--> `LocalStore`  [INFERRED]
  tests/test_local_store.py → src/surprise/local_store.py
- `test_raw_records_are_deduplicated()` --uses--> `LocalStore`  [INFERRED]
  tests/test_local_store.py → src/surprise/local_store.py
- `test_profile_is_stored_through_the_api()` --uses--> `LocalStore`  [INFERRED]
  tests/test_quiz.py → src/surprise/local_store.py
- `test_raw_record_hash_ignores_key_order()` --uses--> `RawRecord`  [INFERRED]
  tests/test_models.py → src/surprise/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Sources de collecte (30 collecteurs, --store local --limit 50)** — readme_que_faire_a_paris, readme_paris_zigzag, readme_funbooker, readme_paris_friendly, readme_paris_city_game, readme_come_to_paris, readme_paris_secret, readme_concerts_paris, readme_paris_jetaime, readme_paris_jetaime_billetterie, readme_visit_paris_region, readme_explore_paris, readme_wecandoo, readme_fever, readme_getyourguide, readme_tiqets, readme_civitatis, readme_eventbrite, readme_shotgun, readme_billetreduc, readme_time_out, readme_le_bonbon, readme_time_out_hotels, readme_nuits_couple, readme_selections_couple, readme_osm_restaurants, readme_sortir_a_paris, readme_dice, readme_escape_game, readme_osm_loisirs [INFERRED 0.85]
- **Pages client Surprise (parcours utilisateur du site)** — src_surprise_accueil_home, src_surprise_quiz_questionnaire, src_surprise_soiree_evening, src_surprise_compte_account, src_surprise_historique_history, src_surprise_admin_moderation [INFERRED 0.85]
- **Vérification et suivi de réservation** — readme_availability_module, readme_booking_module, readme_parcours_module, docs_cadrage_modele_donnees [INFERRED 0.75]

## Communities (84 total, 17 thin omitted)

### Community 0 - "Booking Engines & Runtime"
Cohesion: 0.05
Nodes (72): collections_abc, concurrent_futures, Response, booking_engine(), booking_form(), booking_urls(), engine_in(), _get() (+64 more)

### Community 1 - "Local Store & Availability Cache"
Cohesion: 0.07
Nodes (26): LocalStore, Any, Path, Insert raw payloads; an unchanged payload (same hash) is skipped. Returns new…, Keep the latest normalization of each record., Normalized activities with their moderation status and a little source context.…, Record a moderation decision against the current payload. False if the activity…, Kept activities without enrichment (or without description, or all with… (+18 more)

### Community 2 - "Data Models & Categories"
Cohesion: 0.12
Nodes (35): BaseModel, enum, field_validator, pydantic, categorize(), Activity categories: a fixed taxonomy of outing types, assigned by rules. An…, Categories in taxonomy order, from source tags or section plus title and venue…, normalize() (+27 more)

### Community 3 - "Route/Candidate Composition"
Cohesion: 0.11
Nodes (34): pickle, booking_url(), build_candidate(), _build_candidate(), check_engines(), coordinates(), default_duration(), _expand_days() (+26 more)

### Community 4 - "Activity Tags & Candidate Scoring"
Cohesion: 0.10
Nodes (31): _activity_tags(), add_nights(), Candidate, _complete(), compose(), distance_km(), fits_slot(), night_for() (+23 more)

### Community 5 - "Paris ZigZag Collector"
Cohesion: 0.12
Nodes (31): calendar, HttpUrl, safe_url(), Article, booking_link(), collect(), _collect_with_client(), _domain() (+23 more)

### Community 6 - "Que Faire a Paris Collector"
Cohesion: 0.13
Nodes (28): model_validator, collect(), _collect_with_client(), _date(), export_url(), fetch(), _in_window(), is_evening() (+20 more)

### Community 7 - "Nights-Out Scoring & Rooms"
Cohesion: 0.19
Nodes (30): How well the activity answers the request, on its own., score(), _ld(), Nights out: hotel and love-room collectors, and the room that ends an evening., _room(), test_love_room_catalogue_page_gives_place_price_and_booking(), test_the_evening_ends_in_a_room_near_its_last_step(), test_time_out_hotel_is_named_by_its_page_title_and_priced_by_the_night() (+22 more)

### Community 8 - "Time Out Collector"
Cohesion: 0.13
Nodes (29): ld_address(), Venue facts of a schema.org location (Place with PostalAddress and…, collect(), _collect_with_client(), fetch_pages(), _amount(), collect(), _collect_with_client() (+21 more)

### Community 9 - "Tags CLI & Description"
Cohesion: 0.10
Nodes (21): functools, pytest, describe(), main(), Any, Tags and vibes: what an activity precisely is, and the mood it answers. - Tags…, Tags of an activity, in taxonomy order, from its title, venue name and…, Vibes an activity answers, in questionnaire order. (+13 more)

### Community 10 - "Stdlib/Runtime Utilities"
Cohesion: 0.10
Nodes (23): gzip, hashlib, http, importlib_resources, os, pathlib, secrets, sqlite3 (+15 more)

### Community 11 - "Explore Paris Collector"
Cohesion: 0.14
Nodes (28): collect(), _collect_with_client(), fetch_tour_urls(), locate(), main(), normalize(), parse_tour(), Any (+20 more)

### Community 12 - "Route Generation & Evening Planning"
Cohesion: 0.10
Nodes (26): Base, candidates_for(), evening_routes(), generate(), main(), night_budget_for(), _paced(), plan() (+18 more)

### Community 13 - "Enrich Tests"
Cohesion: 0.12
Nodes (21): activity(), fake_client(), FakeMessages, no_openstreetmap(), fixture, mock, parametrize, test_categorize() (+13 more)

### Community 14 - "Enrichment Pipeline"
Cohesion: 0.13
Nodes (27): booking_link(), describe(), enrich_one(), find_place(), _is_deep_link(), _is_sibling(), main(), osm_address() (+19 more)

### Community 15 - "Availability Checkers"
Cohesion: 0.18
Nodes (24): base64, Availability, check(), check_4escape(), check_come_to_paris(), check_funbooker(), check_sevenrooms(), check_wecandoo() (+16 more)

### Community 16 - "Admin API Tests"
Cohesion: 0.11
Nodes (13): http_server, parametrize, request(), test_invalid_requests_are_refused(), test_meta_lists_categories_and_sources(), test_page_is_served(), test_place_photo_needs_a_key_and_a_valid_id(), test_source_name_and_ids_with_slash_and_hash() (+5 more)

### Community 17 - "Paris Secret Collector"
Cohesion: 0.17
Nodes (22): collect(), _collect_with_client(), _entries(), fetch_articles(), main(), normalize(), parse_article(), Any (+14 more)

### Community 18 - "Availability Tests"
Cohesion: 0.17
Nodes (19): come_to_paris(), item(), pax_form(), mock, slot(), test_4escape_sessions_with_places_for_two(), test_come_to_paris_closed_day(), test_come_to_paris_hours_for_two() (+11 more)

### Community 19 - "Extraction Utilities & Descriptions"
Cohesion: 0.14
Nodes (18): dataclasses, math, extract(), main(), Any, Everything written about an activity: title, venue, source text, site excerpt,…, Keywords found in a text, in lexicon order., texts() (+10 more)

### Community 20 - "Le Bonbon Collector"
Cohesion: 0.18
Nodes (21): Decimal, itertools, euro_amounts(), Amounts in euros mentioned in a price text, sorted., collect(), _collect_with_client(), facts(), fetch_articles() (+13 more)

### Community 21 - "Sortir a Paris Collector"
Cohesion: 0.18
Nodes (21): _clean_url(), collect(), _collect_with_client(), fetch_pages(), _first(), _in_scope(), _link(), main() (+13 more)

### Community 22 - "Shared Collector Helpers & Concerts Paris"
Cohesion: 0.19
Nodes (18): httpx, Pieces shared by the collectors: normalization result, parsing helpers, command…, Command line shared by the collectors: summary, then optional storage., run(), _collect_with_client(), main(), Collector for concerts.paris (agenda of concerts, plays and exhibitions, tier…, collect() (+10 more)

### Community 23 - "Paris ZigZag Tests"
Cohesion: 0.14
Nodes (13): mock, parametrize, results(), test_collect_reads_recent_articles_in_scope(), test_generic_heading_takes_the_venue_name(), test_image_is_the_last_article_photo_above_the_block(), test_is_evening_ignores_closing_times(), test_parse_dates() (+5 more)

### Community 24 - "Paris-Friendly Collector"
Cohesion: 0.20
Nodes (18): collect(), _collect_with_client(), _fold(), latest_id(), main(), normalize(), parse_page(), Any (+10 more)

### Community 25 - "Local HTTP Server / Images API"
Cohesion: 0.20
Nodes (17): activities_json(), main(), make_handler(), do_GET(), do_POST(), _image_copy(), _place_photo(), _send() (+9 more)

### Community 26 - "Escape Game Collector"
Cohesion: 0.21
Nodes (16): _clean(), collect(), _collect_with_client(), fetch_rooms(), main(), normalize(), parse_room(), Any (+8 more)

### Community 27 - "Nuits Couple Collector"
Cohesion: 0.23
Nodes (16): collect(), _collect_with_client(), _get(), guide_rooms(), main(), normalize(), parse_room(), Any (+8 more)

### Community 28 - "Venue Naming & Listing Helpers"
Cohesion: 0.13
Nodes (16): _hour(), _listing(), load(), name_by_rules(), _named(), _place(), Path, The activity as the source names it, with its venue when the title does not say… (+8 more)

### Community 29 - "Que Faire a Paris Tests"
Cohesion: 0.17
Nodes (10): by_id(), mock, test_collect_queries_the_six_week_window(), test_daytime_free_event_with_invalid_url(), test_event_is_normalized(), test_events_outside_paris_are_rejected(), test_occurrences_are_limited_to_the_window(), test_offer_prices_and_booking() (+2 more)

### Community 30 - "Cadrage: Legal & Source Tiers"
Cohesion: 0.13
Nodes (16): Contraintes légales (CGU, robots.txt, attribution ODbL), Sources par niveau (1 open data → 4 compléments), surprise.availability : disponibilités en direct, Collecteur billetreduc, Collecteur come_to_paris, Collecteur dice, Collecteur eventbrite, Collecteur fever (+8 more)

### Community 31 - "Account.js Client Auth"
Cohesion: 0.28
Nodes (15): accountProfile(), authFetch(), chooseEvening(), clearSession(), currentUser(), eveningsHistory(), getSession(), renderAccountNav() (+7 more)

### Community 32 - "Wecandoo Collector"
Cohesion: 0.28
Nodes (15): Normalized, collect(), _collect_with_client(), fetch_workshop_urls(), main(), normalize(), parse_workshop(), Any (+7 more)

### Community 33 - "Facts Extraction"
Cohesion: 0.26
Nodes (14): _date(), _float(), ld_nodes(), normalize_facts(), parse_datetime(), _price(), Any, datetime (+6 more)

### Community 34 - "GetYourGuide Collector"
Cohesion: 0.25
Nodes (14): address_in_text(), The first Paris street address mentioned in a text: '12 rue X, 75011 Paris'., collect(), _collect_with_client(), fetch_activity_urls(), main(), normalize(), parse_activity() (+6 more)

### Community 35 - "Paris Jetaime Billetterie Collector"
Cohesion: 0.27
Nodes (14): collect(), _collect_with_client(), fetch_product_urls(), _fr(), main(), normalize(), parse_product(), Any (+6 more)

### Community 36 - "Multi-Source Collector Tests"
Cohesion: 0.15
Nodes (5): mock, raw(), test_normalize_facts_evening_show(), test_normalize_facts_rejections(), test_shotgun_asks_the_cumulative_page_until_it_ends()

### Community 37 - "Keywords CLI & Stdlib"
Cohesion: 0.18
Nodes (12): argparse, collections, importlib, inspect, json, Keywords: the words that tell an activity's atmosphere, found in all its texts.…, main(), Counter (+4 more)

### Community 38 - "New Sources Tests"
Cohesion: 0.18
Nodes (5): datetime, mock, test_reserve_page_embeds_the_engine(), test_restaurant_without_online_booking_is_rejected(), test_site_with_a_zenchef_widget_is_kept()

### Community 39 - "Paris City Game Collector"
Cohesion: 0.23
Nodes (13): html, collect(), _collect_with_client(), fetch_projects(), main(), parse_project(), Any, Client (+5 more)

### Community 40 - "Billetreduc Collector"
Cohesion: 0.27
Nodes (13): collect(), _collect_with_client(), _description(), fetch_show_urls(), main(), normalize(), parse_show(), Any (+5 more)

### Community 41 - "Civitatis Collector"
Cohesion: 0.27
Nodes (13): collect(), _collect_with_client(), fetch_activity_urls(), main(), normalize(), parse_activity(), Any, Client (+5 more)

### Community 42 - "Tiqets Collector"
Cohesion: 0.27
Nodes (13): complete_place(), A payload without Paris postcode: from its address text, else its coordinates,…, collect(), _collect_with_client(), fetch_product_urls(), main(), normalize(), parse_product() (+5 more)

### Community 43 - "Shotgun Collector"
Cohesion: 0.26
Nodes (13): collect(), _collect_with_client(), fetch_event_slugs(), main(), normalize(), parse_event(), Any, Client (+5 more)

### Community 44 - "Route Naming with Claude"
Cohesion: 0.19
Nodes (13): _centre(), _main_tag(), _name_later(), name_with_claude(), pick(), Title and pitch of each route written by Claude; False when unavailable., Claude's titles into the saved page, for the routes still on it (one may have…, The evening's price, the night apart. (+5 more)

### Community 45 - "Generic Product-URL Collector Helpers"
Cohesion: 0.21
Nodes (13): collect(), _collect_with_client(), fetch_product_urls(), _ld_nodes(), _lines(), main(), parse_product(), Any (+5 more)

### Community 46 - "Fever Collector"
Cohesion: 0.29
Nodes (12): collect(), _collect_with_client(), fetch_plan_ids(), main(), normalize(), parse_plan(), Any, Client (+4 more)

### Community 47 - "Paris Jetaime Collector"
Cohesion: 0.32
Nodes (12): collect(), _collect_with_client(), facts(), fetch_events(), main(), normalize(), Any, Client (+4 more)

### Community 48 - "Admin Moderation UI (Filters/Cards)"
Cohesion: 0.18
Nodes (12): Base : activités réservables/gratuites pour un couple (exception bars/clubs/restos), Filtres durs / souples, card() — admin.html, description() — admin.html, figure() — admin.html, filtered() — admin.html, isEvening() — admin.html, openAt20() — admin.html (+4 more)

### Community 49 - "Visit Paris Region Collector"
Cohesion: 0.30
Nodes (11): re, collect(), _collect_with_client(), fetch_place_urls(), main(), normalize(), Any, Client (+3 more)

### Community 50 - "Client Pages Overview (Admin/Account/Quiz)"
Cohesion: 0.29
Nodes (11): surprise.admin : modération, Compte client et historique (Supabase Auth, RLS), surprise.quiz : questionnaire client + serveur, account.js (signIn/signUp/signOut/accountProfile/supabaseConfig…) — script partagé référencé, Page d'accueil client (accueil.html), Interface de modération (admin.html), client.js (helpers h/$, dayField, choiceContent…) — script partagé référencé, Page de compte (compte.html) (+3 more)

### Community 51 - "Dice Collector"
Cohesion: 0.36
Nodes (10): collect(), _collect_with_client(), main(), normalize(), parse_event(), Any, datetime, Collector for Dice (concerts and club nights ticketing, tier 2: bookable… (+2 more)

### Community 52 - "Local Store Tests"
Cohesion: 0.31
Nodes (9): _store_with_fixture(), test_activities_rejected_at_collection_are_listed_apart(), test_availability_cache(), test_enrichment_is_listed_and_survives_recollection(), test_latest_normalization_is_kept(), test_moderation_decision_survives_recollection_and_flags_changes(), test_moderation_lists_kept_activities_as_proposed(), test_moderation_rejects_unknown_or_filtered_activities() (+1 more)

### Community 53 - "Client.js Shared Helpers"
Cohesion: 0.33
Nodes (5): choiceContent(), dayField(), h(), isoDay(), nextFriday()

### Community 54 - "Generic Collector Client Helpers"
Cohesion: 0.36
Nodes (9): collect(), facts(), fetch_events(), normalize(), Any, Client, datetime, Paris events, the soonest first, page after page. (+1 more)

### Community 55 - "Models Tests"
Cohesion: 0.25
Nodes (8): parametrize, test_occurrence_must_end_after_start(), test_occurrence_requires_timezone(), test_offer_price_consistency(), test_paris_venue(), test_raw_record_hash_ignores_key_order(), test_venue_in_a_town_the_metro_reaches(), test_venue_outside_paris_is_rejected()

### Community 56 - "Cadrage: ZigZag Rule & Booking Engines"
Cohesion: 0.32
Nodes (8): lead_text : texte des médias gardé pour rédaction Claude, Règle Paris ZigZag : n'extraire que l'entité, reconstruire depuis le site officiel, surprise/booking.py : moteurs de réservation reconnus, Collecteur osm_loisirs, Collecteur osm_restaurants, Collecteur paris_zigzag, Collecteur time_out_hotels, Fixture de test : article Paris ZigZag (markup inventé)

### Community 57 - "Event Date/Client Helpers"
Cohesion: 0.29
Nodes (8): Match, _day(), fetch_events(), Client, date, timedelta, The day of the address, of the year to come ("23rd-oct")., Paris events of the window by the day in their address, soonest first.

### Community 58 - "Supabase Store"
Cohesion: 0.25
Nodes (3): Client, Insert raw payloads; an unchanged payload (same hash) is skipped., SupabaseStore

### Community 59 - "Evening & Wishes Domain Model"
Cohesion: 0.29
Nodes (7): evening(), _late(), date, An hour as the evening sees it: 03:30 comes after 23:30., One evening's settings: its wishes and occasion over the profile, which keeps…, The evenings to plan for a profile and wishes: the days given, its first…, requests_for()

### Community 60 - "Module Overview (Keywords/Originality/Tags/Parcours)"
Cohesion: 0.33
Nodes (6): surprise/keywords.py : mots-clés d'ambiance, Collecteur nuits_couple, surprise/originality.py : score d'originalité, surprise.parcours : composition de soirée, surprise/tags.py : tags et facettes, Vibes : envies larges du questionnaire

### Community 61 - "Images Tests"
Cohesion: 0.40
Nodes (4): respx, mock, test_local_copy_downloads_once(), test_local_copy_refuses_non_images()

### Community 62 - "Cadrage: Data Model & Pipeline & RLS"
Cohesion: 0.50
Nodes (5): Collecte limitée par source (--limit 50), Décisions actées (stack Python, Supabase, LLM Claude…), Modèle de données (sources, raw_records, venues, activities, occurrences, offers, provenance), Pipeline de collecte, RLS : public ne lit que les activités approved

### Community 63 - "Quiz.html Rendering"
Cohesion: 0.40
Nodes (5): start() — accueil.html, body() — quiz.html, render() — quiz.html, renderProfile() — quiz.html, showProfile() — quiz.html

### Community 64 - "Cadrage: Enrichment & Images Rules"
Cohesion: 0.50
Nodes (4): Données manquantes : OpenStreetMap (Nominatim) d'abord, Enrichissement sans descriptions Claude par défaut, Images : origine gardée, licences ignorées pour l'instant, surprise.enrich : images, lieu, réservation, description

### Community 66 - "Nuxt Data Extraction"
Cohesion: 0.50
Nodes (4): nuxt_data(), value(), The state a Nuxt site embeds in its page (__NUXT_DATA__), rebuilt from its…, test_nuxt_data()

### Community 67 - "Admin.html Moderation Actions"
Cohesion: 0.67
Nodes (3): decide() — admin.html, save() — admin.html, undo() — admin.html

## Ambiguous Edges - Review These
- `Collecte limitée par source (--limit 50)` → `Décisions actées (stack Python, Supabase, LLM Claude…)`  [AMBIGUOUS]
  docs/cadrage.md · relation: conceptually_related_to

## Knowledge Gaps
- **45 isolated node(s):** `surprise`, `Collecteur que_faire_a_paris`, `Collecteur paris_friendly`, `Collecteur paris_city_game`, `Collecteur come_to_paris` (+40 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 353 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Collecte limitée par source (--limit 50)` and `Décisions actées (stack Python, Supabase, LLM Claude…)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Normalized` connect `Wecandoo Collector` to `Booking Engines & Runtime`, `Data Models & Categories`, `Paris ZigZag Collector`, `Que Faire a Paris Collector`, `Time Out Collector`, `Explore Paris Collector`, `Paris Secret Collector`, `Le Bonbon Collector`, `Sortir a Paris Collector`, `Shared Collector Helpers & Concerts Paris`, `Paris-Friendly Collector`, `Escape Game Collector`, `Nuits Couple Collector`, `Facts Extraction`, `GetYourGuide Collector`, `Paris Jetaime Billetterie Collector`, `Paris City Game Collector`, `Billetreduc Collector`, `Civitatis Collector`, `Tiqets Collector`, `Shotgun Collector`, `Generic Product-URL Collector Helpers`, `Fever Collector`, `Paris Jetaime Collector`, `Visit Paris Region Collector`, `Dice Collector`, `Generic Collector Client Helpers`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `LocalStore` connect `Local Store & Availability Cache` to `Wecandoo Collector`, `Data Models & Categories`, `Route/Candidate Composition`, `Activity Tags & Candidate Scoring`, `Keywords CLI & Stdlib`, `Tags CLI & Description`, `Stdlib/Runtime Utilities`, `Route Generation & Evening Planning`, `Enrichment Pipeline`, `Availability Checkers`, `Admin API Tests`, `Extraction Utilities & Descriptions`, `Local Store Tests`, `Shared Collector Helpers & Concerts Paris`, `Local HTTP Server / Images API`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `run()` connect `Shared Collector Helpers & Concerts Paris` to `Booking Engines & Runtime`, `Local Store & Availability Cache`, `Data Models & Categories`, `Paris ZigZag Collector`, `Que Faire a Paris Collector`, `Time Out Collector`, `Explore Paris Collector`, `Paris Secret Collector`, `Le Bonbon Collector`, `Sortir a Paris Collector`, `Paris-Friendly Collector`, `Escape Game Collector`, `Nuits Couple Collector`, `Wecandoo Collector`, `GetYourGuide Collector`, `Paris Jetaime Billetterie Collector`, `Paris City Game Collector`, `Billetreduc Collector`, `Civitatis Collector`, `Tiqets Collector`, `Shotgun Collector`, `Generic Product-URL Collector Helpers`, `Fever Collector`, `Paris Jetaime Collector`, `Visit Paris Region Collector`, `Dice Collector`, `Supabase Store`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 70 inferred relationships involving `Normalized` (e.g. with `collect()` and `_collect_with_client()`) actually correct?**
  _`Normalized` has 70 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `RawRecord` (e.g. with `Normalized` and `normalize_facts()`) actually correct?**
  _`RawRecord` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `normalize_facts()` (e.g. with `ActivityKind` and `PriceUnit`) actually correct?**
  _`normalize_facts()` has 3 INFERRED edges - model-reasoned connections that need verification._