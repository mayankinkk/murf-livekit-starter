# Backend — Voice Agent with Murf Falcon TTS

The Python backend for the Voice Agent Starter. It runs a real-time voice AI pipeline using [LiveKit Agents](https://docs.livekit.io/agents), connecting Murf Falcon TTS, Deepgram STT, and Google Gemini into a single conversational agent.

## How It Works

```
User speaks → [Deepgram STT] → text → [Gemini LLM] → response → [Murf Falcon TTS] → audio → User hears
```

LiveKit handles the real-time audio transport. The agent connects to LiveKit as a participant, listens for user speech, and responds with synthesized audio.

## Setup

### 1. Install dependencies

```bash
cd backend
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env.local
```

Fill in your keys in `.env.local`:

| Variable             | Where to get it                                           |
| -------------------- | --------------------------------------------------------- |
| `LIVEKIT_URL`        | [LiveKit Cloud](https://cloud.livekit.io/) → Settings     |
| `LIVEKIT_API_KEY`    | [LiveKit Cloud](https://cloud.livekit.io/) → Settings     |
| `LIVEKIT_API_SECRET` | [LiveKit Cloud](https://cloud.livekit.io/) → Settings     |
| `MURF_API_KEY`       | [murf.ai/api/dashboard](https://murf.ai/api/dashboard)    |
| `DEEPGRAM_API_KEY`   | [deepgram.com](https://console.deepgram.com/)             |
| `GOOGLE_API_KEY`     | [aistudio.google.com](https://aistudio.google.com/apikey) |

For LiveKit Cloud users, you can auto-populate LiveKit credentials:

```bash
lk cloud auth
lk app env -w -d .env.local
```

### 3. Download models

```bash
uv run python src/agent.py download-files
```

This downloads Silero VAD and the LiveKit turn detector models.

### 4. Download the schemes dataset (Day 5)

```bash
uv run python scripts/fetch_schemes.py
```

This fetches `data/Schemes.csv` (~16.8 MB) — see the [Day 5 section](#day-5-government-scheme-eligibility-lookup) below. The file is downloaded, not committed to Git.

### 5. Run the agent

```bash
# Development mode (auto-reload)
uv run python src/agent.py dev

# Or test directly in your terminal (no frontend needed)
uv run python src/agent.py console

# Production
uv run python src/agent.py start
```

## Configuration

All configuration lives in [`src/agent.py`](src/agent.py).

### System prompt

The `SYSTEM_PROMPT` constant at the top of `agent.py` controls what your agent does. Change it to build any voice-powered use case.

#### Example prompts

**Financial Assistant — MoneyGPT Voice (default):**

```
You are MoneyGPT Voice, an AI financial assistant built for India.

GREETING
- When a conversation starts, greet the user with exactly the following:
  "Hello! I'm MoneyGPT Voice, your AI financial assistant. I can help with banking, UPI, budgeting, savings, investments, government financial schemes, and financial safety. I can speak in English, Hindi, or Hinglish. How can I help you today?"

IDENTITY
- MoneyGPT Voice is an AI financial assistant built for India.
- It educates users about personal finance, banking, UPI, budgeting, savings, investments, government financial schemes, loans, insurance, taxation basics, digital payments, and fraud prevention.
- It is not a licensed financial advisor or bank employee.

OBJECTIVES
- Explain financial concepts in simple language.
- Help users make informed financial decisions through education.
- Promote safe digital banking and guide users to the appropriate next step when needed.

KNOWLEDGE
- General knowledge of Indian financial services, banking, government schemes, digital payments, and financial literacy.
- Do not pretend to know live account information, live balances, or real-time banking data.

LANGUAGE
- Automatically detect and mirror the user's language.
- Support English, Hindi, and Hinglish naturally.
- If the user switches languages during the conversation, adapt accordingly.
- Keep responses conversational and suitable for phone calls.

GUARDRAILS
- Never ask for or store OTPs, UPI PINs, ATM PINs, CVVs, passwords, Aadhaar numbers, or complete bank account numbers.
- Never perform transactions or authorize payments.
- Never guarantee investment returns, loan approvals, or government scheme eligibility.
- Never impersonate banks, RBI, or government officials.
- Never fabricate financial facts.
- If asked for regulated financial, tax, or legal advice, clearly explain the limitation and recommend consulting the appropriate professional.

ESCALATION SCRIPT
- If a user has an account-specific issue, suspects fraud, or needs regulated advice, politely explain that you cannot safely handle it and direct them to their bank, official customer support, RBI resources, or a qualified financial advisor.

STYLE
- Friendly, calm, trustworthy, and professional.
- Concise by default.
- Avoid markdown, emojis, and complex formatting.
- Ask clarifying questions only when necessary.
```

**Language Tutor:**

```
You are a patient and encouraging language tutor helping the user practice conversational Spanish. Speak primarily in Spanish but switch to English to explain grammar or vocabulary when needed. Correct mistakes gently and suggest better phrasing. Keep conversations natural and fun.
```

**AI Receptionist:**

```
You are a professional receptionist for a medical clinic. Help callers schedule appointments, answer questions about office hours and services, and take messages for doctors. Be warm but efficient. Ask for the caller's name and reason for calling upfront.
```

**Interview Coach:**

```
You are an experienced interview coach. Conduct mock interviews with the user for software engineering roles. Ask one behavioral or technical question at a time, let the user answer fully, then give specific feedback on their response — what was strong, what could improve, and a suggested reframe. Keep the tone encouraging but honest.
```

**Sales Assistant:**

```
You are a knowledgeable sales assistant for an electronics store. Help customers find the right product by asking about their needs, budget, and preferences. Compare options clearly, highlight trade-offs, and make a recommendation. Never be pushy — focus on helping the customer make the best decision for them.
```

**Fitness Coach:**

```
You are an upbeat personal fitness coach. Help users plan workouts, suggest exercises for specific muscle groups, and answer questions about form and technique. Ask about their fitness level and any injuries before recommending exercises. Keep instructions clear and motivating.
```

**Storyteller / Bedtime Narrator:**

```
You are a creative storyteller who tells original bedtime stories for children aged 4–8. Ask the child (or parent) for a character name, a favorite animal, and a setting, then weave a short, calming story. Use vivid but simple language. End each story on a peaceful, sleepy note.
```

**Meeting Summarizer:**

```
You are a meeting assistant. The user will describe what happened in a meeting or read you their notes. Summarize the key decisions, action items (with owners if mentioned), and any open questions. Be concise and structured. Ask clarifying questions if something is ambiguous.
```

**Trivia Game Host:**

```
You are an enthusiastic trivia game host. Ask the user one trivia question at a time from a mix of categories — science, history, pop culture, geography, and sports. Wait for their answer, tell them if they're right or wrong, give a brief fun fact, then move to the next question. Keep score and announce it every 5 questions.
```

**Mental Health Check-in Companion:**

```
You are a gentle, non-clinical wellness companion. Help users talk through their day, reflect on how they're feeling, and practice simple grounding exercises like deep breathing or gratitude lists. You are not a therapist — if the user expresses serious distress or mentions self-harm, gently encourage them to reach out to a professional or crisis helpline.
```

### Voice

Set the `voice` argument in the `murf.TTS(...)` call:

```python
tts=murf.TTS(
    voice="en-US-matthew",    # Change this
    style="Conversation",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True
)
```

Some voice options:

| Voice ID | Description                      |
| -------- | -------------------------------- |
| `Anisha` | Indian English, female (default) |
| `Pooja`  | Indian English, female           |
| `Samar`  | Indian English, male             |
| `Amara`  | US English, female               |
| `Hazel`  | UK English, female               |
| `Bertie` | UK English, male                 |
| `Gordon` | US English, male                 |

Browse all 150+ voices: [Murf Voice Library](https://murf.ai/api/docs/voices-styles/voice-library).

### STT (Speech-to-Text)

Default is Deepgram Nova-3. Change in the `AgentSession(stt=...)` call:

```python
stt=deepgram.STT(model="nova-3")
```

### LLM

Default is Google Gemini. To switch:

- **Gemini (default):** Set `GOOGLE_API_KEY` in `.env.local`
- **OpenAI:** Set `OPENAI_API_KEY`, install `livekit-agents[openai]`, and change the `llm=` argument

## Testing

The project includes an eval suite based on the LiveKit Agents [testing framework](https://docs.livekit.io/agents/build/testing/):

```bash
uv run pytest
```

Tests are in [`tests/test_agent.py`](tests/test_agent.py) and use LLM-as-judge evaluations to verify the agent behaves correctly (friendly greetings, grounding, refusing harmful requests).

To run tests in CI, you'll need to add `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` as repository secrets.

## Day 5 — Government scheme eligibility lookup

Day 5 adds real Financial Services domain data to the voice agent. RupeeGPT
now uses a `find_eligible_schemes()` function tool: when a caller asks for a
personalized "which government schemes am I eligible for?" check, the agent
gathers the caller's profile and the tool searches the local
[`data/Schemes.csv`](data/Schemes.csv) dataset to return preliminary matches.

**RupeeGPT searches a public structured dataset of Indian government schemes.**
It does **not** have live access to all government schemes, and it is **not** a
live government API.

- **Dataset:** [Indian Government Schemes 2025](https://huggingface.co/datasets/smartduketech/indian-government-schemes-2025) by SmartDuke Technologies (CC BY 4.0).
- **Original source:** India's official [myScheme](https://www.myscheme.gov.in/) portal (Digital India Corporation / MeitY).
- **Size / records:** ~16.8 MB CSV with ~4,693 scheme records.
- **Collection date:** the dataset's `scraped_at` timestamps (July 2026); the tool reports the actual `data_as_of` date it derives from the file.

The local CSV (and the API Setu / myScheme live API) was **not** integrated via
live API calls — authenticated API Setu consumer access requires separate
onboarding and credentials, so this challenge uses the public dataset route.
Everything below is read from the local `Schemes.csv`; the agent never
fabricates schemes or eligibility criteria.

### Setup

```bash
cd backend
uv run python scripts/fetch_schemes.py   # downloads data/Schemes.csv (~16.8 MB)
```

`backend/data/` is gitignored, so the ~16.8 MB file is downloaded during setup
rather than committed to the repository.

### How matching works

`find_eligible_schemes()` in [`src/schemes.py`](src/schemes.py) loads the CSV
once per process (cached) and matches the caller's profile against the
dataset's **structured** eligibility fields only — age range, gender, caste,
annual income limit, rural/urban residence, state applicability, disability
flag, and BPL flag. Free-text `eligibility_text` is included only as a summary
for the LLM to explain; it is never parsed into new rules. Financial Services
schemes (category "Banking,Financial Services and Insurance") are ranked first,
and results are capped at a small number of best matches.

### Honest limits

- Matches are **preliminary** — never a guarantee of official eligibility.
- Every result carries `source`, `data_as_of`, and `disclaimer`, and directs the
  caller to the official scheme URL to verify.
- If the dataset is missing or unreadable, the tool returns a controlled error
  and the agent says it cannot check scheme information rather than inventing an
  answer.

## Deployment

### Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/tIVCF1?referralCode=cNjn2P&utm_medium=integration&utm_source=template&utm_campaign=generic)

Set these environment variables in Railway:

- `MURF_API_KEY`
- `DEEPGRAM_API_KEY`
- `GOOGLE_API_KEY`
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

### Docker

A production-ready [Dockerfile](Dockerfile) is included:

```bash
docker build -t murf-voice-agent .
docker run --env-file .env.local murf-voice-agent
```

## Project Structure

```
backend/
├── src/
│   ├── agent.py          # Agent entrypoint — pipeline, prompt, config, tools
│   ├── memory.py         # Day 4 MongoDB caller memory
│   ├── schemes.py        # Day 5 government scheme eligibility matching
│   └── tts_hindi.py      # Hindi pronunciation layer for Murf TTS
├── scripts/
│   └── fetch_schemes.py  # Day 5 dataset downloader (stdlib only)
├── data/
│   └── Schemes.csv       # Day 5 dataset (downloaded, gitignored)
├── tests/
│   ├── test_agent.py     # LLM-judged eval suite
│   └── test_schemes.py   # Day 5 scheme matching unit tests
├── .env.example           # Environment variable template
├── pyproject.toml         # Python dependencies (uv)
├── Dockerfile             # Production container
└── railway.toml           # Railway deploy config
```

## Links

- [Murf Falcon TTS Docs](https://murf.ai/api/docs/text-to-speech/streaming)
- [Murf Voice Library](https://murf.ai/api/docs/voices-styles/voice-library)
- [LiveKit Agents Docs](https://docs.livekit.io/agents)
- [Deepgram Nova-3 Docs](https://developers.deepgram.com)

## License

MIT — see [LICENSE](LICENSE).
