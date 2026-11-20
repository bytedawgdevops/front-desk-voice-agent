"""
Database connection factory.
All other modules use the connection() context manager; nothing else opens
a sqlite3 connection directly.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager

from app.config import DB_PATH

logger = logging.getLogger(__name__)


@contextmanager
def connection():
    """
    Yield a sqlite3.Connection with row_factory and foreign-key enforcement.
    Commits on clean exit, rolls back on any exception, always closes.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def log_turn(
    session_id: str,
    user_text: str,
    agent_reply: str,
    tools_called: list[str],
    escalated: bool,
) -> None:
    """
    Append one turn (user message + assistant reply) to call_log.

    Two rows are written per turn so the schema's role check is satisfied and
    either side can be queried independently.  The assistant row carries the
    tool list and escalation flag in tool_name / tool_input.

    Never raises — a logging failure must not break a call.
    """
    try:
        with connection() as con:
            (turn_num,) = con.execute(
                'SELECT COALESCE(MAX(turn), 0) + 1 FROM call_log WHERE session_id = ?',
                (session_id,),
            ).fetchone()
            con.execute(
                "INSERT INTO call_log (session_id, turn, role, content) VALUES (?, ?, 'user', ?)",
                (session_id, turn_num, user_text),
            )
            con.execute(
                '''
                INSERT INTO call_log
                    (session_id, turn, role, content, tool_name, tool_input)
                VALUES (?, ?, 'assistant', ?, ?, ?)
                ''',
                (
                    session_id,
                    turn_num,
                    agent_reply,
                    json.dumps(tools_called) if tools_called else None,
                    json.dumps({'escalated': escalated}),
                ),
            )
    except Exception:
        logger.exception('call_log write failed for session %s', session_id)
