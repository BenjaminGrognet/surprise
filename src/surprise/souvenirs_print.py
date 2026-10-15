"""Souvenirs printed after an evening: a plaque « notre morceau », the night's sky over Paris and a heart mug (a
magnet and a candle too, drawn but made outside the European Union only), composed from the evening (names, day,
steps, photos) at the size the printer asks, then put in a Printify shop as draft products, never
published nor ordered: Printify draws their mockups, to see what a couple would get.

Made in the European Union only (no customs nor three weeks' wait for a couple in Paris): each souvenir's product,
print provider and variant are fixed, chosen from the catalogue; one without them is looked for by words of its
title, among the providers of the Union. The print area's size is read from the catalogue (in pixels, 300 dpi).

    uv run --env-file .env python -m surprise.souvenirs_print apercu                 # the PNGs in data/souvenirs/
    uv run --env-file .env python -m surprise.souvenirs_print catalogue acrylic      # products, their providers
    uv run --env-file .env python -m surprise.souvenirs_print brouillon --photos <dossier>   # drafts in the shop

PRINTIFY_API_TOKEN (Printify, My profile > Connections) in .env; PRINTIFY_SHOP_ID if the account has several shops.
"""

import argparse
import base64
import functools
import io
import math
import os
import sys
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx
import segno
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

PARIS = ZoneInfo("Europe/Paris")
PARIS_LAT, PARIS_LON = 48.8566, 2.3522
FONTS = Path(__file__).with_name("fonts")
# The Secret Date monogram, gold on the app's velvet (app/src/components/logo-secretdate.tsx).
LOGO = Path(__file__).resolve().parents[2] / "app" / "assets" / "images" / "logo-secretdate.png"
OUT = Path(__file__).resolve().parents[2] / "data" / "souvenirs"
API = "https://api.printify.com/v1"
EUROPE = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU",
          "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"}  # the Union: no customs for a parcel to Paris
LARGEST = 6000  # px: a larger print area is filled by Printify enlarging the design
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
          "décembre"]

INK = (27, 26, 23)
PAPER = (244, 239, 228)
WHITE = (251, 248, 241)
NIGHT_BLUE = (14, 26, 43)
STARLIGHT = (233, 224, 201)
WINE = (124, 47, 58)


@dataclass(frozen=True)
class Palette:
    """A souvenir's paper and inks: the paper, what lives (the stroke), its hairline, what is precious (the monogram,
    the steps), the gold's hairline, the text and the asides."""

    ground: tuple[int, int, int]
    accent: tuple[int, int, int]
    dim: tuple[int, int, int]
    gold: tuple[int, int, int]
    hair: tuple[int, int, int]
    text: tuple[int, int, int]
    soft: tuple[int, int, int]


# The app's Midnight Emerald set on paper: its emerald deepened and its gold darkened to hold on white.
PAPER_INKS = dict(accent=(22, 92, 66), dim=(206, 212, 204), gold=(152, 118, 60), hair=(218, 206, 180),
                  text=(30, 33, 30), soft=(118, 122, 114))
PALETTES = {
    "casse": Palette(ground=(246, 242, 233), **PAPER_INKS),  # an off-white, the default
    "blanc": Palette(ground=(255, 255, 255), **PAPER_INKS),
}
GROUNDS = {"casse": "Blanc cassé", "blanc": "Blanc"}  # their names
DEFAULT_GROUND = "casse"
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


@dataclass(frozen=True)
class Stop:
    at: time
    name: str
    lat: float
    lon: float


@dataclass
class Evening:
    names: str
    day: date
    stops: list[Stop]
    photos: list[Image.Image] = field(default_factory=list)
    link: str | None = None  # the evening's page in the Livre, for the plaque's QR code
    title: str = "Notre soirée"  # its secret name (soirees_choisies.secret_title, surprise.parcours.secret_title)
    clues: list[str] = field(default_factory=list)  # what the passager was told before (app/src/lib/clues.ts)
    palette: str = DEFAULT_GROUND  # its paper, among PALETTES

    @property
    def short_day(self) -> str:
        return f"{self.day:%d.%m.%y}"

    @property
    def long_day(self) -> str:
        return f"{self.day.day}{'er' if self.day.day == 1 else ''} {MONTHS[self.day.month - 1]} {self.day.year}"

    @property
    def weekday_day(self) -> str:
        return f"{DAYS[self.day.weekday()].capitalize()} {self.long_day}"


# The example of the proposal page: three steps between the Marais, the canal and Belleville.
EXAMPLE = Evening(
    names="Camille & Léo",
    day=date(2026, 10, 14),
    stops=[
        Stop(time(19, 30), "Atelier céramique", 48.8575, 2.3600),
        Stop(time(21, 0), "Dîner au bord du canal", 48.8722, 2.3655),
        Stop(time(23, 15), "Le toit de Belleville", 48.8712, 2.3855),
    ],
    title="Le Serment du Canal Saint-Martin",
    clues=[
        "Portez une touche de doré : ce soir, on s'habille un peu.",
        "Vous repartirez avec quelque chose fait de vos mains.",
        "Vos papilles sont conviées.",
        "Tout se joue rive droite.",
    ],
)
# Its photos: CC0, from Wikimedia Commons (data/souvenirs/exemple/, not versioned; see the README).
EXAMPLE_PHOTOS = OUT / "exemple"


# --- photos ---------------------------------------------------------------------------------------------------------

def load_photo(path: Path) -> Image.Image:
    """A photo upright (its EXIF orientation applied), in RGB."""
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def sharpness(photo: Image.Image) -> float:
    """How sharp a photo is: the variance of its edges, read on a copy 1000 px wide (a night's shake lowers it)."""
    grey = photo.convert("L")
    grey.thumbnail((1000, 1000))
    return ImageStat.Stat(grey.filter(ImageFilter.FIND_EDGES)).var[0]


def print_quality(photo: tuple[int, int], area: tuple[int, int]) -> str:
    """« parfaite », « correcte » or « trop juste »: the photo filling an area drawn at 300 dpi, enlarged how much."""
    enlarged = max(area[0] / photo[0], area[1] / photo[1])
    return "parfaite" if enlarged <= 1 else "correcte" if enlarged <= 2 else "trop juste"


def demo_photo(seed: int, size: int = 1600) -> Image.Image:
    """A night's bokeh and two silhouettes, for the example without photos (as on the proposal page)."""
    import random

    rnd = random.Random(seed)
    palettes = [((29, 18, 8), (255, 182, 92)), ((7, 26, 36), (95, 227, 230)), ((22, 11, 34), (255, 111, 168))]
    ground, light = palettes[seed % len(palettes)]
    image = Image.new("RGB", (size, size), ground)
    glow = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(glow)
    for _ in range(50):
        x, y, r = rnd.uniform(0, size), rnd.uniform(size * 0.25, size), rnd.uniform(size * 0.02, size * 0.09)
        shade = tuple(int(c * rnd.uniform(0.4, 1)) for c in light)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=shade)
    image = Image.blend(image, glow.filter(ImageFilter.GaussianBlur(size / 60)), 0.6)
    draw = ImageDraw.Draw(image)
    for x, k in ((0.4, 1.0), (0.61, 0.94)):
        cx, head = x * size, 0.09 * size * k
        draw.ellipse((cx - head, 0.6 * size * k - head, cx + head, 0.6 * size * k + head), fill=(5, 5, 5))
        draw.ellipse((cx - 0.2 * size * k, 0.74 * size, cx + 0.2 * size * k, 1.3 * size), fill=(5, 5, 5))
    return image


# --- drawing helpers ------------------------------------------------------------------------------------------------

def font(name: str, size: float) -> ImageFont.FreeTypeFont:
    files = {"display": "CormorantGaramond_500Medium.ttf", "italic": "CormorantGaramond_500Medium_Italic.ttf",
             "body": "Manrope_600SemiBold.ttf", "bold": "Manrope_700Bold.ttf"}
    return ImageFont.truetype(str(FONTS / files[name]), max(1, round(size)))


def fitted(draw: ImageDraw.ImageDraw, text: str, name: str, size: float, width: float) -> ImageFont.FreeTypeFont:
    """The face at `size`, smaller if the text would be wider than `width`."""
    face = font(name, size)
    while draw.textlength(text, font=face) > width and face.size > 6:
        face = font(name, face.size * 0.92)
    return face


def wrapped(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, width: float) -> list[str]:
    lines: list[str] = []
    for word in text.split(" "):  # a non-breaking space holds its words together
        if lines and draw.textlength(f"{lines[-1]} {word}", font=face) <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def centred(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, face: ImageFont.FreeTypeFont, fill) -> None:
    draw.text((x, y), text, font=face, fill=fill, anchor="ma")


def contain(design: Image.Image, size: tuple[int, int], ground) -> Image.Image:
    """The design at the printer's size, whole: scaled to fit, the rest filled with its ground."""
    canvas = Image.new("RGB", size, ground)
    fit = ImageOps.contain(design, size, Image.LANCZOS)
    canvas.paste(fit, ((size[0] - fit.width) // 2, (size[1] - fit.height) // 2))
    return canvas


def photo_or_demo(evening: Evening, index: int, size: int) -> Image.Image:
    return evening.photos[index % len(evening.photos)] if evening.photos else demo_photo(index, size)


# --- the souvenirs --------------------------------------------------------------------------------------------------

def magnet(evening: Evening, size: tuple[int, int]) -> Image.Image:
    """A polaroid: the best photo, the date in italics underneath."""
    side = 1800
    design = Image.new("RGB", (side, side), WHITE)
    margin, caption = round(side * 0.06), round(side * 0.16)
    area = (side - 2 * margin, side - margin - caption)
    design.paste(ImageOps.fit(photo_or_demo(evening, 0, side), area, Image.LANCZOS), (margin, margin))
    draw = ImageDraw.Draw(design)
    centred(draw, side / 2, side - caption + side * 0.035, f"{evening.names} · {evening.short_day}",
            fitted(draw, f"{evening.names} · {evening.short_day}", "italic", side * 0.07, area[0]), INK)
    return contain(design, size, WHITE)


def qr_image(link: str, side: int, c: Palette) -> Image.Image:
    buffer = io.BytesIO()
    segno.make(link, error="m").save(buffer, kind="png", scale=10, border=2, dark=c.text, light=c.ground)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB").resize((side, side), Image.NEAREST)


def plaque(evening: Evening, size: tuple[int, int]) -> Image.Image:
    """Le carton de la soirée, on paper: the Secret Date monogram, the evening's photo in an arch, its secret name, the
    day, the stroke of its steps and a QR code to its page in the Livre; much white around."""
    c = PALETTES[evening.palette]
    w, h = 2000, 3160
    design = Image.new("RGB", (w, h), c.ground)
    draw = ImageDraw.Draw(design)
    y = lockup(design, w / 2, h * 0.05, w * 0.1, "SECRET DATE", w * 0.017, c)
    pw, ph = round(w * 0.54), round(h * 0.33)
    left, top = round((w - pw) / 2), round(y + h * 0.04)
    photo = ImageOps.fit(photo_or_demo(evening, 0, w), (pw, ph), Image.LANCZOS, centering=(0.5, 0.4))
    design.paste(photo, (left, top), arch(pw, ph))
    gap = w * 0.016
    draw.arc((left - gap, top - gap, left + pw + gap, top + pw + gap), 180, 360, fill=c.hair, width=3)
    for x in (left - gap, left + pw + gap):
        draw.line((x, top + pw / 2, x, top + ph + gap), fill=c.hair, width=3)
    draw.line((left - gap, top + ph + gap, left + pw + gap, top + ph + gap), fill=c.hair, width=3)
    y = title_lines(draw, evening.title, w / 2, top + ph + h * 0.045, w * 0.78, w * 0.072, 2, c)
    centred(draw, w / 2, y + w * 0.012, evening.weekday_day, font("italic", w * 0.036), c.soft)
    trace(design, evening.stops, (w * 0.3, y + h * 0.075, w * 0.7, h * 0.85), font("body", w * 0.018),
          round(w * 0.0022), c)
    draw = ImageDraw.Draw(design)
    m, qr_side = round(w * 0.12), round(w * 0.09)
    qr_top = round(h * 0.895)
    design.paste(qr_image(evening_link(evening), qr_side, c), (w - m - qr_side, qr_top))
    spaced(draw, m, qr_top + qr_side / 2, evening.names.upper(), font("body", w * 0.017), c.text, "left")
    return contain(design, size, c.ground)


# Bright stars (J2000: right ascension in hours, declination in degrees, magnitude) and the lines of their figures.
STARS: dict[str, tuple[float, float, float]] = {
    "Dubhe": (11.062, 61.75, 1.8), "Merak": (11.031, 56.38, 2.4), "Phecda": (11.897, 53.69, 2.4),
    "Megrez": (12.257, 57.03, 3.3), "Alioth": (12.900, 55.96, 1.8), "Mizar": (13.399, 54.93, 2.2),
    "Alkaid": (13.792, 49.31, 1.9), "Polaris": (2.530, 89.26, 2.0), "Kochab": (14.845, 74.16, 2.1),
    "Pherkad": (15.345, 71.83, 3.0), "Caph": (0.153, 59.15, 2.3), "Schedar": (0.675, 56.54, 2.2),
    "GammaCas": (0.945, 60.72, 2.4), "Ruchbah": (1.430, 60.24, 2.7), "Segin": (1.907, 63.67, 3.4),
    "Deneb": (20.690, 45.28, 1.25), "Sadr": (20.370, 40.26, 2.2), "Gienah": (20.770, 33.97, 2.5),
    "DeltaCyg": (19.750, 45.13, 2.9), "Albireo": (19.512, 27.96, 3.1), "Vega": (18.616, 38.78, 0.0),
    "Sheliak": (18.835, 33.36, 3.5), "Sulafat": (18.982, 32.69, 3.3), "ZetaLyr": (18.746, 37.61, 4.3),
    "Altair": (19.846, 8.87, 0.8), "Tarazed": (19.771, 10.61, 2.7), "Alshain": (19.922, 6.41, 3.7),
    "Markab": (23.079, 15.21, 2.5), "Scheat": (23.063, 28.08, 2.4), "Algenib": (0.220, 15.18, 2.8),
    "Alpheratz": (0.140, 29.09, 2.1), "Mirach": (1.162, 35.62, 2.1), "Almach": (2.065, 42.33, 2.1),
    "Mirfak": (3.405, 49.86, 1.8), "Algol": (3.136, 40.96, 2.1), "Capella": (5.278, 46.00, 0.1),
    "Aldebaran": (4.599, 16.51, 0.85), "Pleiades": (3.783, 24.12, 1.6), "Arcturus": (14.261, 19.18, -0.05),
    "Betelgeuse": (5.919, 7.41, 0.5), "Rigel": (5.242, -8.20, 0.13), "Bellatrix": (5.419, 6.35, 1.6),
    "Alnitak": (5.679, -1.94, 1.8), "Alnilam": (5.603, -1.20, 1.7), "Mintaka": (5.533, -0.30, 2.2),
    "Saiph": (5.796, -9.67, 2.1), "Castor": (7.577, 31.89, 1.6), "Pollux": (7.755, 28.03, 1.15),
    "Fomalhaut": (22.961, -29.62, 1.2),
}
FIGURES = [
    ("Dubhe", "Merak"), ("Merak", "Phecda"), ("Phecda", "Megrez"), ("Megrez", "Dubhe"), ("Megrez", "Alioth"),
    ("Alioth", "Mizar"), ("Mizar", "Alkaid"), ("Polaris", "Kochab"), ("Kochab", "Pherkad"), ("Caph", "Schedar"),
    ("Schedar", "GammaCas"), ("GammaCas", "Ruchbah"), ("Ruchbah", "Segin"), ("Deneb", "Sadr"), ("Sadr", "Albireo"),
    ("DeltaCyg", "Sadr"), ("Sadr", "Gienah"), ("Vega", "ZetaLyr"), ("ZetaLyr", "Sheliak"), ("Sheliak", "Sulafat"),
    ("Sulafat", "ZetaLyr"), ("Tarazed", "Altair"), ("Altair", "Alshain"), ("Markab", "Scheat"),
    ("Scheat", "Alpheratz"), ("Alpheratz", "Algenib"), ("Algenib", "Markab"), ("Alpheratz", "Mirach"),
    ("Mirach", "Almach"), ("Mirfak", "Algol"), ("Betelgeuse", "Bellatrix"), ("Bellatrix", "Mintaka"),
    ("Mintaka", "Alnilam"), ("Alnilam", "Alnitak"), ("Alnitak", "Betelgeuse"), ("Alnitak", "Saiph"),
    ("Mintaka", "Rigel"), ("Castor", "Pollux"),
]


def sky_positions(moment: datetime, lat: float = PARIS_LAT, lon: float = PARIS_LON) -> dict[str, tuple[float, float, float]]:
    """Each star above the horizon at that moment: (altitude, azimuth from the north towards the east, in degrees,
    magnitude). Sidereal time from the Julian day; precession since 2000 left out (a fraction of a degree)."""
    jd = moment.astimezone(timezone.utc).timestamp() / 86400 + 2440587.5
    lst = (280.46061837 + 360.98564736629 * (jd - 2451545) + lon) % 360
    phi = math.radians(lat)
    seen = {}
    for name, (ra, dec, mag) in STARS.items():
        ha, de = math.radians(lst - ra * 15), math.radians(dec)
        alt = math.asin(math.sin(de) * math.sin(phi) + math.cos(de) * math.cos(phi) * math.cos(ha))
        if alt < 0:
            continue
        az = math.atan2(-math.cos(de) * math.sin(ha),
                        math.sin(de) * math.cos(phi) - math.cos(de) * math.sin(phi) * math.cos(ha))
        seen[name] = (math.degrees(alt), math.degrees(az) % 360, mag)
    return seen


def night_moment(evening: Evening) -> datetime:
    """The sky's moment: the last step's hour (after midnight, the day after), else 23:00, in Paris."""
    at = evening.stops[-1].at if evening.stops else time(23, 0)
    day = evening.day.toordinal() + (1 if at < time(6, 0) else 0)
    return datetime.combine(date.fromordinal(day), at, PARIS)


def sky(evening: Evening, size: tuple[int, int]) -> Image.Image:
    """L'affiche de la nuit, on paper: the monogram, its secret name, the stars over Paris at its last step (north up,
    east on the left) in fine lines, the clues the passager got before and the stroke of its steps."""
    c = PALETTES[evening.palette]
    w = 2400
    h = round(w * 1.41)
    design = Image.new("RGB", (w, h), c.ground)
    draw = ImageDraw.Draw(design)
    moment = night_moment(evening)
    y = lockup(design, w / 2, h * 0.04, w * 0.06, f"SECRET DATE · {evening.long_day.upper()}", w * 0.014, c)
    title_lines(draw, evening.title, w / 2, y + h * 0.025, w * 0.8, w * 0.062, 2, c)
    radius, cx, cy = w * 0.23, w / 2, h * 0.43
    star_disc(draw, moment, cx, cy, radius, w, c)
    centred(draw, w / 2, cy + radius + w * 0.035, f"Le ciel de Paris à {moment:%H} h {moment:%M}",
            font("italic", w * 0.024), c.soft)
    ornament(draw, w / 2, h * 0.665, w * 0.1, c)
    left, right, top = w * 0.1, w * 0.53, h * 0.7
    draw.line((w * 0.5, top, w * 0.5, top + w * 0.3), fill=c.hair, width=2)
    spaced(draw, left, top, "LES INDICES", font("body", w * 0.014), c.gold, "left")
    face = font("italic", w * 0.026)
    y = top + w * 0.045
    for numeral, clue in zip(("I", "II", "III", "IV", "V"), evening.clues[:5]):
        draw.text((left, y), numeral, font=font("display", w * 0.02), fill=c.gold)
        for line in wrapped(draw, clue, face, w * 0.34):
            draw.text((left + w * 0.045, y), line, font=face, fill=c.text)
            y += face.size * 1.12
        y += w * 0.012
    spaced(draw, right + w * 0.03, top, "LE PARCOURS", font("body", w * 0.014), c.gold, "left")
    trace(design, evening.stops, (right + w * 0.09, top + w * 0.07, w * 0.86, top + w * 0.19),
          font("body", w * 0.014), round(w * 0.0022), c)
    draw = ImageDraw.Draw(design)
    step, y = font("italic", w * 0.022), top + w * 0.25
    for stop in evening.stops:
        draw.text((right + w * 0.03, y), f"{stop.at:%H:%M}".replace(":", " h "), font=font("body", w * 0.014),
                  fill=c.gold, anchor="ls")
        draw.text((right + w * 0.11, y), stop.name, font=fitted(draw, stop.name, "italic", w * 0.022, w * 0.26),
                  fill=c.text, anchor="ls")
        y += step.size * 1.35
    spaced(draw, w / 2, h * 0.955, f"{evening.names.upper()} · PARIS · 48,86° N · 2,35° E", font("body", w * 0.012),
           c.soft)
    return contain(design, size, c.ground)


SCENTS = "figue · bois de cèdre · ambre"


def candle(evening: Evening, size: tuple[int, int]) -> Image.Image:
    """The label: the names, « L'odeur de notre douce nuit du … », the scent."""
    w, h = 2400, 1200
    if size[1] > size[0]:
        w, h = h, w
    design = Image.new("RGB", (w, h), PAPER)
    draw = ImageDraw.Draw(design)
    m = w * 0.1
    centred(draw, w / 2, h * 0.14, evening.names.upper(), fitted(draw, evening.names.upper(), "body", h * 0.05, w - 2 * m), INK)
    title = f"L'odeur de notre douce nuit du {evening.day.day}\u00a0{MONTHS[evening.day.month - 1]}"
    face = font("italic", h * 0.13)
    lines = wrapped(draw, title, face, w - 2 * m)
    while len(lines) > 3:
        face = font("italic", face.size * 0.9)
        lines = wrapped(draw, title, face, w - 2 * m)
    top = h * 0.5 - len(lines) * face.size * 1.05 / 2
    for i, line in enumerate(lines):
        centred(draw, w / 2, top + i * face.size * 1.05, line, face, INK)
    draw.line((w * 0.35, h * 0.8, w * 0.65, h * 0.8), fill=(150, 146, 136), width=max(2, round(h * 0.003)))
    centred(draw, w / 2, h * 0.84, SCENTS, font("body", h * 0.04), INK)
    return contain(design, size, PAPER)


def smooth(points: list[tuple[float, float]], steps: int = 40) -> list[tuple[float, float]]:
    """A line through the points, curved (Catmull-Rom): the evening's one stroke."""
    if len(points) < 3:
        return points
    padded = [points[0], *points, points[-1]]
    line = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1:i + 3]
        for s in range(steps):
            t = s / steps
            line.append(tuple(0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t * t
                                     + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t ** 3) for k in (0, 1)))
    return [*line, points[-1]]


def route_points(stops: list[Stop], box: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    """The steps in the box, north up, the map's proportions kept (a degree of longitude is shorter in Paris)."""
    left, top, right, bottom = box
    xs = [s.lon * math.cos(math.radians(PARIS_LAT)) for s in stops]
    ys = [s.lat for s in stops]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    scale = min(right - left, bottom - top) / span
    cx, cy = (left + right) / 2, (top + bottom) / 2
    mx, my = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return [(cx + (x - mx) * scale, cy - (y - my) * scale) for x, y in zip(xs, ys)]


def heart_mug(evening: Evening, size: tuple[int, int]) -> Image.Image:
    """A white mug and, on its face (the middle of the print area), little: the monogram, the secret name, the day and
    the stroke of the evening's steps. Always on white: the ceramic is, an off-white would show as a band around it."""
    c = replace(PALETTES[evening.palette], ground=PALETTES["blanc"].ground)
    w, h = 2400, 960
    design = Image.new("RGB", (w, h), c.ground)
    draw = ImageDraw.Draw(design)
    y = lockup(design, w / 2, h * 0.08, h * 0.13, "SECRET DATE", h * 0.026, c)
    y = title_lines(draw, evening.title, w / 2, y + h * 0.04, w * 0.32, h * 0.09, 2, c)
    centred(draw, w / 2, y + h * 0.02, evening.weekday_day, font("italic", h * 0.042), c.soft)
    trace(design, evening.stops, (w * 0.455, y + h * 0.13, w * 0.545, h * 0.9), font("body", h * 0.026),
          round(h * 0.0035), c)
    return contain(design, size, c.ground)


def spaced(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, face: ImageFont.FreeTypeFont, fill,
           align: str = "centre") -> None:
    """Capitals spaced out, as the app's eyebrows (a fifth of their size between letters), centred on x or from it."""
    tracking = face.size * 0.2
    width = sum(draw.textlength(c, font=face) for c in text) + tracking * (len(text) - 1)
    x = x - width / 2 if align == "centre" else x
    for c in text:
        draw.text((x, y), c, font=face, fill=fill, anchor="lm")
        x += draw.textlength(c, font=face) + tracking


@functools.cache
def logo_mask() -> Image.Image:
    """The monogram as a mask: its gold kept (the red channel, which the velvet lacks), the velvet gone, cropped."""
    red = Image.open(LOGO).convert("RGB").getchannel("R")
    mask = red.point(lambda v: max(0, min(255, (v - 60) * 3)))
    return mask.crop(mask.getbbox())


def lockup(image: Image.Image, cx: float, top: float, height: float, words: str, size: float, c: Palette) -> float:
    """The monogram in gold ink, `height` tall, the words spaced out under it; where they end."""
    mask = logo_mask()
    mask = mask.resize((round(mask.width * height / mask.height), round(height)), Image.LANCZOS)
    image.paste(Image.new("RGB", mask.size, c.gold), (round(cx - mask.width / 2), round(top)), mask)
    face = font("body", size)
    spaced(ImageDraw.Draw(image), cx, top + height + size * 1.6, words, face, c.gold)
    return top + height + size * 2.4


def arch(w: int, h: int) -> Image.Image:
    """A mask of an arch: a rectangle under a half circle as wide."""
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, w, w), fill=255)
    draw.rectangle((0, w / 2, w, h), fill=255)
    return mask


def ornament(draw: ImageDraw.ImageDraw, cx: float, y: float, half: float, c: Palette) -> None:
    """A hairline broken by a small gold diamond."""
    d = half * 0.04
    for a, b in ((cx - half, cx - d * 2.5), (cx + d * 2.5, cx + half)):
        draw.line((a, y, b, y), fill=c.hair, width=2)
    draw.polygon([(cx, y - d), (cx + d, y), (cx, y + d), (cx - d, y)], fill=c.gold)


def title_lines(draw: ImageDraw.ImageDraw, title: str, cx: float, top: float, width: float, size: float, most: int,
                c: Palette) -> float:
    """The secret name in Cormorant, centred on at most `most` lines (smaller if need be); where it ends."""
    face = font("display", size)
    lines = wrapped(draw, title, face, width)
    while len(lines) > most and face.size > 8:
        face = font("display", face.size * 0.92)
        lines = wrapped(draw, title, face, width)
    for i, line in enumerate(lines):
        centred(draw, cx, top + i * face.size * 1.05, line, face, c.text)
    return top + len(lines) * face.size * 1.05


def trace(image: Image.Image, stops: list[Stop], box: tuple[float, float, float, float],
          labels: ImageFont.FreeTypeFont | None, width: int, c: Palette) -> list[tuple[float, float]]:
    """The evening's stroke, one fine line of emerald, its steps as small gold points, their hours beside."""
    points = route_points(stops, box)
    draw = ImageDraw.Draw(image)
    draw.line(smooth(points), fill=c.accent, width=width, joint="curve")
    r = width * 2.6
    middle = (box[0] + box[2]) / 2
    for (x, y), stop in zip(points, stops):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=c.gold)
        if labels:
            right = x >= middle
            draw.text((x + (r * 3 if right else -r * 3), y), f"{stop.at:%H:%M}".replace(":", " h "), font=labels,
                      fill=c.soft, anchor="lm" if right else "rm")
    return points


def star_disc(draw: ImageDraw.ImageDraw, moment: datetime, cx: float, cy: float, radius: float, w: int,
              c: Palette) -> None:
    """The sky at that moment in a fine circle: the figures in hairlines, the stars in ink, the cardinal points."""
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=c.hair, width=max(2, round(w * 0.001)))
    points = {}
    for name, (alt, az, mag) in sky_positions(moment).items():
        r = radius * math.tan(math.radians(90 - alt) / 2)
        points[name] = (cx - r * math.sin(math.radians(az)), cy - r * math.cos(math.radians(az)), mag)
    for a, b in FIGURES:
        if a in points and b in points:
            draw.line((points[a][:2], points[b][:2]), fill=c.dim, width=max(1, round(w * 0.001)))
    for x, y, mag in points.values():
        s = max(w * 0.0015, w * (0.006 - mag * 0.0014))
        draw.ellipse((x - s, y - s, x + s, y + s), fill=c.text)
    cardinal = font("body", w * 0.012)
    for label, (dx, dy) in {"N": (0, -1), "S": (0, 1), "E": (-1, 0), "O": (1, 0)}.items():
        draw.text((cx + dx * (radius + w * 0.022), cy + dy * (radius + w * 0.022)), label, font=cardinal, fill=c.soft,
                  anchor="mm")


def evening_link(evening: Evening) -> str:
    return evening.link or f"{(os.environ.get('APP_URL') or 'https://surprise.example').rstrip('/')}/livre"


@dataclass(frozen=True)
class Souvenir:
    key: str
    title: str
    searches: tuple[tuple[str, ...], ...]  # words of the catalogue's product titles, the most precise first
    compose: Callable[[Evening, tuple[int, int]], Image.Image]
    price: int  # cents, the draft's selling price
    preview: tuple[int, int]  # the PNG of `apercu` without the catalogue (300 dpi)
    photo: bool = True
    made: tuple[int, int, int] | None = None  # Printify's product, print provider and variant, in the Union


SOUVENIRS = [
    # Posterflow (Germany): acrylic 3 mm on a wooden stand, 13 × 20 cm.
    Souvenir("plaque", "Le carton de la soirée", (("acrylic", "wood"), ("acrylic", "plaque"), ("acrylic", "sign")),
             plaque, 2900, (1417, 2244), made=(1303, 220, 98609)),
    # OPT OnDemand (Czechia): A3 matte poster.
    Souvenir("ciel", "L'affiche de la nuit", (("poster", "(eu)"), ("matte", "poster"), ("poster",)), sky, 3500,
             (3510, 4950), photo=False, made=(443, 30, 62339)),
    # OPT OnDemand (Czechia): heart-handled mug, 11 oz.
    Souvenir("mug", "Mug cœur", (("heart", "mug"),), heart_mug, 1900, (2362, 945), photo=False, made=(896, 30, 77224)),
    # Made in the United States or Canada only: drawn, left out of the drafts.
    Souvenir("magnet", "Magnet polaroïd", (("square", "magnet"), ("photo", "magnet"), ("magnet",)), magnet, 900, (900, 900)),
    Souvenir("bougie", "La bougie de la soirée", (("soy", "candle"), ("candle",)), candle, 2400, (2362, 709),
             photo=False),
]
EUROPEAN = [s.key for s in SOUVENIRS if s.made]


def by_key(key: str) -> Souvenir:
    return next(s for s in SOUVENIRS if s.key == key)


# --- Printify -------------------------------------------------------------------------------------------------------

class Printify:
    def __init__(self, token: str, client: httpx.Client | None = None):
        self.http = client or httpx.Client(timeout=120)
        self.headers = {"Authorization": f"Bearer {token}", "User-Agent": "surprise-souvenirs"}

    def _get(self, path: str) -> Any:
        response = self.http.get(f"{API}{path}", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, body: dict) -> Any:
        response = self.http.post(f"{API}{path}", headers=self.headers, json=body)
        if response.is_error:
            raise RuntimeError(f"Printify {path} : {response.status_code} {response.text[:500]}")
        return response.json()

    def shop_id(self) -> int:
        if shop := os.environ.get("PRINTIFY_SHOP_ID"):
            return int(shop)
        shops = self._get("/shops.json")
        if not shops:
            raise RuntimeError("Aucune boutique Printify : créez-en une (Add new store), puis relancez.")
        return shops[0]["id"]

    def blueprints(self) -> list[dict]:
        return self._get("/catalog/blueprints.json")

    def providers(self, blueprint: int) -> list[dict]:
        return self._get(f"/catalog/blueprints/{blueprint}/print_providers.json")

    def provider_country(self, provider: int) -> str | None:
        return ((self._get(f"/catalog/print_providers/{provider}.json").get("location") or {}).get("country") or None)

    def variants(self, blueprint: int, provider: int) -> list[dict]:
        return self._get(f"/catalog/blueprints/{blueprint}/print_providers/{provider}/variants.json")["variants"]

    def upload(self, name: str, image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=93, dpi=(300, 300))
        return self._post("/uploads/images.json", {"file_name": name, "contents": base64.b64encode(buffer.getvalue()).decode()})["id"]

    def create_draft(self, shop: int, body: dict) -> dict:
        return self._post(f"/shops/{shop}/products.json", body)

    def product(self, shop: int, product: int | str) -> dict:
        return self._get(f"/shops/{shop}/products/{product}.json")


def find_blueprint(blueprints: list[dict], searches: tuple[tuple[str, ...], ...]) -> dict | None:
    """The catalogue's product whose title holds all the words of the first search that finds one, the shortest title."""
    for words in searches:
        found = [b for b in blueprints if all(word in b["title"].lower() for word in words)]
        if found:
            return min(found, key=lambda b: len(b["title"]))
    return None


@dataclass
class Choice:
    blueprint: dict
    provider: dict
    country: str | None
    variant: dict
    area: dict  # the variant's print area: position, width, height

    @property
    def size(self) -> tuple[int, int]:
        return self.area["width"], self.area["height"]


def choose(printify: Printify, souvenir: Souvenir, blueprints: list[dict]) -> Choice | None:
    """Its product, print provider and variant (fixed, or found by its title with the first provider of the Union and
    its first variant), and that variant's print area; None when no one in the Union makes it."""
    if souvenir.made:
        blueprint_id, provider_id, variant_id = souvenir.made
        blueprint = next((b for b in blueprints if b["id"] == blueprint_id), None)
        provider = next((p for p in printify.providers(blueprint_id) if p["id"] == provider_id), None) if blueprint else None
        variant = next((v for v in printify.variants(blueprint_id, provider_id) if v["id"] == variant_id), None) if provider else None
        if not variant:
            return None
        country = printify.provider_country(provider_id)
    else:
        blueprint = find_blueprint(blueprints, souvenir.searches)
        if not blueprint:
            return None
        countries = [(p, printify.provider_country(p["id"])) for p in printify.providers(blueprint["id"])]
        provider, country = next(((p, c) for p, c in countries if c in EUROPE), (None, None))
        if not provider:
            return None
        variant = printify.variants(blueprint["id"], provider["id"])[0]
    area = next((a for a in variant["placeholders"] if a["position"] == "front"), variant["placeholders"][0])
    return Choice(blueprint, provider, country, variant, area)


def design_size(area: tuple[int, int]) -> tuple[int, int]:
    """The print area, at most LARGEST px on its long side: Printify enlarges the design to fill it."""
    shrink = min(1, LARGEST / max(area))
    return round(area[0] * shrink), round(area[1] * shrink)


def draft_body(souvenir: Souvenir, evening: Evening, choice: Choice, image_id: str) -> dict:
    return {
        "title": f"{souvenir.title} · {evening.names} · {evening.short_day}"
                 + ("" if evening.palette == DEFAULT_GROUND else f" · {GROUNDS[evening.palette]}"),
        "description": f"Souvenir de la soirée du {evening.long_day}. Brouillon de test, non publié.",
        "blueprint_id": choice.blueprint["id"],
        "print_provider_id": choice.provider["id"],
        "variants": [{"id": choice.variant["id"], "price": souvenir.price, "is_enabled": True}],
        "print_areas": [{
            "variant_ids": [choice.variant["id"]],
            "placeholders": [{"position": choice.area["position"],
                              "images": [{"id": image_id, "x": 0.5, "y": 0.5, "scale": 1, "angle": 0}]}],
        }],
    }


@dataclass
class Draft:
    souvenir: Souvenir
    choice: Choice
    product_id: str
    mockups: list[str]
    quality: str | None


def make_drafts(printify: Printify, evening: Evening, keys: list[str], out: Path | None = OUT) -> list[Draft]:
    """Each souvenir composed at its print area's size, uploaded, made a draft product; its mockups kept in `out`."""
    shop = printify.shop_id()
    blueprints = printify.blueprints()
    drafts = []
    for souvenir in map(by_key, keys):
        choice = choose(printify, souvenir, blueprints)
        if not choice:
            print(f"{souvenir.title} : aucun atelier de l'Union européenne ne le fabrique")
            continue
        design = souvenir.compose(evening, design_size(choice.size))
        image_id = printify.upload(f"{souvenir.key}-{evening.day}.jpg", design)
        product = printify.create_draft(shop, draft_body(souvenir, evening, choice, image_id))
        mockups = [i["src"] for i in product.get("images") or []]
        quality = print_quality(evening.photos[0].size, choice.size) if souvenir.photo and evening.photos else None
        drafts.append(Draft(souvenir, choice, str(product["id"]), mockups, quality))
        if out:
            out.mkdir(parents=True, exist_ok=True)
            design.save(out / f"{souvenir.key}.png")
    return drafts


def sheet(made: dict[tuple[str, str], Image.Image], keys: list[str], grounds: list[str]) -> Image.Image:
    """The souvenirs side by side, a row per ground, each named under it: to choose a ground at a glance."""
    cell, pad, label = 700, 40, 60
    image = Image.new("RGB", (pad + len(keys) * (cell + pad), pad + len(grounds) * (cell + pad + label)), (250, 248, 244))
    draw = ImageDraw.Draw(image)
    for row, ground in enumerate(grounds):
        for col, key in enumerate(keys):
            thumb = ImageOps.contain(made[key, ground], (cell, cell), Image.LANCZOS)
            x, y = pad + col * (cell + pad), pad + row * (cell + pad + label)
            image.paste(thumb, (x + (cell - thumb.width) // 2, y + (cell - thumb.height) // 2))
            draw.text((x + cell / 2, y + cell + 12), f"{by_key(key).title} · {GROUNDS[ground]}", font=font("body", 26),
                      fill=INK, anchor="ma")
    return image


# --- command line ---------------------------------------------------------------------------------------------------

def read_photos(folder: Path | None) -> list[Image.Image]:
    if not folder:
        return []
    """Its photos in their names' order: the first is the plaque's (in the app, the most loved)."""
    paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    return [load_photo(p) for p in paths]


def token() -> str:
    if value := os.environ.get("PRINTIFY_API_TOKEN"):
        return value
    raise SystemExit("PRINTIFY_API_TOKEN manque dans .env (Printify, My profile > Connections > Personal access tokens).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Les souvenirs d'une soirée : aperçus, catalogue Printify, brouillons")
    sub = parser.add_subparsers(dest="command", required=True)
    preview = sub.add_parser("apercu", help="compose les souvenirs en PNG dans data/souvenirs/, sans Printify")
    draft = sub.add_parser("brouillon", help="crée les souvenirs en produits brouillons dans la boutique Printify")
    for command in (preview, draft):
        command.add_argument("--photos", type=Path, default=EXAMPLE_PHOTOS if EXAMPLE_PHOTOS.is_dir() else None,
                             help="un dossier de photos de la soirée, la première pour la plaque (sinon, celles de l'exemple)")
        command.add_argument("--titre", default=EXAMPLE.title, help="le nom secret de la soirée")
        command.add_argument("--indice", action="append", help="un indice reçu avant (plusieurs fois)")
        command.add_argument("--fond", default=DEFAULT_GROUND, choices=[*PALETTES, "tous"],
                             help="le fond des souvenirs (tous : un de chaque, et leur planche en aperçu)")
        command.add_argument("--prenoms", default=EXAMPLE.names)
        command.add_argument("--jour", type=date.fromisoformat, default=EXAMPLE.day)
        command.add_argument("--souvenirs", default=",".join(EUROPEAN),
                             help=f"parmi {', '.join(s.key for s in SOUVENIRS)}")
    catalogue = sub.add_parser("catalogue", help="les produits Printify dont le titre contient ces mots, leurs ateliers")
    catalogue.add_argument("mots", nargs="+")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # the catalogue's titles hold ″ and ×, which a Windows console refuses

    if args.command == "catalogue":
        printify = Printify(token())
        words = [w.lower() for w in args.mots]
        for blueprint in printify.blueprints():
            if all(w in blueprint["title"].lower() for w in words):
                where = ", ".join(f"{p['title']} ({p['id']}, {printify.provider_country(p['id']) or '?'})"
                                  for p in printify.providers(blueprint["id"]))
                print(f"{blueprint['id']} {blueprint['title']} : {where}")
        return

    keys = args.souvenirs.split(",")
    grounds = list(PALETTES) if args.fond == "tous" else [args.fond]
    photos = read_photos(args.photos)
    evenings = {g: Evening(args.prenoms, args.jour, EXAMPLE.stops, photos, title=args.titre,
                           clues=args.indice or EXAMPLE.clues, palette=g) for g in grounds}
    if args.command == "apercu":
        OUT.mkdir(parents=True, exist_ok=True)
        made = {}
        for ground, evening in evenings.items():
            for souvenir in map(by_key, keys):
                path = OUT / (f"{souvenir.key}-{ground}.png" if len(grounds) > 1 else f"{souvenir.key}.png")
                made[souvenir.key, ground] = souvenir.compose(evening, souvenir.preview)
                made[souvenir.key, ground].save(path)
                print(path)
        if len(grounds) > 1:
            sheet(made, keys, grounds).save(OUT / "planche.png")
            print(OUT / "planche.png")
        return

    printify = Printify(token())
    for ground, evening in evenings.items():
        for d in make_drafts(printify, evening, keys, out=None if len(grounds) > 1 else OUT):
            print(f"{d.souvenir.title} ({GROUNDS[ground]}) : {d.choice.blueprint['title']}, {d.choice.provider['title']} "
                  f"({d.choice.country or '?'}), {d.choice.size[0]}×{d.choice.size[1]} px"
                  + (f", qualité d'impression {d.quality}" if d.quality else ""))
            print(f"  brouillon {d.product_id}, dans Printify > My products")
            for url in d.mockups[:3]:
                print(f"  {url}")


if __name__ == "__main__":
    main()
