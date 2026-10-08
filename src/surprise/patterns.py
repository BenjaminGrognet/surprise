"""Regular expressions told quickly: tags, originality and keywords run some eighty patterns over each of thirty
thousand activities whenever the server loads them. Most patterns begin with words ("karaok", "blind test", "quiz");
a text holding none of them cannot match, which a substring test tells far quicker than the pattern itself.
"""

import re
from collections.abc import Callable

try:  # The parser of the re module (sre_parse before Python 3.11): without it, every pattern is simply run.
    from re import _constants as _sre, _parser
except ImportError:  # pragma: no cover
    _sre = _parser = None

# Words this short are in most texts: no time saved.
MIN_WORD = 2
# A word begun by a small set of letters ("z[ée]nith") stands for one word per letter: so many words at most.
MAX_WORDS = 16


def _letters(value: list) -> list[str] | None:
    """The letters of a small character class of single letters ("[ée]"); None for ranges, negations and the like."""
    if len(value) > 4 or any(op is not _sre.LITERAL for op, _ in value):
        return None
    return [chr(code) for _, code in value]


def _starts(items: list) -> list[str] | None:
    """The words a match of this sequence begins with (one of them, whole); None when it may begin otherwise."""
    words = [""]
    for op, value in items:
        if op in (_sre.AT, _sre.ASSERT, _sre.ASSERT_NOT):
            continue  # \b, ^, look-arounds: they take no letter
        if op is _sre.LITERAL:
            words = [word + chr(value) for word in words]
            continue
        if op is _sre.IN and (letters := _letters(value)) and len(words) * len(letters) <= MAX_WORDS:
            words = [word + letter for word in words for letter in letters]
            continue
        if op in (_sre.MAX_REPEAT, _sre.MIN_REPEAT) and value[0] >= 1 and len(value[2]) == 1 and value[2][0][0] is _sre.LITERAL:
            # At least `low` times the same letter ("\*{4,5}"); what follows may begin anywhere after.
            low, _, [(_, code)] = value
            return [word + chr(code) * low for word in words]
        inner = None
        if op is _sre.BRANCH:
            inner = _branches(value[1])
        elif op is _sre.SUBPATTERN and not value[1] & re.IGNORECASE:
            inner = _starts(list(value[3]))
        if inner is not None and (len(words) == 1 or len(words) * len(inner) <= MAX_WORDS):
            return [word + start for word in words for start in inner]
        return words if all(words) else None
    return words if all(words) else None


def _branches(branches: list) -> list[str] | None:
    """The words each branch of an alternation begins with; None when one of them may begin otherwise."""
    words = []
    for branch in branches:
        if not (found := _starts(list(branch))):
            return None
        words += found
    return words


def leading_words(pattern: re.Pattern[str]) -> tuple[str, ...] | None:
    """Words one of which every match of `pattern` begins with; None when a branch may begin otherwise (a wide
    character class, an optional part), when the pattern ignores case, or when a word is too short to save anything."""
    if _parser is None or pattern.flags & re.IGNORECASE:
        return None
    try:
        words = _starts(list(_parser.parse(pattern.pattern, pattern.flags)))
    except Exception:  # a shape of the parser's tree unknown here: the pattern is run
        return None
    if not words or min(map(len, words)) < MIN_WORD:
        return None
    return tuple(dict.fromkeys(words))


def matcher(pattern: re.Pattern[str]) -> Callable[[str], bool]:
    """Whether `pattern` matches somewhere in a text, as bool(pattern.search(text)), skipping the texts that hold none
    of its leading words."""
    words = leading_words(pattern)
    if words is None:
        return lambda text: pattern.search(text) is not None
    return lambda text: any(word in text for word in words) and pattern.search(text) is not None
