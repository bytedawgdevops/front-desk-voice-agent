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

- Finds the right centre from a name or a suburb, and asks when ambiguous
- Answers opening hours per facility, including seasonal closures
- Answers program questions: swim lessons, OSHC, gymnastics
- Takes a message when it cannot answer, reading the details back first
- Escalates anything involving a child's safety, an injury, a complaint or
  a refund straight to a person, with no attempt to resolve it
- Logs every turn, and routes messages to the right centre

## Architecture

    Browser page    mic capture, plays the reply        HTML + JS (Web Speech API)
    API             receives text, returns reply+audio   Python (FastAPI)
    Receptionist    decides what to do, calls tools      Python + Claude API
    Voice           turns the reply into speech          ElevenLabs
    Data            centres, programs, log, messages     SQLite
    Delivery        gets messages to a person            n8n

One turn: speech → text in the browser → `POST /api/turn` → the model is
given the conversation and five tools → it calls a tool → Python queries
SQLite → the model writes the reply → ElevenLabs speaks it → the turn is
logged → if a message was taken, a webhook fires to n8n.

**The model cannot state a fact it did not get from a tool call.** There is
no path from the model to an opening hour except through a function running
against the database. That is the core design decision and most of the
accuracy story.

## Guardrails

| Guardrail | How |
| --- | --- |
| No invented facts | Every fact comes from a tool call; unknowns return "not found" |
| Escalation | Safety, injury, complaints and refunds bypass the agent entirely |
| Disclosure | The agent identifies itself as automated in its first sentence |
| Minimal data | Name, callback number, centre and topic. Nothing else |
| No child details | The agent never discusses an individual child |
| Degradation | ElevenLabs or n8n failing does not break a call |

Data flows and retention are documented in [retention.md](retention.md).

## Running it

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # then fill in your keys
    python -m data.seed
    uvicorn app.main:app --reload --port 8000

Then `http://localhost:8000` to make a call, `/admin` for the log.

For the n8n delivery layer:

    docker volume create n8n_data
    docker run -it --rm --name n8n -p 5678:5678 \
      -e GENERIC_TIMEZONE="Australia/Adelaide" -e TZ="Australia/Adelaide" \
      -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n

Workflows are in `n8n/` and import through the editor at `localhost:5678`.

## Configuration

| Variable | Required | Notes |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Yes | — |
| `ANTHROPIC_MODEL` | Yes | Fast model; latency matters on a call |
| `ELEVENLABS_API_KEY` | No | Without it, the browser speaks the reply |
| `ELEVENLABS_VOICE_ID` | No | Use an Australian voice |
| `ELEVENLABS_MODEL` | No | Flash/Turbo: lower latency, lower cost |
| `N8N_WEBHOOK_URL` | No | Production URL. Without it, messages save but do not route |
| `N8N_SHARED_TOKEN` | No | Protects the digest endpoint |
| `DB_PATH` | Yes | — |

## Tests

    pytest -v

<!-- TODO after the build:
     - screenshot of the admin page → docs/admin.png, embed it above
     - screenshot of the n8n canvas → docs/n8n.png
     - link to the demo video
     - anything in Known limits that turned out differently
-->

## Known limits

- Chrome and Edge only. Speech capture uses the Web Speech API.
- Speech recognition mishears place names, particularly invented ones.
- The data is invented sample data, not a real organisation's.
- It cannot book, take payment, or access member accounts, by design.
- Correct facts can still be phrased ambiguously; the grounding guarantees
  the facts, not the wording.

## Licence

MIT. The sample data is fictional and free to reuse.
