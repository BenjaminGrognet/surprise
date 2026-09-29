"""Keywords: the words that tell an activity's atmosphere, found in all its texts.

Tags (surprise.tags) say what an activity is, from its title and venue. Keywords
read further, in the source's text, the official site's excerpt and Claude's
description, to catch what makes a couple choose it: "intimiste", "vue sur la
Seine", "cave voûtée", "fait main", "en duo". They are grouped in facets and
stored in the enrichment (keywords), so they can be searched and shown.

    uv run python -m surprise.keywords          # compute and store them for every activity
"""

import argparse
import json
import re
from collections import Counter
from typing import Any

FACETS = {
    "ambiance": "Ambiance",
    "cadre": "Cadre",
    "experience": "Expérience",
    "moment": "Moment",
    "cuisine": "Cuisine",
}

# keyword, facet, pattern on the texts.
_RULES = [
    # Ambiance
    ("intimiste", "ambiance", r"intimist|intime\b|confidentiel|petit comité|quelques places|jauge (?:réduite|limitée)"),
    ("cosy", "ambiance", r"\bcosy\b|cocooning|chaleureu|feutré|douillet|coin du feu|cheminée"),
    ("romantique", "ambiance", r"romanti|en amoureux|amoureux|saint[- ]valentin|love\b|tête[- ]à[- ]tête"),
    ("festif", "ambiance", r"festi(?:f|ve)|ambiance de folie|déjanté|endiablé|dancefloor|fiesta"),
    ("chic", "ambiance", r"\bchic\b|élégan|raffiné|luxe|luxueu|palace|prestig|haut de gamme|étoilé"),
    ("bohème", "ambiance", r"bohème|boho|arty|bric[- ]à[- ]brac|guinguette"),
    ("rétro / vintage", "ambiance", r"vintage|rétro|années (?:20|30|50|60|70|80)|art déco|belle époque|d'antan|old school"),
    ("secret", "ambiance", r"(?:lieu|bar|adresse|passage|jardin|salle|club|porte|cave|cour)s? secr[eè]te?s?|bien gardé|caché|dissimulé|speak ?easy|mot de passe|porte dérobée|méconnu|insoupçonné"),
    ("insolite", "ambiance", r"insolite|atypique|étonnant|surprenant|décalé|hors du commun|inattendu|jamais vu|unique en son genre|original"),
    ("convivial", "ambiance", r"convivia|bonne franquette|comme à la maison|familial|partage"),
    ("mystérieux", "ambiance", r"mystère|mystéri|énigm|occulte|fantôme|hanté|légende"),
    ("zen", "ambiance", r"\bzen\b|apaisant|sérénité|lâcher[- ]prise|détente absolue|bien[- ]être"),
    # Cadre
    ("vue panoramique", "cadre", r"vue (?:panoramique|imprenable|à couper le souffle|sur (?:tout )?paris|sur la tour eiffel|sur la seine|sur les toits)|rooftop|toit[- ]terrasse|au sommet"),
    ("terrasse", "cadre", r"terrasse|en plein air|à ciel ouvert|patio|cour intérieure"),
    ("jardin", "cadre", r"jardin|verdure|végétalis|serre\b|potager|arbres"),
    ("au bord de l'eau", "cadre", r"bord de (?:l'eau|seine|canal)|quais?\b|péniche|bateau|au fil de l'eau|canal saint-martin|bassin de la villette"),
    ("cave voûtée", "cadre", r"cave voûtée|voûtes?\b|sous-sol|souterrain|caveau|crypte|catacombe"),
    ("lieu historique", "cadre", r"historique|patrimoine|classé monument|xviie|xviiie|xixe|siècle|hôtel particulier|château"),
    ("atelier d'artisan", "cadre", r"atelier d'artisan|dans son atelier|dans l'atelier de|manufacture"),
    ("hôtel", "cadre", r"\bhôtel\b"),
    ("aux chandelles", "cadre", r"chandelle|bougies|candlelight|à la lueur"),
    ("dans le noir", "cadre", r"dans le noir|obscurité totale|les yeux bandés"),
    # Expérience
    ("immersif", "experience", r"immersi|réalité virtuelle|\bvr\b|360°|projection monumentale"),
    ("interactif", "experience", r"interacti|participati|vous êtes acteurs?|jouez un rôle|à vous de jouer"),
    ("fait main", "experience", r"fait main|de vos mains|repartez avec|créez votre|fabriquez|confectionnez|façonnez"),
    ("dégustation", "experience", r"dégust|tasting|accord mets|accords? (?:mets[- ]vins|parfaits)"),
    ("en duo", "experience", r"en duo|à deux\b|pour deux|pour 2\b|en couple|formule duo|pour les couples"),
    ("privatisé", "experience", r"privatis|privatif|rien que pour vous|en exclusivité|sur mesure"),
    ("live", "experience", r"\blive\b|en direct|musiciens?|concert|dj set|chanteu"),
    ("sensations", "experience", r"sensations? fortes?|adrénaline|vertige|frisson|à couper le souffle"),
    ("apprendre", "experience", r"initiation|apprenez|découvrez les (?:secrets|bases|techniques)|cours\b|masterclass|guidé par"),
    ("jeu", "experience", r"\bjeux?\b|défi|énigmes?|chasse au trésor|équipe"),
    ("spectacle", "experience", r"spectacle|représentation|sur scène|mise en scène|comédien"),
    # Moment
    ("coucher de soleil", "moment", r"coucher (?:de|du) soleil|sunset|golden hour"),
    ("nocturne", "moment", r"nocturne|de nuit|by night|jusqu'à l'aube|jusqu'au bout de la nuit|after\b|minuit"),
    ("apéro", "moment", r"apéro|apéritif|happy hour|afterwork|planche"),
    ("dîner", "moment", r"dîner|diner\b|souper"),
    ("brunch", "moment", r"brunch|petit[- ]déjeuner|goûter"),
    ("éphémère", "moment", r"éphémère|pop[- ]up|pour quelques (?:jours|semaines)|édition limitée|exceptionnel(?:le)?ment|une seule date|dernière"),
    # Cuisine
    ("bistronomie", "cuisine", r"bistronom|bistrot"),
    ("gastronomique", "cuisine", r"gastronomi|étoilé|michelin|chef (?:étoilé|cuisinier)|menu dégustation"),
    ("cuisine du monde", "cuisine", r"japonais|coréen|thaï|libanais|mexicain|péruvien|italien|indien|éthiopien|créole|géorgien|vietnamien|chinois|marocain|grec|asian|caribbean|lebanese|mexican|peruvian|indian|japanese|korean|thai"),
    ("végétarien", "cuisine", r"végé|vegan|végétal|vegetarian"),
    ("vins nature", "cuisine", r"vins? nat(?:ure)?\b|biodynami|vigneron"),
    ("cocktails", "cuisine", r"cocktail|mixolog|signature drinks"),
    ("fruits de mer", "cuisine", r"fruits de mer|huîtres|poisson|seafood"),
]

KEYWORDS = {key: {"facet": facet} for key, facet, _ in _RULES}
# Lowercase patterns on lowercased text: three times faster than IGNORECASE.
_PATTERNS = [(key, re.compile(pattern)) for key, _, pattern in _RULES]


def texts(item: dict[str, Any]) -> str:
    """Everything written about an activity: title, venue, source text, site excerpt, description."""
    activity = item["activity"]
    enrichment = item.get("enrichment") or {}
    venue = activity.get("venue") or {}
    return " ".join(
        filter(None, [activity.get("title"), venue.get("name"), item.get("lead_text"), enrichment.get("site_excerpt"), enrichment.get("description")])
    )


def extract(text: str) -> list[str]:
    """Keywords found in a text, in lexicon order."""
    text = text.lower()
    return [key for key, pattern in _PATTERNS if pattern.search(text)]


def main() -> None:
    from surprise.local_store import open_store

    parser = argparse.ArgumentParser(description="Mots-clés des activités, stockés dans l'enrichissement")
    parser.add_argument("--dry-run", action="store_true", help="afficher la couverture sans enregistrer")
    args = parser.parse_args()
    with open_store() as store:
        items = [item for item in store.list_for_moderation() if item["status"] != "filtered"]
        found = {(item["source_id"], item["external_id"]): extract(texts(item)) for item in items}
        if not args.dry_run:
            store.save_keywords({key: json.dumps(words, ensure_ascii=False) for key, words in found.items()})
    counts = Counter(word for words in found.values() for word in words)
    print(f"{len(items)} activités, {sum(bool(w) for w in found.values())} avec au moins un mot-clé")
    for key, info in KEYWORDS.items():
        print(f"  {FACETS[info['facet']]:11} {key:22} {counts[key]}")


if __name__ == "__main__":
    main()
