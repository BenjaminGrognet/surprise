"""Display names of the sources, mirroring the public.sources seed in supabase/migrations."""

SOURCES = {
    "que_faire_a_paris": "Que Faire à Paris",
    "openagenda": "OpenAgenda",
    "datatourisme": "DATAtourisme",
    "paris_musees": "Paris Musées",
    "paris_zigzag": "Paris ZigZag",
    "funbooker": "Funbooker",
    "paris_friendly": "Paris-Friendly",
    "paris_city_game": "Paris City Game",
    "come_to_paris": "Come to Paris",
    "paris_secret": "Paris Secret",
    "concerts_paris": "concerts.paris",
    "paris_jetaime": "Paris je t'aime",
    "paris_jetaime_billetterie": "Paris je t'aime (billetterie)",
    "visit_paris_region": "VisitParisRegion",
    "explore_paris": "Explore Paris",
    "wecandoo": "Wecandoo",
    "fever": "Fever",
    "getyourguide": "GetYourGuide",
    "tiqets": "Tiqets",
    "civitatis": "Civitatis",
    "eventbrite": "Eventbrite",
    "shotgun": "Shotgun",
    "billetreduc": "BilletRéduc",
    "time_out": "Time Out Paris",
    "time_out_hotels": "Time Out Paris (hôtels)",
    "nuits_couple": "Nuits en amoureux (love rooms, hôtels insolites)",
    "le_bonbon": "Le Bonbon",
    "selections_couple": "Sélections couple (blogs)",
    "osm_restaurants": "Restaurants OpenStreetMap",
    "manual": "Ajout manuel",
}


def source_name(source_id: str) -> str:
    return SOURCES.get(source_id, source_id)
