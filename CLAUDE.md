# Front Desk — voice receptionist for Kestrel Community Recreation

Kestrel Community Recreation is a FICTIONAL not-for-profit. All data in this
repo is invented. This is a portfolio demo, not a production system, and it
is not affiliated with any real organisation.

## What this is

A voice receptionist for a multi-site community recreation organisation:
swimming pools, recreation centres, outside school hours care, gymnastics.
A caller speaks a question; the agent answers from the database, takes a
message when it cannot, and hands anything serious to a person.

## Rules

- Never invent opening hours, prices or program details. Every fact the
  agent states must come from a tool call against the database.
- If the data does not answer the question, say so and offer to take a
  message. Do not guess, and do not approximate.
- Anything about a child's safety, an injury, a complaint or a refund goes
  straight to escalate(). No attempt to resolve it.
- Never discuss an individual child, by name or otherwise. Take a message.
- SQLite is the source of truth. ElevenLabs is an optional layer: if it
  fails, the call still works. Fall back to browser speech.
- Keep the decision logic in one readable module. I have to be able to
  explain every line of it in an interview.
- Write tests for the tools before wiring up the model.
- No secrets in the repo. API keys from the environment only, via
  app/config.py. Never inline os.getenv() elsewhere.
- Replies are spoken aloud: one or two sentences, no lists, no markdown.

## Collected personal information

Name, callback number, which centre, and the reason for calling. Nothing
else. No date of birth, no address, no payment details, no information
about a child. This limit is enforced in the system prompt and documented
in retention.md.

## Stack

Python 3.11, FastAPI, SQLite (stdlib sqlite3), pytest, Anthropic SDK.
Capture: one HTML page, vanilla JavaScript, Web Speech API (Chrome/Edge).
Voice output: ElevenLabs, Flash/Turbo model, cached to disk by text hash.

## Layout

    app/main.py          FastAPI routes only
    app/receptionist.py  the conversation loop and tool declarations
    app/tools.py         the five tools, plain Python, no AI
    app/voice.py         ElevenLabs, with fallback to None
    app/db.py            connection and queries
    app/config.py        environment loading, single source
    app/prompts/system.md
    data/schema.sql
    data/seed.py
    static/index.html    the caller's page
    static/admin.html    the call log
    tests/test_tools.py

## The five tools

    find_centre(query)
    get_opening_hours(centre_id, facility, day)
    get_program_info(program, centre_id)
    take_message(name, phone, centre_id, topic, message)
    escalate(reason)

Tools return results, never raise, for the "not found" case — the model
needs to be told "no such centre" rather than crash.
