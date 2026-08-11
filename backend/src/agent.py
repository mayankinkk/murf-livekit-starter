import asyncio
import json
import logging
import os
import time
import uuid

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    inference,
    llm,
    room_io,
    tokenize,
)
from livekit.plugins import deepgram, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import memory
import schemes
import tts_hindi

logger = logging.getLogger("agent")

load_dotenv(".env.local")

SYSTEM_PROMPT = """You are RupeeGPT, a personal AI assistant for Indian users.

CALLER MEMORY
- At the very start, call lookup_user() to fetch the caller's saved memory. Never ask for an ID; identity is resolved automatically. Never put caller memory into your own prompt.
- Saved profile: greet naturally by name (e.g. "Namaste Rahul, welcome back."), mirror their saved language_preference, and mention one relevant fact ("Would you like to continue from PM Jan Dhan Yojana?"). Do not repeat the whole profile.
- No saved profile: use the GREETING below, and also address the user's question if they asked one.

CONSENT (MANDATORY — enforced by the tools)
- Every NEW caller-specific fact requires explicit spoken consent in the CURRENT call before it may be saved: name, language preference, schemes_checked, eligibility_answers, and any other personal or financial note. Never save first and ask afterwards.
- Ask naturally, naming the exact fact, e.g. "Would you like me to remember that you have already checked PM Jan Dhan Yojana for future conversations?", "Would you like me to remember your name for future help?", or "Would you like me to remember that your income is below 3 lakh for future conversations?".
- Merely stating or sharing a fact is NOT consent, and never saves anything by itself. In the same turn a caller first mentions a new fact, only ask whether to remember it — do NOT call grant_user_memory_consent or save_user_memory in that turn, even if you are certain they want it saved.
- A "Yes, please" (or any clear affirmation) IS consent for exactly the fact you asked about. Only then, in the NEXT turn, call grant_user_memory_consent(...) then save_user_memory(...) with those exact values.
- Only after the caller explicitly says YES:
    1) Call grant_user_memory_consent(...) with the EXACT values the caller agreed to.
    2) Immediately call save_user_memory(...) with the SAME values.
- A clear NO (or any unsure / non-yes answer) means never save that fact: do NOT call grant_user_memory_consent or save_user_memory for it, and do not ask again for it in this conversation.
- Do NOT re-ask, re-consent, or re-save facts that are already in the caller's saved profile (returned by lookup_user) or that were already consented and saved earlier in this conversation.
- Never grant or save anything the caller did not explicitly agree to. If you are unsure whether they agreed, ask again.
- Never store sensitive data: bank or account numbers, UPI IDs, OTPs, PINs, passwords, card details, Aadhaar or PAN. Never fabricate facts the caller never shared.
- If memory is unavailable, act as if no memory exists and help normally.

GREETING (only for callers with no saved profile)
"Hello! I'm RupeeGPT, your AI financial assistant. I can help you with banking, UPI, savings, budgeting, loans, investments, and financial safety. How can I help you today?"

YOUR ROLE
- Explain Indian personal finance (banking, UPI, savings, budgeting, loans, investments, insurance, taxation basics, digital payments, government schemes, fraud prevention) in simple, friendly language.
- You are not a licensed advisor or bank employee. Never claim live account details, balances, or real-time data.

LANGUAGE (mirror the caller — highest priority)
- ENGLISH: reply fully in English, no Devanagari. Keep scheme names in English spelling ("PM Kisan Samman Nidhi").
- HINDI: reply fully in Hindi/Devanagari, including schemes (पीएम किसान सम्मान निधि, प्रधानमंत्री जन धन योजना, पीएम स्वनिधि, आधार).
- HINGLISH: reply in Roman-script Hinglish, but write all Hindi terms and scheme names strictly in Devanagari (e.g. "apply for the पीएम किसान सम्मान निधि scheme" and "पीएम किसान सम्मान निधि apply kaise karein"). Never write scheme names or Hindi terms in Roman script.
- Never ask a caller to repeat because of language; if unclear, assume and continue.

SCHEME DATA DISCLAIMER (say it once, then keep it natural)
- On your FIRST successful personalized scheme lookup in this conversation,
  briefly and conversationally mention: the scheme information comes from a
  public dataset collected on the date in the tool's data_as_of field (e.g.
  "collected on 5 July 2026"), it is not live or real-time and details may have
  changed, and the caller should verify current details on the official scheme
  page before applying.
- After that first scheme response, do NOT repeat the dataset date, source,
  non-live warning, or verify advice on subsequent responses; keep answering
  naturally using the scheme data the tool returned.
- If the caller explicitly asks where the information came from, how recent it
  is, or whether it is live (e.g. "Where did you get this?", "How recent is
  this?", "Is this live?"), provide the dataset source and collection date again.
- If a genuinely new scheme lookup happens later in the same conversation, do
  not automatically repeat the full disclaimer; only mention the metadata again
  if it is genuinely needed for clarity.

SAFETY & ESCALATION
- Never ask for or store OTPs/UPI PINs/ATM PINs/CVVs/passwords/Aadhaar or full account numbers. Never transact or authorize payments, never guarantee returns/approvals/eligibility, never impersonate banks/officials, never fabricate facts.
- For account-specific issues, suspected fraud, or regulated financial/tax/legal advice, explain the limit and refer to the bank, official customer support, RBI, or a qualified advisor.
- Keep replies brief and conversational (1-3 short sentences). No markdown, emojis, or formatting."""


# ---------- Tool schemas ----------
# Day-4 fix: the OpenAI/Groq strict tool schema validator requires every object
# to declare `additionalProperties: false`. Pydantic turns a bare
# `dict[str, object]` into an object with `additionalProperties: true`, which the
# provider rejects, so both memory tools now ship an explicit `raw_schema`.
#
# `eligibility_answers` keys are dynamic from the caller's answers, but the
# provider accepts no unconstrained object here. We bound the supported fields
# explicitly and keep every one optional (`required: []`) so the agent never has
# to fabricate an answer the caller didn't share.
_ELIGIBILITY_ANSWERS_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "income_bracket": {
            "type": "string",
            "description": "The caller's income bracket, e.g. 'below 3 lakh'.",
        },
        "student": {
            "type": "boolean",
            "description": "Whether the caller is a student.",
        },
        "farmer": {
            "type": "boolean",
            "description": "Whether the caller is a farmer.",
        },
        "self_employed": {
            "type": "boolean",
            "description": "Whether the caller is self-employed.",
        },
        "senior_citizen": {
            "type": "boolean",
            "description": "Whether the caller is a senior citizen.",
        },
        "has_bank_account": {
            "type": "boolean",
            "description": "Whether the caller has a bank account.",
        },
    },
    "required": [],
}


def _pick_arg(raw: dict[str, object] | None, key: str, direct: object) -> object:
    """Pick a tool argument from the LLM's raw JSON first, else the direct value.

    Raw `@function_tool(raw_schema=...)` tools are invoked by LiveKit with the
    whole arguments object as `raw_arguments`. Tests/direct callers use the named
    parameters instead. This keeps both call styles working.
    """
    if isinstance(raw, dict) and key in raw:
        return raw[key]
    return direct


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self._user_language: tts_hindi.Language = "english"

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        """Track the caller's language so the TTS node pronounces scheme names right."""
        text = (new_message.text_content if new_message else None) or ""
        self._user_language = tts_hindi.detect_language(text)
        logger.info("[LANG] user language=%s input=%s", self._user_language, text[:120])

    async def tts_node(self, text, model_settings):
        """TTS node: rewrite final text to Devanagari for Hindi/Hinglish turns.

        The phrase table in tts_hindi is a whitelist of known Hindi/Indian terms,
        so it applies to every turn: a pure-English sentence is passed through
        unchanged, while known schemes/terms (e.g. "PM Jan Dhan Yojana") are
        converted to Devanagari even when the caller is English.
        """
        language = self._tts_language()
        tts_parts: list[str] = []
        original_parts: list[str] = []
        frames = 0
        first_audio_at: float | None = None
        started_at = time.perf_counter()

        async def _capture_original(source):
            async for part in source:
                original_parts.append(part)
                yield part

        async def _tracked():
            async for part in tts_hindi.stream_for_tts(
                _capture_original(text), language=language
            ):
                tts_parts.append(part)
                yield part

        try:
            async for frame in Agent.default.tts_node(self, _tracked(), model_settings):
                frames += 1
                if first_audio_at is None:
                    first_audio_at = time.perf_counter() - started_at
                yield frame
            logger.info(
                "[TTS] complete language=%s frames=%d first_audio=%.2fs duration=%.2fs "
                "text_chars=%d",
                language,
                frames,
                first_audio_at or 0.0,
                time.perf_counter() - started_at,
                len("".join(tts_parts)),
            )
            logger.info("[TTS] language=%s", language)
            logger.info("[TTS] original=%s", "".join(original_parts))
            logger.info("[TTS] transformed=%s", "".join(tts_parts))
        except asyncio.CancelledError:
            logger.info("[TTS] cancelled language=%s frames=%d", language, frames)
            raise
        except Exception as exc:
            logger.error(
                "[TTS] failed language=%s frames=%d err=%r", language, frames, exc
            )
            raise

    def _tts_language(self) -> str:
        lang = getattr(self, "_user_language", "english") or "english"
        return lang if lang in ("hindi", "hinglish") else "english"

    @function_tool(
        raw_schema={
            "name": "lookup_user",
            "description": (
                "Find the current caller in the database and return their saved "
                "profile. Call this once at the very start of every conversation. "
                "Returns the caller's saved name, language preference and any "
                "relevant facts (e.g. schemes they already checked), or a JSON "
                "object signalling that no saved profile exists. Takes no "
                "arguments."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    )
    async def lookup_user(
        self, context: RunContext, raw_arguments: dict[str, object]
    ) -> str:
        """Find the current caller in the database and return their saved profile.

        Call this once at the very start of every conversation.
        Returns the caller's saved name, language preference and any relevant
        facts (e.g. schemes they already checked), or a JSON object signalling
        that no saved profile exists.

        Returns:
            A JSON string of the caller's saved memory, or
            {"memory": "none"} when there is no saved profile or memory is unavailable.
        """
        user_id = _caller_user_id(context)
        profile = memory.lookup_user(user_id)
        if not profile:
            return json.dumps({"memory": "none"}, ensure_ascii=False)
        return json.dumps(
            {
                "name": profile.get("name"),
                "language_preference": profile.get("language_preference"),
                "facts": profile.get("facts", {}),
            },
            ensure_ascii=False,
        )

    @function_tool(
        raw_schema={
            "name": "grant_user_memory_consent",
            "description": (
                "Record the caller's explicit spoken consent to remember specific "
                "facts. Call this ONLY after the caller has clearly said YES to "
                "you saving the information, in the current conversation. Pass "
                "the EXACT values the caller agreed to, then call "
                "save_user_memory() with the same values. save_user_memory() "
                "refuses to persist anything that was not first granted here (or "
                "is not already part of the caller's saved profile). WARNING: "
                "merely stating a fact is NOT consent — ask first, and only call "
                "this once the caller has affirmed they want it remembered."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [],
                "properties": {
                    "name": {
                        "type": ["string", "null"],
                        "description": "The caller's name they agreed to have "
                        "remembered.",
                    },
                    "language_preference": {
                        "type": ["string", "null"],
                        "description": "Their preferred language ('English', "
                        "'Hindi', 'Hinglish') they agreed to have remembered.",
                    },
                    "scheme_checked": {
                        "type": ["string", "null"],
                        "description": "A scheme the caller agreed to have "
                        "remembered they already checked, e.g. 'PM Jan Dhan "
                        "Yojana'.",
                    },
                    "note": {
                        "type": ["string", "null"],
                        "description": "Any non-sensitive caller fact they "
                        "agreed to have remembered.",
                    },
                    "eligibility_answers": {
                        **_ELIGIBILITY_ANSWERS_SCHEMA,
                        "description": "Eligibility details (e.g. income, "
                        "student status) the caller agreed to have remembered. "
                        "Only include values the caller explicitly shared.",
                    },
                },
            },
        }
    )
    async def grant_user_memory_consent(
        self,
        context: RunContext,
        raw_arguments: dict[str, object] | None = None,
        language_preference: str | None = None,
        name: str | None = None,
        note: str | None = None,
        scheme_checked: str | None = None,
        eligibility_answers: dict[str, object] | None = None,
    ) -> str:
        """Record the caller's explicit spoken consent to remember specific facts.

        Call this ONLY after the caller has clearly said YES to you saving the
        information, in the current conversation. Pass the EXACT values the
        caller agreed to. Then call save_user_memory() with the same
        values.

        Args:
            raw_arguments: The raw arguments object from the LLM (used for
                @function_tool(raw_schema=...) calls).
            name: The caller's name they agreed to have remembered.
            language_preference: Their preferred language ("English", "Hindi",
                "Hinglish") they agreed to have remembered.
            scheme_checked: A scheme the caller agreed to have remembered they
                already checked, e.g. "PM Jan Dhan Yojana".
            note: Any non-sensitive caller fact they agreed to have remembered.
            eligibility_answers: Eligibility details (e.g. income, student
                status) the caller agreed to have remembered.
        """
        language_preference = _pick_arg(
            raw_arguments, "language_preference", language_preference
        )
        name = _pick_arg(raw_arguments, "name", name)
        scheme_checked = _pick_arg(raw_arguments, "scheme_checked", scheme_checked)
        note = _pick_arg(raw_arguments, "note", note)
        if not isinstance(language_preference, str):
            language_preference = None
        if not isinstance(name, str):
            name = None
        if not isinstance(scheme_checked, str):
            scheme_checked = None
        if not isinstance(note, str):
            note = None
        picked_eligibility = _pick_arg(
            raw_arguments, "eligibility_answers", eligibility_answers
        )
        eligibility_answers = (
            dict(picked_eligibility) if isinstance(picked_eligibility, dict) else None
        )
        data = _session_userdata(context)
        if not isinstance(data, dict):
            return "Consent cannot be recorded in this session."

        consent = data.setdefault(_CONSENT_KEY, {})
        for scope, value in (
            ("name", name),
            ("language_preference", language_preference),
            ("scheme_checked", scheme_checked),
        ):
            if value is None:
                continue
            values = consent.setdefault(scope, [])
            if not isinstance(values, list):
                values = []
                consent[scope] = values
            if value not in values:
                values.append(value)
        if note is not None:
            consent["note"] = True
        if eligibility_answers:
            consent["eligibility_answers"] = True

        logger.info(
            "[MEMORY] caller consent recorded name=%r lang=%r schemes=%r",
            name,
            language_preference,
            scheme_checked,
        )
        return (
            "Consent recorded for this conversation. You may now call "
            "save_user_memory() with the same values to persist them."
        )

    @function_tool(
        raw_schema={
            "name": "save_user_memory",
            "description": (
                "Create or update the current caller's saved memory in the "
                "database. Refuses to save anything new unless the caller has "
                "explicitly consented in the CURRENT conversation: first call "
                "grant_user_memory_consent() with the exact same values after "
                "the caller says YES, then call this with the same values. "
                "Information already in the caller's saved profile needs no "
                "second consent. Missing arguments are left unchanged and new "
                "facts are merged with any existing facts so a returning caller "
                "is never duplicated."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [],
                "properties": {
                    "name": {
                        "type": ["string", "null"],
                        "description": "The caller's name.",
                    },
                    "language_preference": {
                        "type": ["string", "null"],
                        "description": "The caller's preferred language, e.g. "
                        "'English', 'Hindi', or 'Hinglish'.",
                    },
                    "scheme_checked": {
                        "type": ["string", "null"],
                        "description": "The name of a government/savings scheme "
                        "the caller has already checked, e.g. 'PM Jan Dhan "
                        "Yojana'. Stored under facts.schemes_checked.",
                    },
                    "eligibility_answers": {
                        **_ELIGIBILITY_ANSWERS_SCHEMA,
                        "description": "Eligibility details the caller shared, "
                        "e.g. {'income_bracket': 'below 3 lakh', 'student': "
                        "true}. Stored under facts.eligibility_answers.",
                    },
                    "note": {
                        "type": ["string", "null"],
                        "description": "Any other short, non-sensitive fact "
                        "worth remembering, e.g. 'caller is a rural small "
                        "farmer'. Never store bank account numbers, UPI IDs, "
                        "OTPs, PINs, card details, or Aadhaar/PAN numbers.",
                    },
                },
            },
        }
    )
    async def save_user_memory(
        self,
        context: RunContext,
        raw_arguments: dict[str, object] | None = None,
        language_preference: str | None = None,
        name: str | None = None,
        note: str | None = None,
        scheme_checked: str | None = None,
        eligibility_answers: dict[str, object] | None = None,
    ) -> str:
        """Create or update the current caller's saved memory in the database.

        This tool refuses to save anything new unless the caller has explicitly
        consented in the CURRENT conversation: first call
        grant_user_memory_consent() with the exact values after the caller says
        YES, then call this with the same values. Information that is already in
        the caller's saved profile needs no second consent. Missing arguments
        are left unchanged, and new facts are merged with any existing facts so
        a returning caller is never duplicated.

        Args:
            raw_arguments: The raw arguments object from the LLM (used for
                @function_tool(raw_schema=...) calls).
            name: The caller's name.
            language_preference: The caller's preferred language, e.g. "English",
                "Hindi", or "Hinglish".
            scheme_checked: The name of a government/savings scheme the caller
                has already checked, e.g. "PM Jan Dhan Yojana". Stored under
                facts.schemes_checked.
            eligibility_answers: Eligibility details the caller shared, e.g.
                {"income_bracket": "below 3 lakh", "student": true}. Stored
                under facts.eligibility_answers.
            note: Any other short, non-sensitive fact worth remembering, e.g.
                "caller is a rural small farmer". Never pass bank account
                numbers, UPI IDs, OTPs, PINs, card details, or Aadhaar/PAN numbers.
        """
        language_preference = _pick_arg(
            raw_arguments, "language_preference", language_preference
        )
        name = _pick_arg(raw_arguments, "name", name)
        scheme_checked = _pick_arg(raw_arguments, "scheme_checked", scheme_checked)
        note = _pick_arg(raw_arguments, "note", note)
        if not isinstance(language_preference, str):
            language_preference = None
        if not isinstance(name, str):
            name = None
        if not isinstance(scheme_checked, str):
            scheme_checked = None
        if not isinstance(note, str):
            note = None
        picked_eligibility = _pick_arg(
            raw_arguments, "eligibility_answers", eligibility_answers
        )
        eligibility_answers = (
            dict(picked_eligibility) if isinstance(picked_eligibility, dict) else None
        )
        user_id = _caller_user_id(context)
        if not user_id:
            return "Memory is unavailable right now, so nothing was saved."

        data = _session_userdata(context)
        consent = data.get(_CONSENT_KEY, {}) if isinstance(data, dict) else {}
        if not isinstance(consent, dict):
            consent = {}

        blocked: list[str] = []
        current = memory.lookup_user(user_id) or {}
        current_facts = current.get("facts", {}) if isinstance(current, dict) else {}
        if not isinstance(current_facts, dict):
            current_facts = {}

        if name is not None:
            saved_name = current.get("name")
            if name != saved_name and not _consent_covers(consent, "name", name):
                blocked.append(f"name ({name})")
                name = None

        if language_preference is not None:
            saved_lang = current.get("language_preference")
            if language_preference != saved_lang and not _consent_covers(
                consent, "language_preference", language_preference
            ):
                blocked.append(f"language preference ({language_preference})")
                language_preference = None

        if scheme_checked:
            saved_schemes = current_facts.get("schemes_checked", []) or []
            if scheme_checked not in saved_schemes and not _consent_covers(
                consent, "scheme_checked", scheme_checked
            ):
                blocked.append(f"scheme ({scheme_checked})")
                scheme_checked = None

        if note:
            saved_notes = current_facts.get("notes", []) or []
            if note not in saved_notes and not _consent_covers(consent, "note", note):
                blocked.append("note")
                note = None

        if eligibility_answers and not _consent_covers(
            consent, "eligibility_answers", None
        ):
            blocked.append("eligibility details")
            eligibility_answers = None

        facts: dict[str, object] | None = None
        if scheme_checked or note or eligibility_answers:
            facts = {}
            if scheme_checked:
                facts["schemes_checked"] = [scheme_checked]
            if note:
                facts["notes"] = [note]
            if eligibility_answers:
                facts["eligibility_answers"] = dict(eligibility_answers)

        has_save = any(
            value is not None
            for value in (
                name,
                language_preference,
                scheme_checked,
                note,
                eligibility_answers,
            )
        )
        if not has_save and not facts:
            if blocked:
                return (
                    "Nothing was saved without the caller's consent for: "
                    + ", ".join(blocked)
                    + ". If the caller has ALREADY agreed IN THIS "
                    "conversation, first call grant_user_memory_consent() with "
                    "the exact same values and then call save_user_memory() again "
                    "with them — do not ask again. If the caller has NOT agreed "
                    "yet, ask them first and only save after an explicit YES."
                )
            return "Nothing to save would be different from what is already saved."

        saved = memory.save_user_memory(
            user_id,
            name=name,
            language_preference=language_preference,
            facts=facts,
        )
        if not saved:
            return "Memory is unavailable right now, so nothing was saved."
        if blocked:
            return (
                "Caller memory saved for the consented details. Not saved because "
                "consent was not granted: "
                + ", ".join(blocked)
                + ". If the caller already agreed IN THIS conversation, call "
                "grant_user_memory_consent() with those values, then save again. "
                "Otherwise ask first and only save after an explicit YES."
            )
        return "Caller memory saved."

    @function_tool(
        raw_schema={
            "name": "find_eligible_schemes",
            "description": (
                "Check which Indian government schemes a caller may be eligible "
                "for by matching their profile against a local public dataset of "
                "Indian government schemes. Call this ONLY when the caller asks "
                "for a personalized eligibility check or scheme recommendation "
                "based on their own profile, e.g. 'what government schemes can I "
                "get?', 'which schemes am I eligible for?', 'are there schemes "
                "for someone like me?', 'check schemes for my profile'. Do NOT "
                "call it for generic questions about what a scheme does (e.g. "
                "'what is PM Jan Dhan Yojana?') or for general scheme "
                "explanations. Pass only facts the caller actually shared: age "
                "(years), state (e.g. 'Delhi'), annual_income (rupees), gender "
                "('male'/'female'), occupation, student (true/false), "
                "caste/social_category ('SC'/'ST'/'OBC'/'General'), residence "
                "('rural'/'urban'), disability (true/false), bpl (true/false). "
                "Never fabricate or guess a field. If a useful field is missing "
                "— especially state, age, or income — ask the caller for it "
                "first, then call this tool. Returns a small set of PRELIMINARY "
                "matches (name, category, reason, benefits, documents, official "
                "URL) plus the dataset source and collection date; it is NOT a "
                "live government API and never guarantees official eligibility. "
                "DISCLAIMER — ONCE, CONVERSATIONALLY: on the FIRST successful "
                "scheme lookup in this conversation, briefly tell the caller the "
                "information comes from the public scheme dataset, say when it "
                "was collected from the 'data_as_of' field (e.g. 'collected on "
                "5 July 2026'), make clear it is not live or real-time and "
                "details may have changed, and advise verifying current details "
                "on the official scheme page before applying. Do NOT repeat "
                "that disclaimer (dataset date, source, non-live warning, verify "
                "advice) on later responses; keep answering naturally using the "
                "returned scheme data. Only provide the dataset source and date "
                "again if the caller explicitly asks where the data is from, "
                "how recent it is, or whether it is live. If a new scheme "
                "lookup happens later in the same conversation, do not "
                "automatically repeat the full disclaimer; mention the metadata "
                "again only if it is genuinely needed for clarity. "
                "FAILURE HANDLING: if the result has status 'error', the scheme "
                "data is unavailable. Say ONLY that you are unable to check the "
                "scheme information right now and don't want to give an "
                "incorrect answer, and offer to check again later. Do NOT "
                "speculate about schemes, scholarships, benefits, portals, or "
                "eligibility — not even in general terms. Never invent schemes "
                "or eligibility criteria. If the result has status 'success' "
                "but no matches, say clearly that no matching schemes were "
                "found for their profile."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [],
                "properties": {
                    "age": {
                        "type": "integer",
                        "description": "The caller's age in years.",
                    },
                    "state": {
                        "type": "string",
                        "description": "The caller's state, e.g. 'Delhi' or "
                        "'Karnataka'.",
                    },
                    "annual_income": {
                        "type": "integer",
                        "description": "The caller's family/annual income in "
                        "rupees, e.g. 300000.",
                    },
                    "gender": {
                        "type": "string",
                        "enum": ["male", "female"],
                        "description": "The caller's gender.",
                    },
                    "occupation": {
                        "type": "string",
                        "description": "The caller's occupation, e.g. 'student', "
                        "'farmer', 'street vendor'.",
                    },
                    "student": {
                        "type": "boolean",
                        "description": "Whether the caller is a student.",
                    },
                    "caste": {
                        "type": "string",
                        "enum": ["SC", "ST", "OBC", "General"],
                        "description": "The caller's social category, e.g. "
                        "'SC', 'ST', 'OBC', or 'General'.",
                    },
                    "residence": {
                        "type": "string",
                        "enum": ["rural", "urban"],
                        "description": "Whether the caller lives in a rural or "
                        "urban area.",
                    },
                    "disability": {
                        "type": "boolean",
                        "description": "Whether the caller has a disability status.",
                    },
                    "bpl": {
                        "type": "boolean",
                        "description": "Whether the caller's family is Below "
                        "Poverty Line (BPL).",
                    },
                },
            },
        }
    )
    async def find_eligible_schemes(
        self,
        context: RunContext,
        raw_arguments: dict[str, object] | None = None,
        age: object | None = None,
        state: object | None = None,
        annual_income: object | None = None,
        gender: object | None = None,
        occupation: object | None = None,
        student: object | None = None,
        caste: object | None = None,
        residence: object | None = None,
        disability: object | None = None,
        bpl: object | None = None,
    ) -> str:
        """Match the caller's profile against the local schemes dataset.

        Call this only for a personalized "which schemes am I eligible for?"
        question, with exactly the facts the caller shared (nothing invented).
        Returns a JSON string with a small set of preliminary matches plus the
        dataset source and collection date — or a controlled error / empty
        result. Never raises.
        """
        age = _pick_arg(raw_arguments, "age", age)
        state = _pick_arg(raw_arguments, "state", state)
        annual_income = _pick_arg(raw_arguments, "annual_income", annual_income)
        gender = _pick_arg(raw_arguments, "gender", gender)
        occupation = _pick_arg(raw_arguments, "occupation", occupation)
        student = _pick_arg(raw_arguments, "student", student)
        caste = _pick_arg(raw_arguments, "caste", caste)
        residence = _pick_arg(raw_arguments, "residence", residence)
        disability = _pick_arg(raw_arguments, "disability", disability)
        bpl = _pick_arg(raw_arguments, "bpl", bpl)

        result = schemes.find_eligible_schemes(
            age=age,
            state=state,
            annual_income=annual_income,
            gender=gender,
            occupation=occupation,
            student=student,
            caste=caste,
            residence=residence,
            disability=disability,
            bpl=bpl,
        )
        return json.dumps(result, ensure_ascii=False)


server = AgentServer()


_CONSENT_KEY = "consent"


def _session_userdata(context: RunContext) -> dict:
    """Per-call session state carried across turns in this conversation."""
    try:
        data = context.userdata
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _consent_covers(consent: dict, scope: str, value: object) -> bool:
    """True when the caller granted consent for `scope` (with an exact `value`
    for value-scoped scopes: name, language_preference, scheme_checked).

    `note` and `eligibility_answers` are group scopes: once the caller agrees to
    remembering "those details" they cover all later save attempts for that
    scope. Value scopes must match the exact value the caller agreed to.
    """
    granted = consent.get(scope)
    if scope in ("name", "language_preference", "scheme_checked"):
        return isinstance(granted, list) and value in granted
    return bool(granted)


def _caller_user_id(context: RunContext) -> str:
    """Extract the persistent caller ID from the session userdata."""
    try:
        data = context.userdata
    except Exception:
        return ""
    if isinstance(data, dict):
        uid = data.get("user_id")
        if isinstance(uid, str) and uid:
            return uid
    return ""


async def _discover_user_id(ctx: JobContext) -> str:
    """Read the persistent user_id the frontend attached to the caller's participant.

    The browser sends it via participant attributes, which the agent worker sees
    on the remote participant after connecting. If it's missing (older sessions,
    test harness, console mode) we fall back to a random ID so calls still work.
    """
    for _ in range(40):
        for participant in ctx.room.remote_participants.values():
            if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
                continue
            uid = (participant.attributes or {}).get("user_id")
            if uid:
                logger.info("identified caller: %s", uid)
                return uid
        await asyncio.sleep(0.25)
    logger.info("no caller user_id received, falling back to a random id")
    return str(uuid.uuid4())


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="moneygpt-voice")
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Per-session caller identity (persistent browser ID, see Day 4). The tools
    # in `Assistant` read it from `userdata` — it is filled in after connect.
    userdata = {"user_id": ""}

    # Cap LLM output. Voice replies are short, and LiveKit Inference has no
    # Groq-style per-minute token cap to guard against, so a modest cap simply
    # keeps replies brief and responsive for frequent short voice turns.
    max_output_tokens = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1024"))

    # Set up a voice AI pipeline using Murf Falcon, Gemini via LiveKit Inference,
    # Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3", language="multi"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # LiveKit Inference serves Gemini on LiveKit's infrastructure (no API key needed).
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=inference.LLM(
            model="google/gemini-3.5-flash-lite",
            extra_kwargs={"max_completion_tokens": max_output_tokens},
        ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
            voice="Anisha",
            locale="en-IN",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        # Per-call caller context (persistent user_id) exposed to tools via RunContext.userdata
        userdata=userdata,
    )

    def _on_metrics(ev) -> None:
        m = ev.metrics
        if m.type == "llm_metrics":
            model = m.metadata.model_name if m.metadata else "-"
            logger.info(
                "[LLM] metrics model=%s ttft=%.2fs duration=%.2fs prompt=%d "
                "completion=%d cached=%d total=%d cancelled=%s",
                model,
                m.ttft,
                m.duration,
                m.prompt_tokens,
                m.completion_tokens,
                m.prompt_cached_tokens,
                m.total_tokens,
                m.cancelled,
            )
        elif m.type == "tts_metrics":
            logger.info(
                "[TTS] metrics ttfb=%.2fs duration=%.2fs audio=%.2fs chars=%d "
                "cancelled=%s",
                m.ttfb,
                m.duration,
                m.audio_duration,
                m.characters_count,
                m.cancelled,
            )

    def _on_user_input(ev) -> None:
        if ev.is_final:
            logger.info("[STT] user said: %s", ev.transcript)

    def _on_error(ev) -> None:
        logger.error("[ERROR] source=%s error=%r", type(ev.source).__name__, ev.error)

    def _on_close(ev) -> None:
        logger.info("[CALL] session closed reason=%s error=%r", ev.reason, ev.error)

    session.on("metrics_collected", _on_metrics)
    session.on("user_input_transcribed", _on_user_input)
    session.on("error", _on_error)
    session.on("close", _on_close)

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()

    # The browser sends the persistent user_id as a participant attribute — read
    # it now that we are connected so the memory tools can identify this caller.
    userdata["user_id"] = await _discover_user_id(ctx)
    ctx.log_context_fields["user_id"] = userdata["user_id"]


if __name__ == "__main__":
    cli.run_app(server)
