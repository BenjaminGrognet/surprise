"""Tags and vibes: what an activity precisely is, and the mood it answers.

- Tags describe the activity precisely ("mini-golf", "céramique", "rooftop",
  "aux chandelles"), in three facets: what you do, the setting, the moment.
- Vibes are the broad wishes asked in the client questionnaire ("Relever un
  défi", "Rire", "Se détendre"). They follow from the tags and categories:
  a mini-golf is "Bouger" and "Relever un défi".

Both are computed on read from the stored activity, by rules on the title and
the venue name, so the rules can be tuned without collecting again.
"""

import argparse
import re
from collections import Counter
from functools import lru_cache
from typing import Any

from surprise.categories import CATEGORIES

FACETS = {"activite": "Activité", "cadre": "Cadre", "moment": "Moment"}

# key, label, facet, pattern on title and venue name.
_TAG_RULES = [
    # Jeux et défis
    ("escape_game", "Escape game", "activite", r"escape|urbexscape|hell out|bomb squad|\bthe (?:one|edge|trip)\b|pandore|bureau des légendes|seven squares|monde de noé|aventure fantastique|plume de phénix"),
    ("murder_party", "Murder party / enquête", "activite", r"murder|enquête|thriller|loup[- ]garou|wolf gang|alibi|mazarin et les gardiens|gardiens du secret|cluedo"),
    ("jeu_de_piste", "Jeu de piste / chasse au trésor", "activite", r"jeu de piste|chasse au trésor|city game|explore game"),
    ("quiz", "Quiz / blind test", "activite", r"quiz|blind[- ]test|le dernier qui rit|merci internet"),
    ("karaoke", "Karaoké", "activite", r"karaok|chante\s*!"),
    ("jeux_de_societe", "Jeux de société", "activite", r"jeux? de (?:société|figurines)|bar à jeux|café jeux|wargame|taverne|stratèges|jovial|loufoque|perpette"),
    ("jeu_video", "Jeu vidéo / réalité virtuelle", "activite", r"gaming|jeu vidéo|réalité virtuelle|\bvr\b|playin|press start"),
    ("mini_golf", "Mini-golf", "activite", r"mini[- ]?golf|mad golf"),
    ("jeu_actif", "Jeu actif (salle, palets, glisse)", "activite", r"active room|action game|pucks|shuffled|glisse|a tour de bras|lancer de hache|laser[- ]?game|bowling|billard|fléchettes|baby[- ]?foot|trampoline"),
    ("defouloir", "Défouloir / rage room", "activite", r"casse tout|rage room|tout brûler"),
    ("sport", "Sport / plein effort", "activite", r"\bquad|segway|à vélo|location de vélo|bike|pilates|\bsport|escalade|trampoline|karting|randonnée|wave in paris|\bsurf"),
    # Spectacles
    ("stand_up", "Stand-up / comedy club", "activite", r"comedy|stand[- ]?up|humour|humoriste|one[- ](?:wo)?man"),
    ("theatre", "Pièce de théâtre", "activite", r"théâtre|\bpièce\b"),
    ("comedie", "Comédie", "activite", r"comédie|la claque|dîner de famille|\brire\b"),
    ("comedie_musicale", "Comédie musicale", "activite", r"musical|roi soleil|fantôme de l'opéra"),
    ("magie", "Magie / illusion", "activite", r"magi(?:e|que|cien)|illusion|paradox|lupin"),
    ("cabaret", "Cabaret / revue", "activite", r"cabaret|(?<!machine du )moulin rouge|paradis latin|crazy horse|lido|burlesque|revue"),
    ("drag", "Drag", "activite", r"\bdrag\b|madame arthur"),
    # Said in the title only: "Sexe" (a stand-up), "Strip" (a play) or "Libertino" (a restaurant) are not.
    ("coquin", "Coquin / effeuillage", "activite", r"[ée]roti|burlesque|effeuill|strip[- ]?(?:tease|club|poker|&)|strips back|crazy horse|pole[- ]?dance|pin[- ]?ups?\b|lingerie|sexy|spicy|naughty|coquin|libertin(?!o)"),
    ("cirque", "Cirque", "activite", r"cirque|acrobat"),
    ("danse", "Danse / soirée dansante", "activite", r"\bdanse|dance|\bbal\b|salsa|tango|swing|latino|baile"),
    # Musique
    ("classique", "Musique classique", "activite", r"candlelight|vivaldi|mozart|requiem|beethoven|chopin|\bravel\b|symphoni|concerto|adagio|orchestre|philharmoni|opéra(?!tion)|choir|chœur|choeur|salle gaveau|récital"),
    ("jazz", "Jazz", "activite", r"\bjazz"),
    ("electro", "Électro / DJ / clubbing", "activite", r"\bdj\b|techno|tech no|(?<!murder )party|clubbing|\blive\)|club\b.*\bpresents?|open[- ]air|clubbing|boat party|afro(?:beat|love| sunset)|soirée afro|amapiano|groove"),
    ("concert_live", "Concert live", "activite", r"concert|en live|\blive\b|dream tour|accor arena|zénith|popfest"),
    # Culture
    ("art", "Art / peinture", "activite", r"\barts?\b|peinture|picasso|monet|orsay|orangerie|louvre|dalí|warhol|banksy|rodin|bourdelle|zadkine|maillol|jacquemart|cézanne|galerie\b|pompidou|bourse de commerce|vernissage"),
    ("photo", "Photographie", "activite", r"photo"),
    ("mode_design", "Mode / design", "activite", r"mode\b|haute couture|design|défilé|galliera|joailli"),
    ("histoire", "Histoire / patrimoine", "activite", r"histoire|historique|napoléon|médiéval|templiers|occupation|patrimoine|panthéon|conciergerie|sainte-chapelle|crypte|arc de triomphe|invalides|château|basilique|cathédrale|notre-dame|église|chapelle|carnavalet|hôtel de (?:la marine|lauzun)|versailles|bastille|père[- ]lachaise|cimetière|archéolog|galerie dorée"),
    ("sciences", "Sciences", "activite", r"science|évolution|muséum|spatial|cité de l'économie|musée de l'homme"),
    ("immersif", "Expérience immersive", "activite", r"immersi|atelier des lumières|aura invalides|friends experience|drone|ballet of lights|cité immersive|grand hôtel des rêves|color room"),
    ("cinema", "Cinéma", "activite", r"cinéma|projection|screening|cinémathèque|\bciné\b"),
    ("lecture", "Lecture / conférence", "activite", r"conférence|lecture|littéraire|poésie|poetry|slam|débat|écriture|librair"),
    ("visite_guidee", "Visite guidée / balade", "activite", r"visite|balade|(?:free|bike|food) tour|walk|promenade|excursion|petit train"),
    ("animaux", "Animaux", "activite", r"aquarium|zoo|ménagerie|bestiaire|cinéaqua|animal en ville|maison de l.animal"),
    # Ateliers
    ("ceramique", "Céramique / poterie", "activite", r"céramique|poterie|potier|faïence|modelage|argile|tournage"),
    ("peinture_dessin", "Peinture / dessin", "activite", r"peinture|peign|dessin|croquis|aquarelle|acrylique|calligraphie|illustration|paint"),
    ("cuisine", "Cuisine / pâtisserie", "activite", r"cuisine|pâtisserie|viennoiserie|macaron|madeleine|mochi|ramen|mozzarella|fromage|chocolat|dîner italien|menu 3 plats"),
    ("mixologie", "Cocktails", "activite", r"cocktail|gin\b|mixolog|distillation"),
    ("vin", "Vin / œnologie", "activite", r"\bvins?\b|œnolog|oenolog|wine|vignoble|vendanges|whisky"),
    ("artisanat", "Artisanat (cuir, bijou, textile…)", "activite", r"cuir|couteau|chevalière|bijou|laiton|métal|soudure|couture|cousez|tricot|crochet|broderie|tufting|vannerie|kumihimo|tressage|sérigraphie|gravure|gravez|kintsugi|mosaïque|béret|perles|lampe|sceaux|cyanotype|tampon|tatou|tattoo"),
    ("floral", "Fleurs / végétal", "activite", r"fleur|floral|bouquet|terrarium|kokedama|botanique|plantes|herbier|jardinerie"),
    ("parfum_bougie", "Parfum / bougie", "activite", r"parfum|bougie|fragrance|fragonard"),
    ("shooting", "Shooting photo", "activite", r"shooting|séance photo|studio pro"),
    # Gastronomie
    ("gastronomique", "Table gastronomique", "activite", r"ducasse|alléno|ledoyen|gastronomique|étoilé|menu d'exception|fauchon"),
    ("street_food", "Street food / marché", "activite", r"street food|food tour|marché|market|sausage|handroll|pizza|salted"),
    ("degustation", "Dégustation", "activite", r"dégustation|tasting|pairing|planche"),
    ("brunch_gouter", "Brunch / goûter / thé", "activite", r"brunch|goûter|petit[- ]déjeuner|\btea\b|five o'clock|coffee"),
    # Bien-être
    ("massage", "Massage", "activite", r"massage|tui na"),
    ("spa", "Spa / hammam", "activite", r"\bspa\b|hammam|sauna|bassin|beer spa"),
    ("flottaison", "Flottaison", "activite", r"flottaison|isolation sensorielle"),
    ("relaxation", "Yoga / méditation", "activite", r"yoga|méditation|relaxation|sophrologie"),
    ("baignade", "Baignade / piscine", "activite", r"piscine|baignade|natation|aquagym|jacuzzi|bains? nordiques?|maillot de bain"),
    # Cadre
    ("sur_l_eau", "Sur l'eau", "cadre", r"croisière|péniche|bateau|barque|seine|canal|\briver\b|boat|cruise|akwa|\bflots?\b"),
    ("vue", "Vue panoramique", "cadre", r"rooftop|accès au toit|panoramique|ballon de paris|tour eiffel|\bt7\b|vue spectaculaire"),
    ("souterrain", "Souterrain", "cadre", r"souterrain|catacombe|crypte|métro de paris"),
    ("cache", "Lieu secret / speakeasy", "cadre", r"speak ?easy|secret|caché|little red door|moonshiner|candelaria|maison close|club des haschischins|mask|cupidon"),
    ("plein_air", "Plein air", "cadre", r"jardin|parc\b|square|serre|open[- ]air|plein air|forêt|\blac\b|fête des|kiosque|butte|carnaval|hippodrome"),
    ("chic", "Chic / palace", "cadre", r"ritz|hemingway|\*{4,5}|ducasse|alléno|baccarat|opéra garnier|fauchon"),
    ("eglise", "Église / lieu sacré", "cadre", r"église|eglise|chapelle|saint-sulpice|notre-dame|cathédrale|pagode|temples? hindou"),
    ("chandelles", "Aux chandelles", "cadre", r"candlelight|aux chandelles|bougies"),
    ("dans_le_noir", "Dans le noir", "cadre", r"dans le noir"),
    ("hauteur", "En hauteur (vide, nacelle)", "cadre", r"montgolfi|ballon de paris|escalade|accrobranche|tyrolienne|grande roue|chute libre|parachut|via ferrata"),
    ("grande_salle", "Grande salle / foule", "cadre", r"accor arena|z[ée]nith|stade de france|défense arena|parc des princes|bercy arena"),
    # Moment
    ("nocturne", "Nocturne / soirée", "moment", r"nocturne|nuit|night|soirée|sunset|midnight|halloween|apéro|happy hour"),
    ("diner", "Dîner", "moment", r"dîner|diner|déjeuner|repas"),
    ("en_duo", "Pensé pour deux", "moment", r"duo|à deux|couple|privati|privé|private"),
    ("frisson", "Frisson (fantômes, crime…)", "moment", r"fantôme|ghost|mystère|crime|obscur|horreur|\bhell\b|manoir|catacombe|halloween|loup[- ]garou|étrange|sherlock|assassin|haschisch|prison"),
]

TAGS = {key: {"label": label, "facet": facet} for key, label, facet, _ in _TAG_RULES}
# Lowercase patterns on lowercased text: three times faster than IGNORECASE.
_TAG_PATTERNS = [(key, re.compile(pattern)) for key, _, _, pattern in _TAG_RULES]

# Tags implied by a category, for activities whose title says little ("Dipsy", "Le 1802").
_FROM_CATEGORY = {
    "humour": "stand_up",
    "cabaret": "cabaret",
    "croisiere": "sur_l_eau",
    "nature": "plein_air",
    "bien_etre": "spa",
    "cinema": "cinema",
    "conference": "lecture",
    "visite": "visite_guidee",
    "nuit": "nocturne",
}

# Vibes asked in the questionnaire: label, the client's wording, and what brings each one.
VIBES = {
    "bouger": {
        "label": "Bouger",
        "question": "Bouger, se dépenser un peu",
        "tags": {"sport", "jeu_actif", "defouloir", "mini_golf", "danse"},
        "categories": {"sensations"},
    },
    "defi": {
        "label": "Relever un défi",
        "question": "Relever un défi ensemble, réfléchir, gagner",
        "tags": {"escape_game", "murder_party", "jeu_de_piste", "quiz", "mini_golf", "jeu_actif", "jeux_de_societe", "jeu_video"},
        "categories": {"jeux"},
    },
    "rire": {
        "label": "Rire",
        "question": "Rire aux éclats",
        "tags": {"stand_up", "comedie", "drag", "karaoke", "quiz"},
        "categories": {"humour"},
    },
    "creer": {
        "label": "Créer",
        "question": "Créer quelque chose de nos mains",
        "tags": {"ceramique", "peinture_dessin", "cuisine", "mixologie", "artisanat", "floral", "parfum_bougie"},
        "categories": {"atelier"},
    },
    "savourer": {
        "label": "Savourer",
        "question": "Se régaler, découvrir des saveurs",
        "tags": {"gastronomique", "street_food", "degustation", "vin", "mixologie", "brunch_gouter", "diner", "cuisine"},
        "categories": {"gastronomie", "restaurant"},
    },
    "detente": {
        "label": "Se détendre",
        "question": "Se détendre, prendre soin de nous",
        "tags": {"massage", "spa", "flottaison", "relaxation", "baignade"},
        "categories": {"bien_etre"},
    },
    "emerveiller": {
        "label": "S'émerveiller",
        "question": "En prendre plein les yeux",
        "tags": {"immersif", "vue", "chandelles", "magie", "cirque", "cabaret", "comedie_musicale", "animaux"},
        "categories": {"spectacle", "cabaret"},
    },
    "musique": {
        "label": "Vibrer en musique",
        "question": "Vibrer sur de la musique live",
        "tags": {"classique", "jazz", "concert_live", "electro", "comedie_musicale"},
        "categories": {"concert"},
    },
    "fete": {
        "label": "Faire la fête",
        "question": "Faire la fête, danser jusqu'au bout de la nuit",
        "tags": {"electro", "danse", "karaoke", "drag"},
        "categories": {"nuit"},
    },
    "cultiver": {
        "label": "Se cultiver",
        "question": "Apprendre, découvrir de l'art ou de l'histoire",
        "tags": {"art", "photo", "mode_design", "histoire", "sciences", "lecture", "visite_guidee", "cinema", "theatre"},
        "categories": {"musee", "expo", "conference", "visite", "theatre"},
    },
    "flaner": {
        "label": "Prendre l'air",
        "question": "Flâner dehors, au fil de l'eau ou dans la nature",
        "tags": {"plein_air", "sur_l_eau", "visite_guidee"},
        "categories": {"nature", "croisiere"},
    },
    "frisson": {
        "label": "Frissonner",
        "question": "Frissonner un peu (mystères, fantômes, sous terre)",
        "tags": {"frisson", "souterrain", "murder_party"},
        "categories": set(),
    },
    "insolite": {
        "label": "L'insolite",
        "question": "Sortir des sentiers battus, un lieu qu'on n'imagine pas",
        "tags": {"cache", "souterrain", "dans_le_noir", "defouloir", "flottaison", "immersif"},
        "categories": {"lieu_insolite"},
    },
    "coquin": {
        "label": "Pimenter",
        "question": "Un moment un peu coquin, rien que nous deux",
        "tags": {"coquin"},
        "categories": set(),
    },
    "romantique": {
        "label": "Romantique",
        "question": "Un moment romantique, rien que nous deux",
        "tags": {"chandelles", "en_duo", "vue", "chic", "gastronomique", "massage", "shooting"},
        "categories": {"bien_etre"},
    },
}


def tag(activity: dict[str, Any]) -> list[str]:
    """Tags of an activity, in taxonomy order, from its title, venue name and categories."""
    venue = activity.get("venue") or {}
    return list(_tags(activity.get("title") or "", venue.get("name") or "", tuple(activity.get("categories") or ())))


@lru_cache(maxsize=100_000)
def _tags(title: str, venue: str, categories: tuple[str, ...]) -> tuple[str, ...]:
    # Cached: the planner, the originality and the admin ask for the same activities in turn.
    text = f"{title} {venue}".lower()
    found = {key for key, pattern in _TAG_PATTERNS if pattern.search(text)}
    found |= {_FROM_CATEGORY[c] for c in categories if c in _FROM_CATEGORY}
    return tuple(key for key in TAGS if key in found)


def vibes(tags: list[str], categories: list[str]) -> list[str]:
    """Vibes an activity answers, in questionnaire order."""
    tags_set, categories_set = set(tags), set(categories)
    return [key for key, vibe in VIBES.items() if vibe["tags"] & tags_set or vibe["categories"] & categories_set]


def describe(activity: dict[str, Any]) -> dict[str, list[str]]:
    tags = tag(activity)
    return {"tags": tags, "vibes": vibes(tags, activity.get("categories") or [])}


def main() -> None:
    """Report tag and vibe coverage of the local base, to tune the rules."""
    from surprise.local_store import open_store

    parser = argparse.ArgumentParser(description="Couverture des tags et vibes sur la base locale")
    parser.add_argument("--untagged", action="store_true", help="lister les activités sans vibe")
    args = parser.parse_args()
    with open_store() as store:
        items = [item for item in store.list_for_moderation() if item["status"] != "filtered"]
    tag_counts: Counter[str] = Counter()
    vibe_counts: Counter[str] = Counter()
    without = []
    for item in items:
        found = describe(item["activity"])
        tag_counts.update(found["tags"])
        vibe_counts.update(found["vibes"])
        if not found["vibes"]:
            without.append(item)
    print(f"{len(items)} activités, {len(items) - len(without)} avec au moins une vibe\n\nVibes :")
    for key, vibe in VIBES.items():
        print(f"  {vibe['label']:20} {vibe_counts[key]}")
    print("\nTags :")
    for key, info in TAGS.items():
        print(f"  {FACETS[info['facet']]:9} {info['label']:36} {tag_counts[key]}")
    if args.untagged:
        print("\nSans vibe :")
        for item in without:
            print(f"  {item['source_id']:26} {item['activity']['title'][:90]}")


# The categories each vibe relies on must exist.
assert all(vibe["categories"] <= CATEGORIES.keys() for vibe in VIBES.values())
assert all(vibe["tags"] <= TAGS.keys() for vibe in VIBES.values())
assert _FROM_CATEGORY.keys() <= CATEGORIES.keys() and set(_FROM_CATEGORY.values()) <= TAGS.keys()

if __name__ == "__main__":
    main()
