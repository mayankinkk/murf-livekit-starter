"""TTS-layer Hindi pronunciation for RupeeGPT.

The agent replies in whatever script the LLM picks. What the caller *hears* is
decided by the final text that reaches Murf Falcon TTS, so this module rewrites
that final text:

- Scheme names and Hindi terms are written in Devanagari (e.g. "PM Kisan Samman
  Nidhi" -> "पीएम किसान सम्मान निधि") so the en-IN voice reads them like a
  native Hindi speaker instead of English-accented roman text.
- The rewriting is a *whitelist* of genuine Hindi/Indian terms, so it is safe to
  apply even when the caller is clearly English: only the known terms (e.g.
  "PM Jan Dhan Yojana", "Aadhaar") become Devanagari, and any other English
  sentence is passed through untouched.
- The rewrite is safe to apply to a streaming text input: full phrases are never
  split across emitted chunks because we only release text at sentence
  boundaries (a scheme name never crosses one).
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterable, AsyncIterator
from typing import Literal

logger = logging.getLogger("agent")

Language = Literal["english", "hindi", "hinglish"]

# The Devanagari block (U+0900 to U+097F).
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

# English spelling -> natural Devanagari. Ordered longest/most specific first so
# "PM Kisan Samman Nidhi" wins over the shorter "Samman Nidhi" / "Yojana".
_ENGLISH_TO_HINDI: tuple[tuple[str, str], ...] = (
    ("pradhan mantri jan dhan yojana", "प्रधानमंत्री जन धन योजना"),
    ("pradhan mantri kisan samman nidhi", "प्रधानमंत्री किसान सम्मान निधि"),
    ("pradhan mantrijan dhan yojana", "प्रधानमंत्री जन धन योजना"),
    ("pm kisan samman nidhi", "पीएम किसान सम्मान निधि"),
    ("pm jan dhan yojana", "पीएम जन धन योजना"),
    ("pm svanidhi", "पीएम स्वनिधि"),
    ("sarkari yojana", "सरकारी योजना"),
    ("jan dhan yojana", "जन धन योजना"),
    ("kisan samman nidhi", "किसान सम्मान निधि"),
    ("pradhan mantri", "प्रधानमंत्री"),
    ("jan dhan", "जन धन"),
    ("samman nidhi", "सम्मान निधि"),
    ("svanidhi", "स्वनिधि"),
    ("aadhaar", "आधार"),
    ("yojana", "योजना"),
)

# Word-boundary aware, case-insensitive phrases. ``(?<!\w)`` / ``(?!\w)`` stop
# matches inside "PMKisan" or "SVANidhi's", and stop "Yojana" matching "Kujana".
_PHRASE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?<!\w)" + re.escape(source) + r"(?!\w)", re.IGNORECASE),
        translation,
    )
    for source, translation in _ENGLISH_TO_HINDI
]

# Latin words that signal Hinglish (Hindi written in Roman script). Kept to
# words that essentially never occur in plain English to avoid false positives.
HINGLISH_MARKERS = (
    "mujhe",
    "batao",
    "bataiye",
    "bata",
    "karein",
    "karo",
    "karna",
    "karte",
    "kaise",
    "kya",
    "chahiye",
    "baare",
    "baat",
    "nahi",
    "nhi",
    "mein",
    "hain",
    "hai",
    "sakta",
    "sakti",
    "sakte",
    "yeh",
    "woh",
    "voh",
    "namaste",
    "namaskar",
    "yojana",
    "sarkari",
    "swanidhi",
    "svanidhi",
    "aadhaar",
    "mera",
    "meri",
    "mere",
    "tumhara",
    "aapka",
    "samajh",
    "samjha",
    "paise",
    "rupaye",
    "rupai",
    "bharat",
    "pehle",
    "abhi",
    "shuruaat",
    "faayda",
    "milta",
    "milte",
    "milega",
    "chalein",
    "chho",
    "karke",
)

_HINGLISH_RE = re.compile(
    r"(?<!\w)(" + "|".join(re.escape(word) for word in HINGLISH_MARKERS) + r")(?!\w)",
    re.IGNORECASE,
)

# Numbers below are used by the streaming splitter.
_SENTENCE_ENDINGS = (".", "!", "?", "\n")
# Largest word count of any phrase in _ENGLISH_TO_HINDI (byte-safety margin).
_MAX_PHRASE_WORDS = 5
# Emergency flush size: if a buffered utterance has no sentence punctuation,
# we will not hold text forever. 512 characters is far beyond any TTS reply.
_MAX_BUFFER_CHARS = 512


def detect_language(text: str) -> Language:
    """Classify an utterance as English, Hindi, or Hinglish.

    Uses characters: Devanagari => Hindi; then a word list for romanized Hindi
    (Hinglish); otherwise English.
    """
    if not text:
        return "english"
    if _DEVANAGARI_RE.search(text):
        return "hindi"
    if _HINGLISH_RE.search(text):
        return "hinglish"
    return "english"


def apply_hindi_pronunciation(text: str, language: Language = "hinglish") -> str:
    """Rewrite known Hindi schemes/terms in ``text`` to their Devanagari forms.

    The phrase table is a whitelist of genuine Hindi/Indian terms (scheme names,
    "aadhaar", "pradhan mantri", ...), so it is safe to apply for *any* caller
    language: a pure-English sentence with none of those terms passes through
    byte-for-byte, while "PM Jan Dhan Yojana" in an otherwise English reply
    becomes "पीएम जन धन योजना". Anything already in Devanagari is left alone.
    """
    if not text:
        return text
    for pattern, replacement in _PHRASE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def stream_for_tts(
    text_source: AsyncIterable[str], *, language: Language
) -> AsyncIterator[str]:
    """Transform a streaming text source for Murf TTS.

    Accumulates the incoming chunks and only emits complete sentences, applying
    :func:`apply_hindi_pronunciation` per emitted sentence so a scheme name is
    never split across an emission boundary. This runs for every language: for
    English callers the whitelist still rewrites known Indian schemes/terms to
    Devanagari, while any other English sentence passes through unchanged.
    """

    async def wrapped() -> AsyncIterator[str]:
        buffer = ""
        async for chunk in text_source:
            buffer += chunk
            while True:
                cut = _sentence_cut(buffer)
                if cut is None:
                    break
                yield apply_hindi_pronunciation(buffer[:cut], language)
                buffer = buffer[cut:]

            if len(buffer) >= _MAX_BUFFER_CHARS:
                word_break = _word_cut(buffer)
                if word_break is not None:
                    yield apply_hindi_pronunciation(buffer[:word_break], language)
                    buffer = buffer[word_break:]

        if buffer:
            yield apply_hindi_pronunciation(buffer, language)

    return wrapped()


def _sentence_cut(buffer: str) -> int | None:
    """Index just past the last sentence-ending punctuation, if present."""
    for punct in _SENTENCE_ENDINGS:
        idx = buffer.rfind(punct)
        if idx != -1:
            return idx + 1
    return None


def _word_cut(buffer: str) -> int | None:
    """Index of the last space that leaves at least ``_MAX_PHRASE_WORDS`` words.

    Used only when no sentence punctuation has arrived for a very long time.
    Cutting after a word that has at least ``_MAX_PHRASE_WORDS`` whole words
    after it means no scheme-name phrase spans the cut boundary.
    """
    if len(buffer) < _MAX_PHRASE_WORDS * 8:
        return None
    for idx in range(len(buffer) - 1, -1, -1):
        if buffer[idx] == " ":
            rest = buffer[idx + 1 :].lstrip(" ").split()
            if len(rest) >= _MAX_PHRASE_WORDS:
                return idx
    return None
