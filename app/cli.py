"""
Text REPL for the front-desk receptionist.

Usage:
    python -m app.cli

Type a question and press Enter. The reply and any tool calls are printed.
Type 'quit' or press Ctrl-C to exit.
"""

import sys
import uuid

from app.receptionist import reply


def main() -> None:
    session_id    = str(uuid.uuid4())
    conversations: dict = {}

    print("Front Desk CLI — type your question, 'quit' to exit.\n")

    while True:
        try:
            text = input('You: ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not text:
            continue
        if text.lower() in ('quit', 'exit', 'q'):
            break

        result = reply(session_id, conversations, text)

        if result.tools_called:
            print(f'[tools: {", ".join(result.tools_called)}]')

        print(f'Agent: {result.reply}\n')

        if result.escalated:
            print('[call escalated — ending session]')
            break


if __name__ == '__main__':
    main()
