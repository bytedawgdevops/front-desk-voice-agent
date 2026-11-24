# Threat model

Front Desk is a portfolio demo that runs locally on fictional data. This
page lists the threats that would matter if it were deployed, and states
honestly which ones the code handles. Every row was checked against the
code at commit `84bbdb4` and the GitHub repository settings.

| Threat | Why this application is exposed | Mitigation | Status |
| --- | --- | --- | --- |
| **API key theft** | The server holds Anthropic and ElevenLabs keys, and the repo is public. | Keys are read only in `app/config.py`, from the environment or a local `.env`. `.env` is gitignored and has never been committed; only `.env.example` is tracked. GitHub secret scanning and push protection are enabled. Keys never reach the browser: `/api/turn` returns only the reply, tool names, an audio URL and the escalation flag. CI uses placeholder values. | Implemented |
| **Cost abuse** | `/api/turn` has no authentication, and each request can trigger paid Claude and ElevenLabs calls. | `_TOOL_CAP = 5` (`app/receptionist.py:27`) limits the model round trips **within one turn**, and `max_tokens=1024` limits each call. That bounds the cost of a single request, not the number of requests. There is **no rate limiting, no limit on turns per conversation, and no input length limit**. Conversation history (`app/main.py:31`) grows without limit and is resent on every call, so each turn costs more than the last. The ElevenLabs disk cache only helps with repeated replies. | Not implemented |
| **Prompt injection** | Whatever the caller says goes to the model unfiltered. | Architectural: the model can only call five tools (`_dispatch`, `app/receptionist.py:193`, rejects any other name). `find_centre`, `get_opening_hours` and `get_program_info` are read-only `SELECT`s over centres, facilities and programs, which is public information. `take_message` inserts one row into `messages`; it can't read, update or delete anything. `escalate` returns a fixed value and ends the turn. No tool reads `call_log` or `messages`, so no other caller's data can be reached, and the model has no network, file or shell access. **Blast radius:** junk messages in the queue, forced escalations, and false statements spoken to the caller. Grounding is enforced by the prompt, not checked in code. | Partial |
| **SQL injection** | Values the model passes to tools come from caller speech. | All eight `execute` calls in `app/tools.py` use `?` placeholders, and no SQL in `app/` is built from strings. Tested by `test_sql_injection_find_centre` in `tests/test_tools.py`, which covers `find_centre` only. `LIKE` wildcards (`%`, `_`) in input can widen a match but can't change the query. | Implemented |
| **PII and third-party data flows** | Callers give their name and phone number, and can say anything else. | `log_turn` (`app/db.py:36`) stores the **full caller transcript and full agent reply** of every turn, plus tool names and the escalation flag, but not tool arguments. The minimal-data rule controls what the agent *asks for*, not what the transcript keeps: a caller who volunteers a child's details has them logged. Data leaves the machine in three places: **Google** gets the caller's audio through Chrome's Web Speech API; **Anthropic** gets every turn, the full history and the tool results; **ElevenLabs** gets the reply text, which includes the caller's name and number, because the prompt has the agent read details back before saving. Nothing in the code deletes old data. `/admin` and `/api/admin/*` have **no authentication**; only uvicorn's default binding to localhost protects them. | Partial |
| **Dependency compromise** | Seven packages install unpinned from PyPI, along with whatever they depend on. | CI runs `pip-audit` and `bandit -r app -ll` on every push and pull request. `pip-audit` first flagged the runner's bundled setuptools 79.0.1 (PYSEC-2026-3447, GHSA-xmj3-9gf7-h52w). Fixes existed, so CI now upgrades setuptools before auditing and the audit is clean. `continue-on-error` stays as a safeguard against a CVE with no fix. **Dependabot alerts and security updates are disabled**, and there is no `dependabot.yml`. `requirements.txt` has no versions, lockfile or hashes, so every build installs whatever is newest. Actions are pinned to major-version tags, not commit SHAs. | Partial |
| **Untrusted model output in the admin page** | `/admin` displays text written by callers and by the model. | Every caller- or model-derived value (name, phone, centre, topic, transcript, reply, tool names) goes through `esc()` (`static/admin.html:177`) before being inserted into the page. The only unescaped values are database IDs and formatted timestamps. `esc()` doesn't escape single quotes, which is safe because no attribute uses them. | Implemented |

## What's specific to an AI application

Ruff, bandit and pip-audit check code and packages. None of them can tell
you that a caller might *talk the agent into something*: a sentence that
looks harmless to a scanner is a valid input to the model. So the control
for that has to be architectural rather than a filter. Trying to spot
malicious phrasing in speech is a contest the defender loses. Limiting what
the model can *do* holds no matter what it is persuaded to try. Here, that
limit is the five tools: four are read-only or inert, and one writes a
single row.

That makes the tool list the security boundary. Adding a sixth tool is a
security decision, not a feature decision. A tool that looks up a booking,
reads past messages or sends an email widens what a persuasive caller can
reach. It needs the same scrutiny as a new public API endpoint.
