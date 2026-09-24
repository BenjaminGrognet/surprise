"""Activity categories: a fixed taxonomy of outing types, assigned by rules.

An activity can have several categories (a jazz concert on a barge is both
"concert" and "croisiere"). Rules look at the source's own tags or section and
at keywords in the title and venue name.
"""

import re

CATEGORIES = {
    "concert": "Concert",
    "theatre": "Théâtre",
    "humour": "Humour / stand-up",
    "cabaret": "Cabaret / music-hall",
    "spectacle": "Spectacle / cirque",
    "danse": "Danse / soirée dansante",
    "cinema": "Cinéma / projection",
    "expo": "Exposition",
    "musee": "Musée",
    "visite": "Visite / balade",
    "lieu_insolite": "Lieu insolite",
    "atelier": "Atelier créatif",
    "gastronomie": "Gastronomie / dégustation",
    "bar": "Bar",
    "restaurant": "Restaurant",
    "jeux": "Jeux / escape game",
    "sensations": "Activité sensations",
    "bien_etre": "Bien-être / spa",
    "croisiere": "Croisière / péniche",
    "festival": "Festival",
    "nuit": "Soirée / clubbing",
    "conference": "Conférence / lecture",
    "nature": "Nature / jardin",
    "salon": "Salon / marché",
}

# Que Faire à Paris tags.
_TAGS = {
    "concert": "concert",
    "spectacle musical": "spectacle",
    "théâtre": "theatre",
    "humour": "humour",
    "cirque": "spectacle",
    "danse": "danse",
    "ecrans": "cinema",
    "expo": "expo",
    "art contemporain": "expo",
    "photo": "expo",
    "peinture": "expo",
    "street-art": "expo",
    "bd": "expo",
    "balade urbaine": "visite",
    "atelier": "atelier",
    "gourmand": "gastronomie",
    "festival": "festival",
    "nuit": "nuit",
    "conférence": "conference",
    "littérature": "conference",
    "sciences": "conference",
    "nature": "nature",
    "salon": "salon",
    "brocante": "salon",
}

# Paris ZigZag sections (first two path segments of the article URL).
_SECTIONS = {
    "bar-restaurant/bar": "bar",
    "bar-restaurant/restaurant": "restaurant",
    "sortir-paris/theatre": "theatre",
    "sortir-paris/balade-paris": "visite",
    "sortir-paris/visites-guidees-zigzag": "visite",
    "insolite/lieux-insolites": "lieu_insolite",
    "insolite/histoire-insolite-paris": "lieu_insolite",
    "insolite/balades-excursions": "visite",
    "visites-privees": "visite",
}

_KEYWORDS = [
    ("humour", r"stand[- ]?up|comedy|humour|humoriste|one[- ](?:wo)?man[- ]show|impro(?:visation)?\b"),
    ("cabaret", r"cabaret|music[- ]hall|burlesque|revue|crazy horse|paradis latin|moulin rouge|lido"),
    ("jeux", r"escape[- ]game|jeux? de (?:société|piste|rôle)|quiz|blind[- ]test|karaok[ée]|murder party|bowling|billard"),
    ("sensations", r"lancer de hache|hache|laser[- ]?game|trampoline|escalade|karting|réalité virtuelle|\bvr\b|simulateur|parachute|flyboard"),
    ("bien_etre", r"\bspa\b|massage|hammam|bien[- ]être|sauna|méditation|sophrologie"),
    ("croisiere", r"péniche|croisière|bateau|navigation|bateaux[- ]mouches"),
    ("gastronomie", r"dégustation|œnolog|oenolog|\bvins?\b|cocktails?|brunch|gastronom|chocolat|fromage|dîner[- ]spectacle|food"),
    ("musee", r"\bmusée"),
    ("visite", r"\bvisite|balade|promenade|parcours|excursion|randonnée urbaine"),
    ("cinema", r"cinéma|projection|\bfilm|ciné[- ]|drive[- ]in"),
    ("concert", r"concert|\bjazz|récital|orchestre|philharmoni|chorale|\blive\b|opéra|symphoni"),
    ("theatre", r"théâtre|\bpièce\b|comédie"),
    ("expo", r"\bexpo(?:sition)?s?\b|galerie|vernissage|installation immersive"),
    ("danse", r"\bdanse|bal\b|salsa|tango|swing|rock (?:4|à)"),
    ("nuit", r"clubbing|\bdj\b|soirée|nuit blanche|night"),
    ("festival", r"festival"),
    ("atelier", r"\batelier|initiation|workshop|cours de"),
    ("bar", r"\bbar\b|speakeasy|rooftop|pub\b|brasserie artisanale"),
    ("restaurant", r"restaurant|bistrot|\btable\b|gastronomique"),
    ("lieu_insolite", r"insolite|secret|caché|souterrain|catacombe"),
    ("nature", r"jardin|\bparc\b|serre|potager|bois de"),
    ("conference", r"conférence|lecture|rencontre littéraire|débat|poésie"),
    ("salon", r"\bsalon\b|marché|brocante|foire"),
]
_KEYWORD_PATTERNS = [(category, re.compile(pattern, re.IGNORECASE)) for category, pattern in _KEYWORDS]


def categorize(
    title: str, venue_name: str | None = None, tags: list[str] | None = None, section: str | None = None
) -> list[str]:
    """Categories in taxonomy order, from source tags or section plus title and venue keywords."""
    found = {_TAGS[t.strip().lower()] for t in tags or [] if t.strip().lower() in _TAGS}
    if section and (category := _SECTIONS.get(section)):
        found.add(category)
    text = f"{title} {venue_name or ''}"
    found |= {category for category, pattern in _KEYWORD_PATTERNS if pattern.search(text)}
    return [category for category in CATEGORIES if category in found]
