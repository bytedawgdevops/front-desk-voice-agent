"""
FastAPI application — routes only.

All conversation logic lives in app.receptionist.
All voice logic lives in app.voice.
"""

import pathlib

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import app.db as _db
from app.config import AUDIO_CACHE_DIR
from app.receptionist import reply
from app.voice import speak

app = FastAPI(title='Kestrel Front Desk')

# Serve generated audio files.
_cache_dir = pathlib.Path(AUDIO_CACHE_DIR)
_cache_dir.mkdir(parents=True, exist_ok=True)
app.mount('/audio', StaticFiles(directory=str(_cache_dir)), name='audio')

# Serve the caller UI and any other static assets.
app.mount('/static', StaticFiles(directory='static'), name='static')

# One conversations dict per process lifetime — keyed by conversation_id.
_conversations: dict = {}


class TurnRequest(BaseModel):
    conversation_id: str
    text: str


class TurnResponse(BaseModel):
    reply:       str
    tools_used:  list[str]
    audio_url:   str | None
    escalated:   bool


@app.post('/api/turn', response_model=TurnResponse)
def turn(body: TurnRequest):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail='text must not be empty')

    result = reply(body.conversation_id, _conversations, body.text)
    audio_url = speak(result.reply)

    return TurnResponse(
        reply=result.reply,
        tools_used=result.tools_called,
        audio_url=audio_url,
        escalated=result.escalated,
    )


@app.get('/')
def index():
    return FileResponse('static/index.html')


@app.get('/admin')
def admin():
    return FileResponse('static/admin.html')


# ---------------------------------------------------------------------------
# Admin data endpoints
# ---------------------------------------------------------------------------

@app.get('/api/admin/messages')
def admin_messages():
    with _db.connection() as con:
        rows = con.execute(
            '''
            SELECT m.id, m.name, m.phone,
                   COALESCE(c.name, '—') AS centre,
                   m.topic, m.message, m.delivered, m.created_at
            FROM   messages m
            LEFT JOIN centres c ON c.id = m.centre_id
            ORDER  BY m.created_at DESC
            LIMIT  100
            '''
        ).fetchall()
    return [dict(r) for r in rows]


@app.get('/api/admin/conversations')
def admin_conversations():
    with _db.connection() as con:
        rows = con.execute(
            '''
            SELECT a.session_id,
                   a.turn,
                   u.content  AS caller_said,
                   a.content  AS agent_replied,
                   a.tool_name AS tools,
                   a.tool_input,
                   a.created_at
            FROM   call_log a
            JOIN   call_log u
                   ON  u.session_id = a.session_id
                   AND u.turn       = a.turn
                   AND u.role       = 'user'
            WHERE  a.role = 'assistant'
            ORDER  BY a.created_at DESC
            LIMIT  100
            '''
        ).fetchall()
    return [dict(r) for r in rows]


@app.get('/api/admin/topics')
def admin_topics():
    with _db.connection() as con:
        rows = con.execute(
            '''
            SELECT topic, COUNT(*) AS count
            FROM   messages
            GROUP  BY topic
            ORDER  BY count DESC
            '''
        ).fetchall()
    return [dict(r) for r in rows]
