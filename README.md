# Front Desk

A voice receptionist for a multi-site community recreation organisation.
You speak a question, it answers from the organisation's own data, takes a
message when it cannot answer, and hands anything serious to a person.

> **This is a portfolio prototype.** Kestrel Community Recreation is a
> fictional organisation and every centre, program and price in this
> repository is invented. It is not affiliated with, and does not represent,
> any real organisation.

## The problem

Community recreation organisations run dozens of sites — pools, gyms,
outside school hours care, early learning. Their websites typically publish
a phone number for every centre and opening hours for none of them.

So every routine question becomes a phone call: is the pool open, when does
the next swim lesson intake start, who do I talk to about vacation care.
That call lands on a desk where someone is already serving the queue in
front of them, and after hours it rings out.

Front Desk answers those calls. More usefully, it logs them — which gives
the organisation, for the first time, a record of what people actually ring
to ask. Three weeks of that data says which pages on the website to fix,
and fixing them stops the calls.

## What it does

- Finds the right centre from a name or a suburb, and asks when it's ambiguous
- Answers opening hours per facility, including seasonal pool closures
- Answers program questions: swim lessons, OSHC, gymnastics
- Takes a message when it cannot answer, reading the details back first
- Escalates anything involving a child's safety, an injury, a complaint or
  a refund straight to a person, with no attempt to resolve it
- Logs every turn and every message, viewable on an admin page

The sample data covers **13 centres**: seven recreation and aquatic centres,
four OSHC services, a gymnastics academy and a head office. Two of them are
in Muralong on purpose, so the agent has to ask which one the caller means.

## Making a call

![The caller page during a conversation](docs/caller.png)

Open `http://localhost:8000` in Chrome or Edge. Click the microphone once to
start talking. The button turns red and changes its label to show it's
listening, and an interim transcript appears on screen as you speak, so you
can see it's hearing you. Click again to send.
If it hears nothing, it says "I didn't catch that, try again" instead of
silently failing.

The reply is spoken by an ElevenLabs voice. Generated audio is cached on disk
by a hash of the text, so repeated phrases like the greeting cost nothing
after the first time. If ElevenLabs is not configured, times out (2 seconds)
or returns an error, the browser speaks the reply with its own voice
instead. The call carries on either way.

## The admin page

![The admin page showing messages, conversations and topics](docs/admin.png)

`http://localhost:8000/admin` shows three tables:

- **Messages taken**: reference, time, caller, callback number, centre, topic
- **Recent conversations**: what the caller said, what the agent replied,
  which tools it used, and whether the call was escalated
- **Topics by frequency**: what people ring about, most common first

The third table is the point of the project: it's the list of website pages
to fix.

## Architecture

    Browser page    mic capture, plays the reply         HTML + JS (Web Speech API)
    API             receives text, returns reply+audio   Python (FastAPI)
    Receptionist    decides what to do, calls tools      Python + Claude API
    Tools           five plain functions, no AI          Python
    Voice           turns the reply into speech          ElevenLabs, browser fallback
    Data            centres, programs, log, messages     SQLite

One turn: speech → text in the browser → `POST /api/turn` → the model is
given the conversation and five tools → it calls a tool → Python queries
SQLite → the model writes the reply → ElevenLabs speaks it (or the browser
does) → the turn is logged.

**Each turn has a limit of five model round trips.** If the model is still
calling tools after five rounds, the loop stops and the caller hears a fixed
"Let me take a message and have someone call you back." A confused model
can't loop forever, run up API costs, or leave a caller waiting in silence.
The limit is `_TOOL_CAP` in `app/receptionist.py`.

## The five tools

The model never touches the database directly. It can only call these five
functions in `app/tools.py`, which are plain Python with no AI in them. Each
one returns a result for the "not found" case rather than raising, so the
model is told "no such centre" and can say so.

| Tool | What it does |
| --- | --- |
| `find_centre(query, purpose)` | Matches a centre by name or suburb. Normalises speech ("the one at Muralong", "and" for "&"), returns up to five matches and flags when there were more. `purpose` filters out head office when the caller wants hours or programs. |
| `get_opening_hours(centre_id, facility, day)` | Hours for one facility on one day, `today` included. Tells apart "closed that day", "closed for the season" and "no such facility". |
| `get_program_info(program, centre_id)` | Programs at a centre matching a name, type or description: ages, price per session, details. An empty list means that centre doesn't offer it. |
| `take_message(name, phone, centre_id, topic, message)` | Saves the message to SQLite and returns a reference number. Called only after the details have been read back to the caller. |
| `escalate(reason)` | Ends the conversation and hands the call to a person. Nothing else runs after it. |

## Guardrails

**Grounding through tools.** Every opening hour, price and program detail
the agent states comes from a tool call against the database. There is no
other path from the model to a fact. If a tool returns nothing, the agent
says it doesn't know and offers to take a message.
*Why:* a receptionist that confidently gives the wrong pool hours is worse
than no receptionist. The caller drives there, finds it closed, and stops
trusting the service. Making the database the only source of facts is what
makes the answers trustworthy.

**Escalation, with the hand-off enforced in code.** The system prompt tells
the model to call `escalate()` straight away for anything about a child's
safety, an injury, a complaint or a refund. No clarifying questions first,
no looking anything up. Once it does, the code takes over, and the model
has no say in what happens next:

- the receptionist loop stops, and any other tool calls in the same
  response are dropped
- the caller hears a fixed hand-off line written in code, not text the
  model generated
- the turn is logged as escalated and flagged in the Escalated column on
  `/admin`
- the caller page disables the microphone, so the conversation can't
  continue with the agent

*Why:* these are the calls where a wrong word causes real harm or real
liability. An automated system shouldn't attempt them at all, and the
person who picks up shouldn't have to undo something it said. Putting the
hand-off in code means that once escalation starts, no prompt wording or
model mistake can make the agent keep talking.

**Minimal data collection.** The agent collects a name, a callback number,
which centre, and the reason for calling. Nothing else: no date of birth,
no address, no payment details, and nothing about any child. It won't
discuss an individual child at all, and takes a message instead.
*Why:* anything the system doesn't collect can't leak, be misused or need
deleting later. These four things are all a staff member needs to call
back. Information about children carries the highest duty of care, so the
safest amount to hold is none.

The agent also says it is automated in its first sentence, so no caller
thinks they're talking to a person. Data flows and retention are documented
in [retention.md](retention.md).

## Running it

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # then fill in your keys
    python -m data.seed
    uvicorn app.main:app --reload --port 8000

Then `http://localhost:8000` to make a call, `/admin` for the log.

To try the conversation without a microphone, `python -m app.cli` runs the
same receptionist in the terminal.

## Configuration

| Variable | Required | Notes |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Yes | — |
| `ANTHROPIC_MODEL` | Yes | Fast model; latency matters on a call |
| `ELEVENLABS_API_KEY` | No | Without it, the browser speaks the reply |
| `ELEVENLABS_VOICE_ID` | No | Use an Australian voice |
| `ELEVENLABS_MODEL` | No | Flash/Turbo: lower latency, lower cost |
| `DB_PATH` | Yes | Defaults to `data/frontdesk.db` |
| `AUDIO_CACHE_DIR` | No | Defaults to `audio_cache` |
| `N8N_WEBHOOK_URL` | No | Reserved for message delivery; not used yet |
| `N8N_SHARED_TOKEN` | No | Reserved for message delivery; not used yet |

## Tests

    pytest -v

The tools were tested before the model was wired up. The 17 tests in
`tests/test_tools.py` run against a seeded database.

## Known limits

- **Chrome and Edge only.** Speech capture uses the Web Speech API, which
  Firefox and Safari don't fully support.
- **Speech recognition mishears place names, particularly invented ones.**
  "Muralong" or "Kalindra" may come back as ordinary words. `find_centre`
  normalises what it can, but it can't recover a name the browser never
  heard correctly.
- **The data is fictional sample data**, not a real organisation's. The
  13 centres, hours, programs and prices are all invented.
- **No booking or payments.** It can't book a class, take payment or open a
  member account. That's deliberate: those need identity checks and payment
  handling, which a phone receptionist demo shouldn't attempt.
- **Messages are saved but not sent anywhere yet.** They're stored in SQLite
  and shown on `/admin`. Forwarding them to the right centre through an n8n
  webhook is planned but not built.
- **Deciding to escalate is the model's call.** The hand-off is enforced in
  code, but recognising that a call needs escalating relies on the model
  following the system prompt. No keyword check in code backs it up, so an
  unusually worded complaint could be missed.
- **Conversations are held in memory and not capped in length.** Each turn
  is limited to five round trips, but a conversation can have any number of
  turns. History lives in the server process, so it grows as the call goes
  on and is lost on restart. The call log in SQLite survives.
- **Grounding guarantees the facts, not the wording.** A correct fact can
  still be phrased ambiguously.

## Licence

MIT. The sample data is fictional and free to reuse.
