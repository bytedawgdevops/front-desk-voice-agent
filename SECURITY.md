# Security

## Reporting a vulnerability

Open an issue on this repository describing the problem and how to
reproduce it. This is a portfolio demo with fictional data, so public
reporting is fine.

## In scope

- Application code (`app/`, `static/`, `data/seed.py`)
- CI configuration (`.github/workflows/`)
- Dependency handling (`requirements.txt` and the CI audit steps)

## Out of scope

- **The sample data.** Every centre, program, price and phone number is
  invented.
- **Availability.** The demo runs locally; there is no hosted service to
  take down.
- **Third-party services** (Anthropic, ElevenLabs, Google's speech
  recognition). Report issues in those to their own disclosure processes.

## Known limitations

Known gaps, including ones that are deliberately not fixed, are listed in
[docs/threat-model.md](docs/threat-model.md).
