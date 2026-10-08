"""Patterns told quickly (surprise.patterns): the words every match begins with, read off the pattern; a text without
any of them is skipped, and the answer is always the pattern's own."""

import re

import pytest

from surprise import keywords, originality, tags
from surprise.patterns import leading_words, matcher


@pytest.mark.parametrize("pattern, words", [
    (r"karaok", ("karaok",)),
    (r"blind[- ]tests?|\bquiz", ("blind-test", "blind test", "quiz")),  # \b takes no letter
    (r"mini[- ]?golf|mad golf", ("mini", "mad golf")),  # re factors out their first letter
    (r"z[ée]nith|accor arena", ("zénith", "zenith", "accor arena")),  # a small set of letters: one word each
    (r"\*{4,5}|ritz", ("****", "ritz")),  # at least four stars
    (r"(?<!murder )party|club\b.*\bpresents?", ("party", "club")),  # a look-behind takes no letter either
    (r"\b(?:pizza|burger)\b", ("pizza", "burger")),
    (r"ch[âa]teaux?(?![- ]rouge)|manoir", ("château", "chateau", "manoir")),
])
def test_the_words_every_match_begins_with(pattern, words):
    assert leading_words(re.compile(pattern)) == words


@pytest.mark.parametrize("pattern", [
    r"[a-z]+bar",  # a range: any word
    r"(?:the )?bar",  # an optional beginning
    r"bars?|.*club",  # one branch may begin anywhere
    r"a|bar",  # a one-letter word is in every text
    r"(?i)karaok",  # case ignored: the substring test would not
])
def test_no_words_when_a_match_may_begin_otherwise(pattern):
    assert leading_words(re.compile(pattern)) is None


@pytest.mark.parametrize("flags", [0, re.IGNORECASE])
def test_a_pattern_without_words_is_simply_run(flags):
    found = matcher(re.compile(r"[a-z]+ bar", flags))
    assert found("un joli bar") and not found("rien ici")


# Every pattern the server runs over the activities, and texts around their words: in them, cut short, glued to others.
PATTERNS = [
    *(re.compile(p) for _, _, _, p in tags._TAG_RULES),
    *(re.compile(p) for _, _, p in keywords._RULES),
    *(p for _, _, p in originality._NATURE_PATTERNS),
    originality._COMMON, originality._SETTING, originality._BIG_VENUE, originality._CHAIN, originality._GENERIC_CUISINE,
]


def _texts(words):
    for word in words:
        yield word
        yield f"une soirée {word} à paris"
        yield word[:-1]
        yield f"x{word}x"
        yield f"le {word}s du soir, puis {word} live"


def test_each_pattern_answers_as_itself():
    texts = [
        "", "un bar caché", "soirée karaoké et blind test entre amis", "dîner-spectacle au zénith", "escape game",
        "un château, un manoir", "visite du louvre en bus panoramique", "pizza burger kebab", "rooftop **** au ritz",
    ]
    for pattern in PATTERNS:
        found = matcher(pattern)
        for text in [*texts, *_texts(leading_words(pattern) or ())]:
            assert found(text) == bool(pattern.search(text)), (pattern.pattern, text)
