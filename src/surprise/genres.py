"""Music genres: what a concert or a club night plays, so that a couple's evening keeps to their music.

The profile asks "Sur quelles musiques vibrez-vous ?" (surprise.quiz); its genres filter the musical
outings (surprise.parcours): a concert whose genre the couple did not tick is left out, one whose
genre is unknown stays. Classical concerts are never left out: one may love a Candlelight for an
occasion without listening to it every day.

The genre comes from the source when it says it (concerts.paris), else from the texts: the title and
venue first, then the source's text and the descriptions.
"""

import re
from typing import Any

# key, label, pattern on lowercased text.
_RULES = [
    ("rock", "Pop, rock & indé", r"\brock\b(?! ?(?:4|à|acrobatique))|\bpop\b(?![- ]up)|\bindie\b|\bindé\b|\bfolk\b|\bpunk|grunge|shoegaze|britpop|new wave|post[- ]rock"),
    ("chanson", "Chanson & variété", r"chanson française|chansons? fran|variété|chanteu(?:r|se) français|french pop|\bpop française"),
    ("jazz", "Jazz & blues", r"\bjazz|\bblues|\bswing\b|bebop|be-bop|manouche|big band"),
    ("soul", "Soul, funk & R&B", r"\bsoul\b|\bfunk|\br&b\b|\brnb\b|gospel|\bdisco\b|motown|neo[- ]soul"),
    ("rap", "Rap & hip-hop", r"\brap\b|\brappeu|hip[- ]?hop|\btrap\b|\bdrill\b|\bgrime\b"),
    ("electro", "Électro & techno", r"électro|electro|techno|\bhouse\b|\bdj\b|dj set|clubbing|\btrance\b|drum ?(?:&|and|n'?) ?bass|\bdnb\b|\brave\b|minimal|\bedm\b"),
    ("latino", "Latino, afro & reggae", r"\blatin|salsa|bachata|cumbia|reggaeton|kizomba|samba|bossa|tango|\bafro|amapiano|\bzouk|kompa|dancehall|reggae|musiques? du monde|world music|flamenco|forró|pagode|baile funk"),
    ("metal", "Metal & hard rock", r"\bm[eé]tal\b|hard rock|hardcore|heavy|thrash|black metal|death metal|\bdoom\b"),
    ("classique", "Classique & opéra", r"classique|candlelight|vivaldi|mozart|beethoven|chopin|\bbach\b|debussy|\bravel\b|orchestre|philharmoni|symphoni|concerto|opéra(?!tion)|récital|quatuor|lyrique|baroque|chœur|choeur|requiem"),
]

GENRES = {key: label for key, label, _ in _RULES}
_PATTERNS = [(key, re.compile(pattern)) for key, _, pattern in _RULES]

# concerts.paris says the genre of each event.
_SOURCE_GENRES = {
    "pop-rock-inde": "rock",
    "variete-francaise": "chanson",
    "jazz": "jazz",
    "rnb-soul-funk-gospel-reggae": "soul",
    "rap": "rap",
    "electro": "electro",
    "musiques-du-monde": "latino",
    "hard-rock-metal": "metal",
    "musique-classique": "classique",
    "opera-lyrique": "classique",
}

# Always allowed, whatever the couple ticked: a Candlelight is for an occasion, not for every day.
ALWAYS = {"classique"}


def found(text: str) -> list[str]:
    """Genres named in a text, in list order."""
    text = text.lower()
    return [key for key, pattern in _PATTERNS if pattern.search(text)]


def genres(item: dict[str, Any]) -> list[str]:
    """What the activity plays: the source's genre, else those of its title and venue, else of its texts."""
    if genre := _SOURCE_GENRES.get(item.get("source_genre") or ""):
        return [genre]
    activity = item["activity"]
    venue = activity.get("venue") or {}
    named = found(f"{activity.get('title') or ''} {venue.get('name') or ''}")
    if named:
        return named
    enrichment = item.get("enrichment") or {}
    return found(" ".join(filter(None, [item.get("lead_text"), enrichment.get("site_excerpt"), enrichment.get("description")])))


def off_key(item_genres: list[str], categories: set[str], liked: set[str]) -> bool:
    """A concert or a club night playing none of the genres the couple likes (none said: all are fine).

    Its music unknown, it stays proposed: nothing says it is not theirs.
    """
    if not liked or not item_genres or "concert" not in categories and "nuit" not in categories:
        return False
    return not (liked | ALWAYS) & set(item_genres)
