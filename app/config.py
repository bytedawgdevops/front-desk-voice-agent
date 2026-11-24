"""
Single source of truth for environment variables.
Every other module imports from here; nothing else calls os.getenv().
"""

import os

from dotenv import load_dotenv

load_dotenv()

DB_PATH             = os.environ.get('DB_PATH',             'data/frontdesk.db')
ANTHROPIC_API_KEY   = os.environ.get('ANTHROPIC_API_KEY',   '')
ANTHROPIC_MODEL     = os.environ.get('ANTHROPIC_MODEL',     'claude-haiku-4-5')
ELEVENLABS_API_KEY  = os.environ.get('ELEVENLABS_API_KEY',  '')
ELEVENLABS_VOICE_ID = os.environ.get('ELEVENLABS_VOICE_ID', '')
ELEVENLABS_MODEL    = os.environ.get('ELEVENLABS_MODEL',    'eleven_flash_v2_5')
N8N_WEBHOOK_URL     = os.environ.get('N8N_WEBHOOK_URL',     '')
N8N_SHARED_TOKEN    = os.environ.get('N8N_SHARED_TOKEN',    '')
AUDIO_CACHE_DIR     = os.environ.get('AUDIO_CACHE_DIR',     'audio_cache')
