"""Outbound telephony agent for RupeeGPT — Day 6: scheme-deadline reminder.

This agent dials a person who was previously identified as a *preliminary*
match for an Indian government scheme (Day 5) and reminds them that an
application deadline is approaching (Financial Services track). It deliberately
reuses RupeeGPT's existing voice stack from ``src/agent.py``:

- **STT**: Deepgram Nova-3 (multi-language)
- **LLM**: Gemini via LiveKit Inference (``google/gemini-3.5-flash-lite``)
- **TTS**: Murf Falcon (Anisha, en-IN) with the same multilingual TTS node so
  Hindi/Hinglish scheme names are pronounced naturally.

The deadline values come from ``reminder.py``. The current scheme dataset has no
verified live government deadline, so the reminder is a clearly labelled
DEMO/TEST — see ``reminder.py`` and the prompt below. Never present it as a real
government deadline.

Run the worker (terminal 1):

    uv run python src/telephony/outbound/agent.py dev

Then dial from another terminal (terminal 2):

    uv run python src/telephony/outbound/dial.py --to <your-linphone-username>

The call goes out through the outbound SIP trunk named in
``LIVEKIT_SIP_OUTBOUND_TRUNK_ID`` (created in LiveKit Cloud, pointing at
sip.linphone.org, transport TLS, caller number ``sip:<your username>``).
"""

import asyncio
import json
import logging
import os
import time

from dotenv import load_dotenv
from livekit import api, rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    llm,
    room_io,
    tokenize,
)
from livekit.plugins import deepgram, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import tts_hindi
from telephony.outbound import reminder

logger = logging.getLogger("outbound-agent")

load_dotenv(".env.local")

# Required - created in LiveKit Cloud (SIP trunks -> Outbound). Never commit.
OUTBOUND_TRUNK_ID = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")

# Optional - a phone number to warm-transfer people to when they ask for a human.
TRANSFER_TO_NUMBER = os.getenv("TRANSFER_TO_NUMBER")

# The identity LiveKit gives the person we call. Used for transfers later.
CALLEE_IDENTITY = "phone-user"

# Must match AGENT_NAME in dial.py.
AGENT_NAME = "outbound-agent"


def build_system_prompt() -> str:
    """The control prompt for the Day 6 reminder call.

    Built at import time from the DEMO/TEST reminder in ``reminder.py`` so the
    LLM only ever talks about the one scheme and deadline we actually have.
    """
    scheme = reminder.scheme_name()
    deadline = reminder.deadline_human()
    return f"""You are RupeeGPT, calling a person who was previously identified as a
PRELIMINARY match for an Indian government scheme (Financial Services track).
This is an OUTBOUND reminder call about ONE scheme: {scheme}.

OPENING
- The opening greeting has ALREADY been spoken to the caller: "Namaste, this is
  RupeeGPT. I'm calling because a government scheme we previously discussed has
  an upcoming application deadline. If you'd rather not receive this call, just
  say so and I'll end the call."
- Do NOT repeat that greeting. Pause after it and let the caller respond;
  continue naturally from what they say.

WHAT YOU MAY SAY
- Discuss ONLY the scheme above and ONLY the deadline value provided:
  {deadline}.
- Treat the earlier match as PRELIMINARY. NEVER claim guaranteed eligibility,
  approval for, or a guaranteed place in any scheme.
- Do not invent scheme details, benefits, application steps, or dates. Share
  only what is in the preliminary match or the reminder above.
- Whenever you mention the deadline, make clear it is a DEMONSTRATION/TEST
  deadline, not a verified live government deadline, and advise verifying
  current details on the official scheme page before applying.

RULES
- If the caller says they do not want this call (e.g. "stop", "please don't
  call me", "not interested"), sincerely acknowledge it and end the call with
  the end_call tool. Do not try to persuade them to stay.
- If a voicemail or answering machine answers instead of a person, use the
  detected_answering_machine tool right away.
- If the caller asks for a real person, use the transfer_to_human tool.
- Never ask for or store sensitive data: bank or account numbers, UPI IDs,
  OTPs, PINs, passwords, card details, Aadhaar or PAN.
- Keep replies brief and conversational (1-3 short sentences). No markdown,
  emojis, or formatting."""


# The first thing the person hears when they pick up. Covers who is calling,
# why, and how to stop the call, all in one short, natural opening.
GREETING = (
    "Namaste, this is RupeeGPT. I'm calling because a government scheme we "
    "previously discussed has an upcoming application deadline. If you'd "
    "rather not receive this call, just say so and I'll end the call."
)


class OutboundAgent(Agent):
    def __init__(self, ctx: JobContext) -> None:
        super().__init__(instructions=build_system_prompt())
        self.ctx = ctx
        self._user_language: tts_hindi.Language = "english"

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        """Track the caller's language so the TTS node pronounces terms right."""
        text = (new_message.text_content if new_message else None) or ""
        self._user_language = tts_hindi.detect_language(text)
        logger.info("[LANG] user language=%s input=%s", self._user_language, text[:120])

    async def tts_node(self, text, model_settings):
        """TTS node identical to src/agent.py: rewrite known Hindi/Indian terms
        to Devanagari so the en-IN Murf voice pronounces them naturally. Safe to
        apply for English callers too (whitelist passes English through)."""
        language = self._tts_language()
        frames = 0
        first_audio_at: float | None = None
        started_at = time.perf_counter()

        async def _tracked():
            async for part in tts_hindi.stream_for_tts(text, language=language):
                yield part

        try:
            async for frame in Agent.default.tts_node(self, _tracked(), model_settings):
                frames += 1
                if first_audio_at is None:
                    first_audio_at = time.perf_counter() - started_at
                yield frame
            logger.info(
                "[TTS] complete language=%s frames=%d first_audio=%.2fs duration=%.2fs",
                language,
                frames,
                first_audio_at or 0.0,
                time.perf_counter() - started_at,
            )
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

    @function_tool
    async def transfer_to_human(self, context: RunContext) -> str:
        """Transfer the caller to a human colleague.

        Use this when they explicitly ask for a real person, or when you cannot
        help them with their request.
        """
        if not TRANSFER_TO_NUMBER:
            return "Transfers are not available on this line. Offer to have someone call back instead."

        # Tell them before transferring - the SIP transfer cuts off the audio.
        await context.session.generate_reply(
            instructions="Tell them you're connecting them to a colleague now."
        )

        logger.info("transferring call to %s", TRANSFER_TO_NUMBER)
        try:
            await self.ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=self.ctx.room.name,
                    participant_identity=CALLEE_IDENTITY,
                    transfer_to=f"tel:{TRANSFER_TO_NUMBER}",
                    play_dialtone=True,
                )
            )
        except Exception:
            logger.exception("transfer failed")
            return "The transfer did not go through. Apologize and offer a call back."

        return "Transferred."

    @function_tool
    async def detected_answering_machine(self, context: RunContext) -> str:
        """Hang up because the call reached a voicemail or answering machine.

        Use this as soon as you hear a recorded greeting rather than a live person.
        """
        logger.info("answering machine detected - hanging up")
        await self._hangup()
        return "Call ended."

    @function_tool
    async def end_call(self, context: RunContext) -> str:
        """Hang up the call.

        Use this once the conversation is finished (including any time the
        caller asked to stop receiving calls) and you have acknowledged it.
        """
        await context.session.generate_reply(
            instructions="Thank them for their time and say a short goodbye."
        )

        logger.info("ending call")
        await self._hangup()
        return "Call ended."

    async def _hangup(self) -> None:
        """Delete the room, which drops the SIP leg and ends the phone call."""
        await self.ctx.api.room.delete_room(
            api.DeleteRoomRequest(room=self.ctx.room.name)
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


def phone_number_from_metadata(ctx: JobContext) -> str | None:
    """Read the target to dial out of the dispatch metadata set by dial.py."""
    metadata = ctx.job.metadata
    if not metadata:
        return None
    try:
        parsed = json.loads(metadata)
        if isinstance(parsed, dict):
            value = parsed.get("phone_number")
            return value.strip() if isinstance(value, str) and value.strip() else None
    except json.JSONDecodeError:
        # Allow a bare number/username as metadata too, for quick `lk dispatch` tests.
        value = metadata.strip()
        return value or None
    return None


def _on_metrics(ev) -> None:
    m = ev.metrics
    if m.type == "llm_metrics":
        model = m.metadata.model_name if m.metadata else "-"
        logger.info(
            "[LLM] metrics model=%s ttft=%.2fs duration=%.2fs prompt=%d completion=%d",
            model,
            m.ttft,
            m.duration,
            m.prompt_tokens,
            m.completion_tokens,
        )
    elif m.type == "tts_metrics":
        logger.info(
            "[TTS] metrics ttfb=%.2fs duration=%.2fs audio=%.2fs chars=%d",
            m.ttfb,
            m.duration,
            m.audio_duration,
            m.characters_count,
        )


def _on_user_input(ev) -> None:
    if ev.is_final:
        logger.info("[STT] user said: %s", ev.transcript)


def _on_error(ev) -> None:
    logger.error("[ERROR] source=%s error=%r", type(ev.source).__name__, ev.error)


def _on_close(ev) -> None:
    logger.info("[CALL] session closed reason=%s error=%r", ev.reason, ev.error)


@server.rtc_session(agent_name=AGENT_NAME)
async def outbound_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    phone_number = phone_number_from_metadata(ctx)
    if not phone_number:
        logger.error(
            "no phone number in job metadata - dispatch with "
            '{"phone_number": "+15551234567"}'
        )
        ctx.shutdown()
        return

    if not OUTBOUND_TRUNK_ID:
        logger.error("LIVEKIT_SIP_OUTBOUND_TRUNK_ID is not set - cannot place calls")
        ctx.shutdown()
        return

    await ctx.connect()

    # Same voice pipeline as src/agent.py - Deepgram STT -> Gemini LLM (LiveKit
    # Inference) -> Murf Falcon TTS, with the multilingual TTS rewrite on top.
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=inference_llm(),
        tts=murf.TTS(
            voice="Anisha",
            locale="en-IN",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    session.on("metrics_collected", _on_metrics)
    session.on("user_input_transcribed", _on_user_input)
    session.on("error", _on_error)
    session.on("close", _on_close)

    # Start the session while the phone is still ringing so the models are warm
    # by the time somebody picks up.
    session_started = asyncio.create_task(
        session.start(
            agent=OutboundAgent(ctx),
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    # BVCTelephony is tuned for the narrow frequency range of phone audio.
                    noise_cancellation=lambda params: (
                        noise_cancellation.BVCTelephony()
                        if params.participant.kind
                        == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                        else noise_cancellation.BVC()
                    ),
                ),
            ),
        )
    )

    logger.info("dialing %s through trunk %s", phone_number, OUTBOUND_TRUNK_ID)
    try:
        # wait_until_answered means this returns once the call connects - if the
        # number is busy, declines, or never answers, it raises instead.
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=OUTBOUND_TRUNK_ID,
                sip_call_to=phone_number,
                participant_identity=CALLEE_IDENTITY,
                participant_name="Phone user",
                wait_until_answered=True,
            )
        )
    except api.TwirpError as e:
        logger.error(
            "call to %s did not connect: %s (%s)",
            phone_number,
            e.message,
            e.metadata.get("sip_status"),
        )
        session_started.cancel()
        ctx.shutdown()
        return

    await session_started

    # Speak first - they just picked up an unexpected call and won't say anything.
    await session.say(GREETING, allow_interruptions=True)


def inference_llm():
    """Gemini served by LiveKit Inference - matches src/agent.py (no API key)."""
    from livekit.agents import inference

    max_output_tokens = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1024"))
    return inference.LLM(
        model="google/gemini-3.5-flash-lite",
        extra_kwargs={"max_completion_tokens": max_output_tokens},
    )


if __name__ == "__main__":
    cli.run_app(server)
