# Data handling and retention

Front Desk is a demo. Every centre, program and price in it is fictional,
but anything a person says to it is real speech, and some of it leaves the
machine. This page says what is stored, where it goes, and how long it
stays. The data flows below match the PII row in
[docs/threat-model.md](docs/threat-model.md), which is the reference.

## What is stored

Everything is stored in one SQLite file: `data/frontdesk.db` by default, or
wherever `DB_PATH` points.

| Table | What it holds | Written by |
| --- | --- | --- |
| `call_log` | The **full caller transcript and full agent reply, verbatim, for every turn**: two rows per turn, plus the names of the tools called and whether the turn was escalated. Tool arguments are not stored. | `log_turn` in `app/db.py` |
| `messages` | Name, callback number, centre, topic and message text for each message taken | `take_message` in `app/tools.py` |

The agent is instructed to ask only for a name, callback number, centre and
reason for calling, and never for a date of birth, address, payment details
or anything about a child. That rule limits what the agent **asks for**, not
what gets stored. `call_log` keeps every word of the transcript, so anything
a caller volunteers is stored, including details about a child.

Generated speech is also cached as MP3 files in `audio_cache/` (or
`AUDIO_CACHE_DIR`), named by a hash of the reply text. These are the
agent's replies, not the caller's voice. A reply that reads back a
caller's details contains that caller's name and number as audio.

## Where it goes

| Destination | What it receives | How |
| --- | --- | --- |
| Google | The caller's audio | Chrome's Web Speech API sends speech to Google for recognition. This happens in the browser, before the app sees any text. |
| Anthropic | Every turn, the full conversation history, and every tool result | The Claude API call in `app/receptionist.py` |
| ElevenLabs | The text of each agent reply | `app/voice.py`, only when ElevenLabs keys are set |

The system prompt tells the agent to "read the details back to the caller
once before saving" a message. So the reply sent to ElevenLabs includes the
caller's name and callback number.

## Retention

**Nothing is deleted automatically.** No code removes old messages, old
transcripts or cached audio. The database persists until someone deletes it
by hand:

    rm data/frontdesk.db        # or the file DB_PATH points to
    rm -rf audio_cache/         # cached speech
    python -m data.seed         # recreate an empty database

Re-running `python -m data.seed` on its own also wipes everything. It drops
and recreates every table, including `messages` and `call_log`.

Data already sent to Google, Anthropic or ElevenLabs is kept under their
own retention policies, which this project doesn't control.

## Who can see it

Whoever runs the demo, and anyone who can reach the server. `/admin` and the
`/api/admin/*` endpoints have no authentication. They are protected only by
uvicorn listening on localhost by default.

## If this were real

This is fictional demo data. Real caller data would need retention
**enforced in code**, as a scheduled job that actually deletes records,
not described in a document. It would also need:

1. A spoken notice at the start of the call, and a way to decline.
2. Authentication on the admin page, encryption at rest, and access logging.
3. A documented process for a caller asking what is held about them.
