"""
The receptionist conversation loop.

Declares the five tools in Anthropic tool-calling format, runs the
send→execute→return cycle, and returns TurnResult to the caller.
"""

import json
import pathlib
from dataclasses import dataclass, field

import anthropic

import app.tools as _tools
from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

_SYSTEM_PROMPT = (
    pathlib.Path(__file__).parent / 'prompts' / 'system.md'
).read_text(encoding='utf-8')

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_TOOL_CAP = 5
_OVERFLOW_REPLY  = "Let me take a message and have someone call you back."
_ESCALATE_REPLY  = "I'm putting you through to a team member right away, please hold."

# ---------------------------------------------------------------------------
# Tool declarations
# ---------------------------------------------------------------------------

_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'today']

TOOLS: list[dict] = [
    {
        'name': 'find_centre',
        'description': (
            'Search for centres by name or suburb. '
            'Call this first whenever the caller mentions a location or centre name — '
            'it resolves the centre_id required by get_opening_hours and get_program_info. '
            'Pass purpose to filter out irrelevant centre types: '
            '"hours" excludes head_office (caller asking about opening times), '
            '"programs" excludes head_office (caller asking about swim lessons, OSHC or gymnastics), '
            '"contact" includes all types (caller wants a phone number or address). '
            'The query is normalised before searching: "and" is treated as "&", '
            'common filler words (the, one, at, in) are stripped. '
            'Returns centres (up to 5) and a truncated flag. '
            'If truncated is true, ask the caller to be more specific. '
            'If more than one centre is returned, ask the caller to confirm which one.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'The centre name, suburb, or partial description the caller gave.',
                },
                'purpose': {
                    'type': 'string',
                    'enum': ['hours', 'programs', 'contact'],
                    'description': 'Filter centres by relevance to the caller\'s intent.',
                },
            },
            'required': ['query'],
        },
    },
    {
        'name': 'get_opening_hours',
        'description': (
            'Return opening hours for a named facility at a centre on a given day. '
            'Call after find_centre() has resolved centre_id. '
            'Pass the full day name or "today" — "today" is resolved to the current day automatically. '
            'Reports three distinct closed states: '
            '"closed_today" (facility does not open that day), '
            '"closed_seasonal" (winter/summer closure with closed_from and closed_until months), '
            '"facility_not_found" (returns available_facilities so you can redirect the caller).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'centre_id': {
                    'type': 'integer',
                    'description': 'The centre id returned by find_centre.',
                },
                'facility': {
                    'type': 'string',
                    'description': 'Partial facility name, e.g. "indoor pool", "gym", "gymnastics hall".',
                },
                'day': {
                    'type': 'string',
                    'enum': _DAYS,
                    'description': 'Day of the week, or "today" to use the current day.',
                },
            },
            'required': ['centre_id', 'facility', 'day'],
        },
    },
    {
        'name': 'get_program_info',
        'description': (
            'Return programs matching the query at a given centre. '
            'Call after find_centre() has resolved centre_id. '
            '"program" can be a partial name ("swim"), a type keyword ("oshc", "gymnastics"), '
            'or a plain description ("lesson for a six-year-old") — '
            'the search runs across name, program_type and description. '
            'An empty list means that centre offers nothing matching the query; '
            'offer to take a message.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'program': {
                    'type': 'string',
                    'description': 'Partial program name, type keyword, or description.',
                },
                'centre_id': {
                    'type': 'integer',
                    'description': 'The centre id returned by find_centre.',
                },
            },
            'required': ['program', 'centre_id'],
        },
    },
    {
        'name': 'take_message',
        'description': (
            'Save a caller\'s message to the database. '
            'Call once you have confirmed name, phone, centre and topic with the caller. '
            'Read the details back to the caller once before calling this tool. '
            'If the return status is "error", apologise and ask the caller to call 08 8300 0000 directly.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': 'Caller\'s full name.',
                },
                'phone': {
                    'type': 'string',
                    'description': 'Caller\'s callback number.',
                },
                'centre_id': {
                    'type': 'integer',
                    'description': 'Relevant centre id, or omit if not centre-specific.',
                },
                'topic': {
                    'type': 'string',
                    'description': 'Short reason for the call, e.g. "swim lessons enquiry".',
                },
                'message': {
                    'type': 'string',
                    'description': 'The full message to pass on.',
                },
            },
            'required': ['name', 'phone', 'topic', 'message'],
        },
    },
    {
        'name': 'escalate',
        'description': (
            'Signal that this call must be handled by a person immediately. '
            'Call for anything involving a child\'s safety, an injury, a complaint, or a refund — '
            'no attempt to resolve it first. '
            'Do not ask clarifying questions and do not look anything up before calling this tool. '
            'The call ends immediately after this tool returns.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'reason': {
                    'type': 'string',
                    'description': 'Brief description of why escalation is required.',
                },
            },
            'required': ['reason'],
        },
    },
]

_TOOL_MAP: dict = {
    'find_centre':      _tools.find_centre,
    'get_opening_hours': _tools.get_opening_hours,
    'get_program_info': _tools.get_program_info,
    'take_message':     _tools.take_message,
    'escalate':         _tools.escalate,
}


def _dispatch(name: str, args: dict):
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return {'error': f'unknown tool: {name}'}
    return fn(**args)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    reply:        str
    tools_called: list[str] = field(default_factory=list)
    escalated:    bool      = False


def reply(session_id: str, conversations: dict, user_text: str) -> TurnResult:
    """
    Advance the conversation by one user turn.

    conversations is a plain dict keyed by session_id — the caller owns it
    and passes it in each time, so this module holds no global state.
    """
    history = conversations.setdefault(session_id, [])
    history.append({'role': 'user', 'content': user_text})

    tools_called: list[str] = []

    for _ in range(_TOOL_CAP):
        response = _client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )

        # Append the assistant turn to the running history.
        history.append({'role': 'assistant', 'content': response.content})

        if response.stop_reason == 'end_turn':
            text = next(
                (b.text for b in response.content if hasattr(b, 'text')),
                '',
            )
            return TurnResult(reply=text, tools_called=tools_called)

        if response.stop_reason != 'tool_use':
            # Unexpected stop — return whatever text there is.
            text = next(
                (b.text for b in response.content if hasattr(b, 'text')),
                '',
            )
            return TurnResult(reply=text, tools_called=tools_called)

        # Execute every requested tool and collect results.
        tool_results = []
        escalated = False

        for block in response.content:
            if block.type != 'tool_use':
                continue

            tools_called.append(block.name)
            result = _dispatch(block.name, block.input)

            tool_results.append({
                'type':        'tool_result',
                'tool_use_id': block.id,
                'content':     json.dumps(result),
            })

            if block.name == 'escalate':
                escalated = True
                break  # stop processing further tool requests

        history.append({'role': 'user', 'content': tool_results})

        if escalated:
            return TurnResult(
                reply=_ESCALATE_REPLY,
                tools_called=tools_called,
                escalated=True,
            )

    # Reached the tool cap without a plain-text reply.
    return TurnResult(reply=_OVERFLOW_REPLY, tools_called=tools_called)
