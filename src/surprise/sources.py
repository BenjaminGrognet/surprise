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
    "manual": "Ajout manuel",
}


def source_name(source_id: str) -> str:
    return SOURCES.get(source_id, source_id)
