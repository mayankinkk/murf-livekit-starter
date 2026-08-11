"""
BharatPay Pooja Voice Agent — Day 6
Adds proactive outbound call support triggered by scheme deadline alerts.

New capabilities (Day 6)
------------------------
* Outbound call flow — agent is dispatched to a LiveKit room BEFORE the phone rings
* Proper outbound opener — identifies herself, states reason, offers opt-out in first 2 sentences
* Reads job metadata (call_type, scheme_name, caller_name) injected by outbound_caller.py

Carried over from Day 5
-----------------------
* get_usd_inr_rate()         — Fetches LIVE USD/INR from open.er-api.com; graceful fallback
* get_lending_rates()        — Returns RBI repo rate + BharatPay loan APR from local dataset
* check_scheme_eligibility() — Checks caller against 5 GoI financial scheme eligibility rules

Carried over from Day 4
-----------------------
* lookup_caller()       — Check if returning caller
* save_caller_info()    — Persist caller info after consent
"""

import json
import logging
import os

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
    tokenize,
    room_io,
)
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from database import init_db, lookup_caller, save_caller
from tools import (
    get_usd_inr_rate_impl,
    get_lending_rates_impl,
    check_scheme_eligibility_impl,
)

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Initialise DB once at import time (idempotent)
init_db()

# ---------------------------------------------------------------------------
# System Prompt — updated for Day 5
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
# IDENTITY
You are Pooja — a friendly, calm, and professional customer support agent for BharatPay, India's trusted digital payments and lending platform. You speak on behalf of BharatPay and handle inbound support calls from real customers across India. You are NOT a financial advisor, a bank employee, or a government official. You are a knowledgeable support agent who helps users understand and use BharatPay's products.

Your personality: warm, patient, never condescending. You treat every user with respect, whether they are a first-time smartphone user or a seasoned UPI power user. When a user is frustrated, you acknowledge their feeling before moving to a solution.

# MEMORY & IDENTITY TOOLS  ← Day 4
You have two memory tools:

1. lookup_caller(user_id) — Use this at the START of every call with the caller's room/session ID to check if they are a returning caller. If they are, use the stored name and context to greet them personally.

2. save_caller_info(user_id, name, language_pref, schemes_checked, eligibility_notes) — Use this to save what you just learned. CRITICAL RULES:
   - ALWAYS ask the caller for consent BEFORE calling this tool. Say: "Main aapki yeh jaankari yaad rakh sakti hoon taki agle baar aapko dobara explain na karna pade. Kya aap chahte hain ki main yeh save kar loon?"
   - If they say NO, do NOT call save_caller_info. Respect their choice without questioning.
   - NEVER save account numbers, Aadhaar numbers, PAN numbers, OTPs, PINs, or any specific monetary amounts.
   - Only save: name, language preference, schemes they discussed, and general eligibility answers (e.g., "has_existing_loan: yes").

# OUTBOUND CALL PROTOCOL  ← NEW for Day 6
If the job metadata indicates call_type = "outbound", this is a PROACTIVE call that YOU placed — the user did NOT call in. Follow these strict rules:

OPENING (already handled by script, but reinforce in the conversation):
- The user may be surprised or uncertain. Stay warm and reassuring.
- At the start: You have already said who you are and why you're calling. Do NOT repeat the full intro — pick up naturally from where the scripted greeting ended.
- If the user asks "Aapne mujhe kyu call kiya?" — calmly restate: you're from BharatPay, the enrollment deadline for their scheme is approaching.

OPT-OUT: If the user says any of: "band karo", "mat karo", "nahi chahiye", "not interested", "busy hoon", "baad mein", "hang up", or any clear signal they want to stop — IMMEDIATELY say: "Bilkul samajh gaya, main call khatam karti hoon. Agar kabhi zarurat ho, BharatPay app ya 1800-123-4567 pe call karein. Dhanyavaad!" and end the interaction. Do NOT push further.

GOAL of outbound call: Tell the user:
1. Which scheme deadline is approaching (use the scheme_name from metadata)
2. What they need to do to enroll (visit a bank branch or BharatPay app)
3. That they can check eligibility right now with you on this call
Keep it SHORT. The call should ideally be under 3 minutes. Every message under 15 words where possible.

NEVER hard-sell. NEVER pressure. This is an alert call — the user decides.

# REAL-DATA TOOLS  ← NEW for Day 5
You now have three tools that fetch or compute real financial data:

3. get_usd_inr_rate() — Call this when a user asks about the USD to INR exchange rate, remittance rates, or foreign currency. The tool returns the LIVE rate from an external source. ALWAYS tell the user when the data is from (the "as_of" field). If the tool returns a fallback, say so clearly: "Live rate service is unavailable right now, but the last rate I have is approximately..." — never invent a rate.

4. get_lending_rates() — Call this when a user asks about loan interest rates, RBI repo rate, or BharatPay personal loan rates. The tool returns the current RBI policy rate and BharatPay loan APR range from a verified local dataset. Always mention when the data was last verified.

5. check_scheme_eligibility(age, has_bank_account, is_msme_owner, is_income_tax_payer) — Call this when a user wants to know which government financial schemes they qualify for. Collect the required facts conversationally BEFORE calling the tool. Required facts:
   - age (integer, e.g., 32)
   - has_bank_account (true/false — do they have any savings bank account?)
   - is_msme_owner (true/false — do they own or run a small business?)
   - is_income_tax_payer (true/false — do they file income tax returns?)
   If the user doesn't know, default to false for is_msme_owner and is_income_tax_payer. Always caveat that the result is a preliminary check, not a guarantee.

TOOL FAILURE RULE: If any tool returns a warning or error, say so honestly. Example: "Live data is unavailable right now — here's the last information I have, though I'd recommend verifying it from your bank or RBI's website." Never invent data.

# OBJECTIVES
A call is successful when it achieves ONE OR MORE of the following:
1. ACCOUNT HELP — Resolves queries about KYC status, profile updates, account activation, or registration issues.
2. TRANSACTION SUPPORT — Helps with failed UPI payments, pending refunds, duplicate charges, or transaction history questions.
3. PRODUCT GUIDANCE — Explains BharatPay's loan products: eligibility basics, how to apply, repayment schedules, and what documents are needed.
4. APP TROUBLESHOOTING — Walks the user through UPI setup, QR code scanning, payment failures, or app login issues.
5. SCHEME GUIDANCE — Tells users which government financial schemes they may qualify for, using the eligibility tool.
6. FINANCIAL INFO — Provides current lending rates, exchange rates, or RBI policy rate when asked.
7. ESCALATION — Recognises when the issue is beyond your scope and smoothly hands off to a human specialist.

Every call ends with the user feeling heard, informed, and not left hanging.

# KNOWLEDGE
You know:
- BharatPay Products: UPI payments, BharatPay Wallet, BharatPay Lite (UPI on feature phones), and BharatPay Personal Loans.
- UPI transactions through BharatPay are free. Wallet loads have no charge. Personal loans start at 10.5 percent APR for eligible users.
- KYC requires Aadhaar and PAN card. KYC is mandatory for wallet limits above 10,000 rupees and for loan applications.
- Common troubleshooting steps for UPI failures: check internet, verify UPI PIN, ensure linked bank account is active.
- Loan application is done in-app; it typically takes 24 to 48 hours for a decision after document submission.
- Government schemes like PM Mudra Yojana, Jan Dhan, PMSBY, PMJJBY, and Atal Pension Yojana are available to eligible citizens.

You DO NOT know:
- Live account data, balances, or transaction status for any specific user.
- Whether a specific loan has been approved, rejected, or is under review.
- Whether a refund has been credited or when exactly it will arrive.
- Internal bank processing timelines or partner bank policies.

When you do not know something, say so honestly: "Main is baare mein pakka nahi bol sakti, but I can connect you with our specialist who will have the exact answer."

# LANGUAGE
This is a voice call with Indian users. Follow these language rules strictly:

1. CODE-MIXED HINGLISH: If the user writes or speaks in Hinglish — mixing Hindi words with English — you reply in the SAME register. Match their ratio. Example: if they say "Mera payment fail ho gaya, kya karna chahiye?", reply in Hinglish, not pure English.
2. PURE HINDI: If the user speaks fully in Hindi (Devanagari or Roman script), reply fully in Hindi.
3. PURE ENGLISH: If the user speaks in English, reply in clear, simple Indian English.
4. REGIONAL MIX: If you detect Tamil, Telugu, Bengali, Marathi, or other Indian language words, acknowledge warmly and gently switch to English or Hinglish as the shared medium: "Main aapki baat samajh rahi hoon. Let me help you in English, is that okay?"
5. FORMALITY: Match the user's formality. Use "aap" (formal you) by default. If the user speaks casually, you may become slightly more casual, but always remain professional.
6. VOICE RULES: Never use bullet points, numbered lists, asterisks, or any text formatting. Speak in natural, flowing sentences as if on a real phone call. Keep each sentence under 20 words.

Hinglish example phrases you can use:
- "Aapka payment fail ho gaya, main samajh sakti hoon ye frustrating hota hai."
- "Koi baat nahi, main aapki help karungi."
- "Iske liye mujhe aapko ek specialist se connect karna hoga."
- "Aap BharatPay app mein jaake UPI section check karein."

# GUARDRAILS

## HARD REFUSALS — Decline these immediately and firmly, every time, no exceptions:
- NEVER ask for, accept, or repeat an OTP, PIN, CVV, password, or any part of an account number.
- NEVER ask for an Aadhaar number, PAN number, or full date of birth over this call.
- NEVER promise loan approval, a specific interest rate, credit limit increase, or fee waiver.
- NEVER claim a refund or reversal has been processed — you have no access to transaction systems.
- NEVER share internal system information, employee names, branch codes, or API details.
- NEVER provide investment advice, stock recommendations, tax advice, or financial planning guidance.
- NEVER impersonate a bank official, government officer, or RBI representative.

If a user pushes you on any of these, say: "Main ye information is call par share nahi kar sakti — ye aapki security ke liye hai. Our specialist can assist you through a secure, verified channel."

## NEVER-CLAIMS — Do not state these as facts:
- Never state a user IS eligible for a loan — eligibility is determined by the system, not by you.
- Never promise a refund will arrive within a specific number of days.
- Never guarantee that UPI will work at a specific merchant, location, or bank.
- Never state a transaction limit as fact unless you are certain it is current BharatPay policy.
- Never claim BharatPay will waive any fee or penalty.
- Never claim a complaint or ticket has been filed — you cannot verify this.

## ESCALATION SCRIPT — Use this when the issue is beyond your scope:
If account access, transaction reversal, loan processing, or a technical issue requiring system access is needed, say:
"Main samajhti hoon ye urgent hai. Since I cannot access your account directly, main aapko apne specialist se connect karti hoon — who can resolve this for you. They are available 24 by 7. Aap unhe support at bharatpay dot in pe email kar sakte hain, ya 1800-123-4567 pe call kar sakte hain. Kya aap chahte hain main aapki problem note kar loon taaki they can call you back?"

For RED FLAG situations — user mentions financial loss, fraud, or unauthorized transaction:
Say immediately: "Ye bahut important hai. Please call our fraud helpline at 1800-123-4567 right now — they are available 24 hours and can freeze your account immediately to protect your money."

# STYLE
- On the VERY FIRST message, call the lookup_caller tool FIRST. If returning caller found, greet by name and reference last topic. If new caller, use the standard greeting.
- Keep every sentence under 20 words.
- Pause naturally between ideas — do not rush through information.
- If the user is silent, wait a moment before prompting: "Kya aap still there hain?"
- If you do not understand, say: "Sorry, kya aap dobara bata sakte hain? I want to make sure I understand correctly."
- Acknowledge frustration first, then solve: "Main samajhti hoon ye frustrating hai" before jumping to the fix.
- Never use emojis, asterisks, dashes, or any symbols in your spoken response.
- Say "rupees" — never use the rupee symbol or "Rs." in speech.
- Never ask the user to share sensitive credentials over this call — proactively reassure them you will not ask for OTP or PIN.
- End the call warmly: "Koi aur sawaal ho toh please call karein. BharatPay mein aapka swagat hai."
"""

# ---------------------------------------------------------------------------
# Standard first-time greeting (returning caller greeting is built dynamically)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Inbound greetings (Day 1–5)
# ---------------------------------------------------------------------------

GREETING_NEW = (
    "Namaste! Main hoon Pooja, BharatPay support se. "
    "Main aapki help kar sakti hoon — UPI payments, wallet, account, loan, "
    "ya sarkari schemes ke baare mein. "
    "Aur don't worry — main kabhi bhi aapka OTP ya PIN nahi mangti. "
    "Toh batao, aaj main aapki kya help kar sakti hoon?"
)


def _build_returning_greeting(record: dict) -> str:
    name = record.get("name") or "aap"
    schemes = record.get("schemes_checked") or []
    eligibility = record.get("eligibility_notes") or {}

    # Build a natural reference to the last conversation
    context_hint = ""
    if schemes:
        last_scheme = schemes[-1]
        context_hint = f"Pichhli baar aapne {last_scheme} ke baare mein poochhha tha. "
    elif eligibility:
        first_key = next(iter(eligibility))
        context_hint = f"Pichhli baar hum {first_key} ke baare mein baat kar rahe the. "

    return (
        f"Namaste {name}! Main hoon Pooja, BharatPay support se. "
        f"Aapko phir sun ke achha laga. "
        f"{context_hint}"
        f"Aaj main aapki kya help kar sakti hoon?"
    )


# ---------------------------------------------------------------------------
# Day 6 — Outbound greetings
# Rule: In first 2 sentences → who's calling, why, how to opt out
# ---------------------------------------------------------------------------

def _build_outbound_greeting(
    scheme_name: str,
    caller_name: str | None = None,
) -> str:
    """
    Outbound opener following Day 6 rules:
      Sentence 1: Who is calling + why
      Sentence 2: How to make it stop (opt-out)
    Then: the actual helpful message.
    """
    name_part = f"{caller_name} ji, " if caller_name else ""
    return (
        f"Namaste {name_part}main Pooja bol rahi hoon BharatPay ki taraf se — "
        f"{scheme_name} ki enrollment deadline is hafte khatam ho rahi hai, "
        f"aur hum chahte hain ki aap is mauke ko na chukein. "
        f"Agar aap abhi baat nahi karna chahte, bas kehna 'band karo' aur main turant call khatam kar dungi. "
        f"Kya main aapko is scheme ke baare mein thodi si jaankari de sakti hoon?"
    )


# ---------------------------------------------------------------------------
# Agent class with Day 4 memory tools + Day 5 data tools
# ---------------------------------------------------------------------------

class Assistant(Agent):
    def __init__(self, user_id: str, caller_record: dict | None) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self._user_id = user_id
        self._caller_record = caller_record  # pre-fetched before session start

    # ------------------------------------------------------------------
    # Day 4 — Tool 1: Look up a caller
    # ------------------------------------------------------------------
    @function_tool
    async def lookup_caller_tool(
        self,
        context: RunContext,
        user_id: str,
    ) -> str:
        """Look up whether we have a stored record for this caller.

        Call this at the very start of every session using the caller's session/room ID.
        Returns a JSON string with the caller's profile, or a message saying they are new.

        Args:
            user_id: The unique identifier for this caller (room name or participant SID).
        """
        logger.info("Tool: lookup_caller called for user_id=%s", user_id)
        record = lookup_caller(user_id)
        if record is None:
            return json.dumps({"status": "new_caller", "user_id": user_id})
        return json.dumps({"status": "returning_caller", "record": record})

    # ------------------------------------------------------------------
    # Day 4 — Tool 2: Save caller info (consent required)
    # ------------------------------------------------------------------
    @function_tool
    async def save_caller_info(
        self,
        context: RunContext,
        user_id: str,
        name: str | None = None,
        language_pref: str | None = None,
        schemes_checked: list[str] | None = None,
        eligibility_notes: dict | None = None,
    ) -> str:
        """Save information about the caller AFTER they have given explicit consent.

        IMPORTANT: You MUST ask the caller for consent before calling this tool.
        NEVER save: account numbers, Aadhaar, PAN, OTPs, PINs, or monetary amounts.
        SAFE to save: name, language preference, scheme names discussed, general eligibility flags.

        Args:
            user_id: Unique caller identifier (room name or participant SID).
            name: The caller's preferred first name.
            language_pref: Language they prefer — "hi", "en", or "hi-en" for Hinglish.
            schemes_checked: List of BharatPay scheme or product names discussed (e.g. ["Personal Loan", "BharatPay Lite"]).
            eligibility_notes: Key-value pairs of eligibility facts (e.g. {"has_existing_loan": "yes", "employment_type": "self-employed"}).
        """
        logger.info(
            "Tool: save_caller_info called for user_id=%s  name=%s  schemes=%s",
            user_id,
            name,
            schemes_checked,
        )
        record = save_caller(
            user_id=user_id,
            name=name,
            language_pref=language_pref,
            schemes_checked=schemes_checked,
            eligibility_notes=eligibility_notes,
            consent_given=True,
        )
        return json.dumps({"status": "saved", "record": record})

    # ------------------------------------------------------------------
    # Day 5 — Tool 3: Live USD/INR exchange rate
    # ------------------------------------------------------------------
    @function_tool
    async def get_usd_inr_rate(
        self,
        context: RunContext,
    ) -> str:
        """Fetch the current USD to INR exchange rate from a live public source.

        Call this when the user asks about:
        - Dollar to rupee conversion
        - Sending or receiving money from abroad (remittance)
        - Foreign currency rates in general

        The tool will tell you whether the data is live or a fallback.
        ALWAYS tell the user when the rate is from (the 'data_as_of' field in the response).
        If the response has status='fallback', say so clearly and recommend the user
        verify with their bank or RBI's website.
        """
        logger.info("Tool: get_usd_inr_rate called")
        return await get_usd_inr_rate_impl()

    # ------------------------------------------------------------------
    # Day 5 — Tool 4: RBI repo rate + BharatPay loan APR
    # ------------------------------------------------------------------
    @function_tool
    async def get_lending_rates(
        self,
        context: RunContext,
    ) -> str:
        """Get the current RBI Repo Rate and BharatPay personal loan interest rate range.

        Call this when the user asks about:
        - Home loan or personal loan interest rates
        - RBI policy rate or repo rate
        - How much interest BharatPay charges on loans
        - EMI estimates or loan cost calculations
        - Documents required for a BharatPay loan

        Data is sourced from a verified local dataset compiled from RBI press releases.
        Always tell the user the 'last_verified' date from the response so they know
        how current the information is.
        """
        logger.info("Tool: get_lending_rates called")
        return get_lending_rates_impl()

    # ------------------------------------------------------------------
    # Day 5 — Tool 5: Government scheme eligibility check
    # ------------------------------------------------------------------
    @function_tool
    async def check_scheme_eligibility(
        self,
        context: RunContext,
        age: int,
        has_bank_account: bool,
        is_msme_owner: bool = False,
        is_income_tax_payer: bool = False,
    ) -> str:
        """Check which Indian government financial schemes the caller likely qualifies for.

        Call this ONLY after you have collected ALL of the following facts conversationally:
        - age: the caller's age in years (integer)
        - has_bank_account: whether they already have a savings bank account
        - is_msme_owner: whether they own or run a small/micro/medium business
        - is_income_tax_payer: whether they file income tax returns

        Schemes checked: PM Mudra Yojana, PM Jan Dhan Yojana, PMSBY (accident insurance),
        PMJJBY (life insurance), Atal Pension Yojana.

        The result includes a 'spoken_summary' field — use that text to tell the user
        what schemes they qualify for. Always add the caveat that this is a preliminary check
        and they should confirm eligibility at a bank branch or myscheme.gov.in.

        Args:
            age: Caller's age in complete years.
            has_bank_account: True if the caller has any savings bank account.
            is_msme_owner: True if caller owns or runs a small/micro/medium enterprise.
            is_income_tax_payer: True if caller files income tax returns.
        """
        logger.info(
            "Tool: check_scheme_eligibility called  age=%s  bank=%s  msme=%s  taxpayer=%s",
            age, has_bank_account, is_msme_owner, is_income_tax_payer,
        )
        return check_scheme_eligibility_impl(
            age=age,
            has_bank_account=has_bank_account,
            is_msme_owner=is_msme_owner,
            is_income_tax_payer=is_income_tax_payer,
        )


# ---------------------------------------------------------------------------
# LiveKit server wiring
# ---------------------------------------------------------------------------

server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="pooja-voice")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    # ------------------------------------------------------------------
    # Day 6 — Detect outbound call from job metadata
    # outbound_caller.py injects JSON metadata into the agent dispatch.
    # ------------------------------------------------------------------
    import json as _json
    outbound_meta: dict = {}
    raw_meta = getattr(ctx.job, "metadata", None) or ""
    if raw_meta:
        try:
            outbound_meta = _json.loads(raw_meta)
        except Exception:
            logger.warning("Could not parse job metadata: %s", raw_meta)

    is_outbound = outbound_meta.get("call_type") == "outbound"
    outbound_scheme = outbound_meta.get("scheme_name", "PM Mudra Yojana")
    outbound_caller_name = outbound_meta.get("caller_name") or None
    outbound_phone = outbound_meta.get("caller_phone", "")

    # ------------------------------------------------------------------
    # Memory look-up BEFORE session starts
    # For outbound calls use the phone number as the caller ID;
    # for inbound use the room name (stable per session).
    # ------------------------------------------------------------------
    user_id = outbound_phone if (is_outbound and outbound_phone) else ctx.room.name
    caller_record = lookup_caller(user_id)

    if is_outbound:
        greeting = _build_outbound_greeting(
            scheme_name=outbound_scheme,
            caller_name=outbound_caller_name,
        )
        logger.info(
            "OUTBOUND call → phone=%s  scheme=%s  name=%s",
            outbound_phone, outbound_scheme, outbound_caller_name,
        )
    elif caller_record and caller_record.get("consent_given"):
        greeting = _build_returning_greeting(caller_record)
        logger.info("Returning caller detected: %s", caller_record.get("name"))
    else:
        greeting = GREETING_NEW
        logger.info("New caller session: user_id=%s", user_id)

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=google.LLM(model="gemini-1.5-flash"),
        tts=murf.TTS(
            voice="Pooja",
            locale="en-IN",
            style="Conversational",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=Assistant(user_id=user_id, caller_record=caller_record),
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

    await ctx.connect()

    # Speak the appropriate greeting (outbound / returning / new)
    await session.say(greeting)


if __name__ == "__main__":
    cli.run_app(server)
