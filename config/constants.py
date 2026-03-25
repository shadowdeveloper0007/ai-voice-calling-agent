import os
from pathlib import Path
from dotenv import load_dotenv
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load env files once — every other module should import from here
load_dotenv(_PROJECT_ROOT / '.env.global')
load_dotenv(_PROJECT_ROOT / '.env.local', override=True)

# ── LiveKit ─────────────────────────────────────────────────
LIVEKIT_URL = os.getenv('LIVEKIT_URL', '')
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY', '')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET', '')
AGENT_NAME = os.getenv('AGENT_NAME', 'ai-receptionist')
SIP_TRUNK_ID = os.getenv('SIP_TRUNK_ID', '')
CLINIC_API_KEY = os.getenv('CLINIC_API_KEY', '')

# ── OpenAI / LLM ───────────────────────────────────────────
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
ELEVEN_API_KEY = os.getenv('ELEVEN_API_KEY', '')

# ── Qdrant ──────────────────────────────────────────────────
QDRANT_URL = os.getenv('QDRANT_URL', '')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY', '')
QDRANT_COLLECTION_NAME = os.getenv('QDRANT_COLLECTION_NAME', 'business_knowledge')

# ── Opus API ────────────────────────────────────────────────
OPUS_API_URL = os.getenv('OPUS_API_URL', 'https://api.resepsjon.framsynt.com')
OPUS_BEARER_TOKEN = os.getenv('OPUS_BEARER_TOKEN', '')
OPUS_USE_TEST_ENV = os.getenv('OPUS_USE_TEST_ENV', 'false').lower() == 'true'
OPUS_PREFERRED_CLINICIAN_ID = int(os.getenv('OPUS_PREFERRED_CLINICIAN_ID', '8692'))
OPUS_CLINIC_ID = os.getenv('OPUS_CLINIC_ID', '471-15f8ea64-137c-4483-835e-144919e58149')

# ── n8n Webhook URLs ────────────────────────────────────────
FORSTE_LEDIGE_TIME_URL = os.getenv('FORSTE_LEDIGE_TIME', 'https://n8n.csdevhub.com/webhook/sjekk_forste_ledige_time')
SJEKK_LEDIGHET_URL = os.getenv('SJEKK_LEDIGHET', 'https://n8n.csdevhub.com/webhook/sjekkLedighet')
BOOK_TIME_URL = os.getenv('BOOK_TIME', 'https://n8n.csdevhub.com/webhook/book-time')
LEGG_IGJEN_BESKJED_URL = os.getenv('LEGG_IGJEN_BESKJED', 'https://n8n.csdevhub.com/webhook/leave_message')
GET_CLIENT_DETAIL_URL = os.getenv('GET_CLIENT_DETAIL', 'https://n8n.csdevhub.com/webhook/get_client_detail')
CANCEL_BOOKING_URL = os.getenv('CANCEL_BOOKING', 'https://n8n.csdevhub.com/webhook/cancel_booking')
UPDATE_APPOINTMENT_URL = os.getenv('UPDATE_APPOINTMENT', 'https://n8n.csdevhub.com/webhook/update_appointment_date')

# ── Prompt presets ──────────────────────────────────────────
presets_path = _PROJECT_ROOT / 'test.yaml'
with open(presets_path, 'r') as file:
    presets = yaml.safe_load(file)

ANBEFALT = presets['Prompt']

# Global variable to store business settings (set at runtime)
business_settings = None
