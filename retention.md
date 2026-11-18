# Data handling and retention

This is a prototype using fictional organisation data. It does, however,
collect real information from whoever is speaking to it, and it sends some
of that to third parties. This document says what, where and for how long.

## What is collected

| Field | Source | Why |
| --- | --- | --- |
| Caller name | Spoken by the caller | So the callback is addressed to someone |
| Callback number | Spoken by the caller | So someone can call back |
| Centre | Inferred from the conversation | So the message reaches the right site |
| Topic and message | Spoken by the caller | So the callback is useful |
| Transcript of each turn | Speech recognition | Call log and quality review |

**Not collected, by design:** date of birth, address, payment details, and
any information about an individual child. The agent takes a message and a
person calls back instead.

## Where it goes

| Destination | What it receives | Why |
| --- | --- | --- |
| Local SQLite (`data/frontdesk.db`) | Everything above | Source of truth |
| ElevenLabs | The sentence the agent speaks | Speech synthesis |
| n8n | The message record, including the callback number | Routing to the right centre |
| Google Sheets (via n8n) | The message record | Shared visibility for staff |
| Email (via n8n) | The message record | Notification |

The agent is instructed to confirm a message with "I've got that" rather
than reading a caller's name back in the synthesised reply, so names reach
the speech API less often than they otherwise would.

## Retention

| Data | Kept for | Then |
| --- | --- | --- |
| Messages | 90 days | Deleted |
| Call log transcripts | 30 days | Deleted |
| Aggregate topic counts | Indefinitely | No personal data retained |
| Cached audio | Until manually cleared | Contains no caller speech |

Run `python -m data.prune` to apply these. <!-- TODO: write this script -->

## Who can see it

Only whoever runs this prototype. In a real deployment this section would
name the roles with access to the message queue and the call log, and they
would not be the same people.

## If this were real

Three things this prototype does not do, which a production version would
need:

1. A recorded consent line at the start of the call, and a way to decline.
2. Encryption at rest, and access logging on the message store.
3. A documented process for a caller asking what is held about them.
