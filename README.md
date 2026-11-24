# Front Desk

[![CI](https://github.com/bytedawgdevops/front-desk-voice-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/bytedawgdevops/front-desk-voice-agent/actions/workflows/ci.yml)

Front Desk is a voice receptionist for a multi-site community recreation
organisation. You ask a question out loud; it answers from the
organisation's database, takes a message when it can't answer, and hands
anything serious to a person.

> **This is a portfolio demo.** Kestrel Community Recreation is a fictional
> organisation, and every centre, program and price in this repository is
> invented. It is not affiliated with any real organisation.

## The problem

Community recreation organisations run dozens of sites: pools, gyms,
outside school hours care. Their websites often list a phone number for
every centre and opening hours for none of them. So every routine question
becomes a phone call, which lands on a desk already serving a queue, or
rings out after hours.

Front Desk answers those calls and logs them. The log is the useful part:
it's a record of what people actually ring to ask, which tells the
organisation which web pages to fix.

## Architecture

    Browser     Web Speech API turns speech into text;     static/index.html
                plays the reply
    API         POST /api/turn, admin endpoints             app/main.py (FastAPI)
    Agent       Claude decides what to do, calls tools      app/receptionist.py (Anthropic API)
    Tools       five plain functions, no AI                 app/tools.py
    Voice       ElevenLabs, cached to disk;                 app/voice.py
                browser speech if it fails
    Data        centres, hours, programs, log, messages     SQLite (stdlib sqlite3)

One turn: the browser recognises speech and sends the text to
`POST /api/turn`. Claude gets the conversation and the five tools, calls
whichever it needs, and writes a reply from the results. The server turns
the reply into speech with ElevenLabs and logs the turn to SQLite.

Speech output is cached on disk by a hash of the reply text, so repeated
phrases are free after the first time. If ElevenLabs isn't configured,
errors, or takes longer than 2 seconds, the browser speaks the reply
instead. The call carries on either way.

The mic is click-to-talk: click once to start, and an interim transcript
appears on screen as you speak; click again to send.

Each turn is limited to five model round trips (`_TOOL_CAP`). After that the
agent offers to take a message, so a confused model can't loop.

## Seeded data

`python -m data.seed` creates the database with:

- **13 centres**: 7 recreation and aquatic centres, 4 OSHC services,
  1 gymnastics academy, 1 head office. Two are in Muralong on purpose, so
  the agent has to ask which one the caller means.
- **29 facilities** with **183** opening-hour rows. Two outdoor pools have
  seasonal closures.
- **48 programs**: 31 swim lesson programs, 12 OSHC sessions,
  5 gymnastics classes.

## The tools

The model can't touch the database or anything else directly. These five
functions in `app/tools.py` are all it can do. Each one returns a result for
"not found" instead of raising an error.

- `find_centre(query, purpose)`: **reads** centres by name or suburb and
  returns up to five matches. It can't see messages or the call log.
- `get_opening_hours(centre_id, facility, day)`: **reads** one facility's
  hours for one day, including seasonal closures. It's read-only.
- `get_program_info(program, centre_id)`: **reads** programs at one centre
  (ages, price, description). It's read-only.
- `take_message(name, phone, centre_id, topic, message)`: **inserts one
  row** into `messages`. It can't read, change or delete anything.
- `escalate(reason)`: returns a fixed value. The code then stops the turn,
  plays a hand-off line written in code, and disables the mic. It touches no
  data.

## Guardrails

- **Grounding through tools.** Every hour, price and program detail must
  come from a tool call. If the data doesn't answer the question, the agent
  says so and offers to take a message. A wrong answer about pool hours is
  worse than no answer.
- **Escalation.** A child's safety, an injury, a complaint or a refund goes
  straight to `escalate()`, with no attempt to resolve it. These calls are
  where a wrong word causes real harm. The model decides *when*; the code
  enforces what happens next.
- **Minimal data collection.** The agent asks only for a name, callback
  number, centre and reason, and never anything about a child. What isn't
  collected can't leak. The transcript is still stored in full; see
  [retention.md](retention.md).

## Setup

Requires Python 3.11.

    git clone https://github.com/bytedawgdevops/front-desk-voice-agent.git
    cd front-desk-voice-agent
    python3.11 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # add ANTHROPIC_API_KEY; ElevenLabs keys optional
    python -m data.seed
    uvicorn app.main:app --reload --port 8000

Open `http://localhost:8000`. To try the agent without a microphone, run
`python -m app.cli`.

Without ElevenLabs keys, the browser speaks the replies. `.env.example` also
has two `N8N_*` placeholders that no code uses yet.

**Re-running `python -m data.seed` deletes all messages and call logs.** It
drops and recreates every table.

## Browser support

**Chrome and Edge only.** Speech recognition uses the Web Speech API, which
Firefox and Safari don't fully support. In Chrome, recognition is done by
Google's servers.

## Admin page

`http://localhost:8000/admin` shows messages taken, recent conversations
(what the caller said, the reply, tools used, whether it was escalated), and
the most common topics.

**It has no authentication.** Neither does `/api/admin/*`. Anyone who can
reach the server can read every message and transcript. That's acceptable
only because uvicorn listens on localhost by default.

## Tests

    pytest -v

There are 17 tests in `tests/test_tools.py`, covering the tools against a
temporary seeded database, including an SQL injection test. They make no
API calls. CI runs them on every push and pull request, along with ruff,
bandit and pip-audit.

## Security

[SECURITY.md](SECURITY.md) explains how to report a problem.
[docs/threat-model.md](docs/threat-model.md) lists the threats, what's
mitigated, and what isn't.

## Known limits

- **Local only.** It's meant to run on your own machine, not be deployed.
- **No admin authentication.** See above.
- **No rate limiting.** `/api/turn` accepts unlimited requests, and each one
  can cost money in Claude and ElevenLabs calls.
- **No turn cap.** `_TOOL_CAP` limits the round trips within one turn, not
  the number of turns. A conversation can go on forever, and its history is
  held in memory, grows with every turn and is lost on restart.
- **No automatic data deletion.** Transcripts and messages stay until
  deleted by hand.
- **Speech recognition mishears invented place names**, like "Muralong".
- **Escalation depends on the model** noticing the topic; no keyword check
  in code backs it up.
- **No booking or payments**, by design.

## What I'd build next

These are designed but not built:

- **Telephony.** A real phone number, with call audio streamed to speech
  recognition and the reply streamed back, so callers don't need a browser.
- **Message delivery.** An automation layer that sends each saved message
  to the right centre's staff. It would run after the database write, so a
  failed delivery never loses a message.
