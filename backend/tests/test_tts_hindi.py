"""Unit tests for the TTS-layer Hindi pronunciation rewrite.

These are pure-function tests: they exercise the exact transform that runs on
the text handed to Murf, without needing any credentials.
"""

from tts_hindi import apply_hindi_pronunciation, detect_language, stream_for_tts


def test_english_utterance_with_scheme_converts_term_and_keeps_english() -> None:
    """An English sentence stays English; the scheme name becomes Devanagari."""
    text = "PM Jan Dhan Yojana helps people open savings accounts."
    language = detect_language(text)  # english or hinglish — conversion is agnostic
    out = apply_hindi_pronunciation(text, language)
    assert "पीएम जन धन योजना" in out
    assert out.startswith("पीएम जन धन योजना helps people open savings")
    assert "PM Jan Dhan Yojana" not in out


def test_english_scheme_variants_convert() -> None:
    """All requirement schemes convert for an English-detected caller."""
    cases = {
        "PM Jan Dhan Yojana": "पीएम जन धन योजना",
        "PM Kisan Samman Nidhi": "पीएम किसान सम्मान निधि",
        "PM SVANidhi": "पीएम स्वनिधि",
        "Aadhaar": "आधार",
    }
    for text, devanagari in cases.items():
        out = apply_hindi_pronunciation(text, "english")
        assert devanagari in out, f"{text!r} -> {out!r}"


def test_pure_english_untouched() -> None:
    """Pure English without any Indian terms passes through byte-for-byte."""
    text = "Please explain how to open a savings account at the bank."
    assert detect_language(text) == "english"
    assert apply_hindi_pronunciation(text, "english") == text


def test_hinglish_caller_gets_scheme_in_devanagari() -> None:
    """A Hinglish caller keeps roman script but scheme names are Devanagari."""
    text = "PM Jan Dhan Yojana ke baare mein batao."
    assert detect_language(text) == "hinglish"
    out = apply_hindi_pronunciation(text, "hinglish")
    assert "पीएम जन धन योजना" in out


def test_required_final_string_is_devanagari_not_roman() -> None:
    """Requirement 6: final string contains 'पीएम जन धन योजना', not the roman spelling."""
    original = "Please tell me everything there is to know about PM Jan Dhan Yojana."
    out = apply_hindi_pronunciation(original, "hinglish")
    assert "पीएम जन धन योजना" in out
    assert "PM Jan Dhan Yojana" not in out


async def test_stream_for_tts_reassigns_english_text() -> None:
    """stream_for_tts also converts the known term when language=english."""

    async def source():
        for chunk in ("Tell me about ", "PM Jan Dhan ", "Yojana. Then stop."):
            yield chunk

    out = []
    async for part in stream_for_tts(source(), language="english"):
        out.append(part)
    assert "".join(out) == "Tell me about पीएम जन धन योजना. Then stop."


async def test_stream_for_tts_pure_english_passthrough() -> None:
    async def source():
        for chunk in ("Could you suggest a good fixed depo", "sit plan right now?"):
            yield chunk

    out = []
    async for part in stream_for_tts(source(), language="english"):
        out.append(part)
    assert "".join(out) == "Could you suggest a good fixed deposit plan right now?"
