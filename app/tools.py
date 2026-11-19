"""
The five tools available to the receptionist agent.

Plain Python — no AI, no API calls.  Every function returns a dict or list;
none of them raise for the not-found case, because the model needs to be told
"no such centre" rather than receive a 500 error.
"""

import datetime
import re

from app import db

# Index-1 mapping so _MONTH_NAMES[month_number] gives the full month name.
_MONTH_NAMES = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]

_WEEKDAY_NAMES = {
    0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
    4: 'Friday', 5: 'Saturday', 6: 'Sunday',
}

# Filler words a caller might say that add no search value.
_FILLER = re.compile(r'\b(the|one|at|in)\b', re.IGNORECASE)

_FIND_LIMIT = 5


def _normalise(query: str) -> str:
    """
    Prepare a caller's query for LIKE matching.

    - 'and' → '&'  so "Muralong Aquatic and Recreation" hits the DB value
    - strips filler words: the, one, at, in
    - collapses whitespace
    """
    q = re.sub(r'\band\b', '&', query, flags=re.IGNORECASE)
    q = _FILLER.sub('', q)
    return ' '.join(q.split())


# ---------------------------------------------------------------------------
# find_centre
# ---------------------------------------------------------------------------

def find_centre(query: str) -> dict:
    """
    Search for centres by name or suburb.

    Call this first whenever the caller mentions a location or centre name —
    it resolves the centre_id required by get_opening_hours and
    get_program_info.

    The query is normalised before searching: 'and' is treated as '&',
    common filler words (the, one, at, in) are stripped, and whitespace is
    collapsed.  This means "the one at Muralong" and "Muralong Aquatic and
    Recreation" both resolve correctly.

    Returns a dict:
      centres   – up to 5 matching centres (id, name, type, suburb,
                  address, phone)
      truncated – True when more than 5 centres matched; ask the caller to
                  be more specific before proceeding.

    If centres is empty, nothing matched; offer to take a message.
    If more than one centre is returned, ask the caller to confirm which one.
    """
    term = f'%{_normalise(query)}%'
    with db.connection() as con:
        # Fetch one extra row to detect truncation without a second COUNT query.
        rows = con.execute(
            '''
            SELECT id, name, type, suburb, address, phone
            FROM   centres
            WHERE  name LIKE ? OR suburb LIKE ?
            ORDER  BY name
            LIMIT  ?
            ''',
            (term, term, _FIND_LIMIT + 1),
        ).fetchall()

    truncated = len(rows) > _FIND_LIMIT
    return {
        'centres':   [dict(r) for r in rows[:_FIND_LIMIT]],
        'truncated': truncated,
    }


# ---------------------------------------------------------------------------
# get_opening_hours
# ---------------------------------------------------------------------------

def get_opening_hours(centre_id: int, facility: str, day: str) -> dict:
    """
    Return opening hours for a named facility at a centre on a given day.

    Call after find_centre() has resolved centre_id.  Pass the full day name
    ('Monday', 'Saturday', etc.); 'today' is also accepted and resolved to
    the current day automatically.

    Three distinct not-operating cases are reported separately so the model
    can phrase the response correctly:
      - 'closed_today'    the facility simply does not open on that day
      - 'closed_seasonal' the facility is in its winter/summer closure window
      - 'facility_not_found' no facility matched the query at this centre
    """
    # Normalise day: accept 'today' or any capitalisation.
    normalised = day.strip()
    if normalised.lower() == 'today':
        normalised = _WEEKDAY_NAMES[datetime.date.today().weekday()]
    else:
        normalised = normalised.capitalize()

    with db.connection() as con:
        centre = con.execute(
            'SELECT id, name FROM centres WHERE id = ?',
            (centre_id,),
        ).fetchone()

        if centre is None:
            return {'status': 'centre_not_found', 'centre_id': centre_id}

        term = f'%{facility}%'
        facilities = con.execute(
            '''
            SELECT id, name, closure_month_start, closure_month_end
            FROM   facilities
            WHERE  centre_id = ? AND name LIKE ?
            ORDER  BY name
            ''',
            (centre_id, term),
        ).fetchall()

        if not facilities:
            # Return the centre's actual facility names so the model can tell
            # the caller what is available instead of just saying "not found".
            available = con.execute(
                'SELECT name FROM facilities WHERE centre_id = ? ORDER BY name',
                (centre_id,),
            ).fetchall()
            return {
                'status':              'facility_not_found',
                'query':               facility,
                'available_facilities': [r['name'] for r in available],
            }

        today_month = datetime.date.today().month
        results = []

        for fac in facilities:
            entry: dict = {'facility': fac['name']}

            # Check the seasonal closure window first.  Outdoor pools carry
            # closure_month_start=5 and closure_month_end=9 (May–September
            # inclusive).  When today falls inside that range the facility is
            # shut, regardless of what facility_hours contains.
            start = fac['closure_month_start']
            end   = fac['closure_month_end']
            if start is not None and end is not None and start <= today_month <= end:
                entry.update({
                    'status':       'closed_seasonal',
                    'closed_from':  _MONTH_NAMES[start],
                    'closed_until': _MONTH_NAMES[end],
                })
                results.append(entry)
                continue

            hours = con.execute(
                '''
                SELECT open_time, close_time
                FROM   facility_hours
                WHERE  facility_id = ? AND day_of_week = ?
                ''',
                (fac['id'], normalised),
            ).fetchone()

            if hours is None:
                # An absent row in facility_hours means the facility does not
                # operate on this day — this is intentional schema design, not
                # a data gap (see schema.sql: "An absent row means closed that
                # day").  We return 'closed_today' so the model can tell the
                # caller plainly, rather than guessing or staying silent.
                entry['status'] = 'closed_today'
            else:
                entry.update({
                    'status':     'open',
                    'open_time':  hours['open_time'],
                    'close_time': hours['close_time'],
                })

            results.append(entry)

    return {
        'status':  'ok',
        'centre':  centre['name'],
        'day':     normalised,
        'results': results,
    }


# ---------------------------------------------------------------------------
# get_program_info
# ---------------------------------------------------------------------------

def get_program_info(program: str, centre_id: int) -> list[dict]:
    """
    Return programs matching the query at a given centre.

    Call after find_centre() has resolved centre_id.  'program' can be a
    partial name ('swim'), a type keyword ('oshc', 'gymnastics'), or a plain
    description ('lesson for a six-year-old') — the search runs across name,
    program_type and description.  An empty list means that centre offers
    nothing matching the query; offer to take a message.
    """
    term = f'%{program}%'
    with db.connection() as con:
        rows = con.execute(
            '''
            SELECT name, program_type, age_min, age_max, price_per_session,
                   description, next_intake, day_of_week, start_time,
                   duration_minutes
            FROM   programs
            WHERE  centre_id = ?
              AND  (name LIKE ? OR program_type LIKE ? OR description LIKE ?)
            ORDER  BY name
            ''',
            (centre_id, term, term, term),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# take_message
# ---------------------------------------------------------------------------

def take_message(
    name: str,
    phone: str,
    centre_id: int,
    topic: str,
    message: str,
) -> dict:
    """
    Save a caller's message to the database.

    Call once the agent has confirmed name, phone, centre and topic with the
    caller.  Always write to the database before attempting any n8n delivery —
    the message must be persisted first so it is never lost if delivery fails.
    Returns the new message_id so the delivery layer can mark it delivered.
    On database failure returns an error dict rather than raising, so the
    agent can tell the caller something went wrong and suggest they call back.
    """
    try:
        with db.connection() as con:
            cur = con.execute(
                '''
                INSERT INTO messages (name, phone, centre_id, topic, message)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (name, phone, centre_id or None, topic, message),
            )
            return {'status': 'ok', 'message_id': cur.lastrowid}
    except Exception as exc:
        return {'status': 'error', 'detail': str(exc)}


# ---------------------------------------------------------------------------
# escalate
# ---------------------------------------------------------------------------

def escalate(reason: str) -> dict:
    """
    Signal that this call must be handled by a person immediately.

    Call for anything involving a child's safety, an injury, a complaint or a
    refund — no attempt to resolve it first.  The receptionist loop must stop
    and trigger a human hand-off as soon as this tool returns; it must not
    continue the conversation or call any other tool afterward.
    """
    return {'status': 'escalated', 'reason': reason}
