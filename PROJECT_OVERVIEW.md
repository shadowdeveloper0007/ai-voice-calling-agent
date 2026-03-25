# Voice Agent Project Overview

## 1) Project Overview

Yeh project ek **AI Voice Agent** hai jo incoming call/audio conversation handle karta hai. Agent ka primary role:
- caller ki speech ko text me convert karna (STT),
- context ke basis par response generate karna (LLM),
- aur response ko voice me bolna (TTS).

Isme business-specific settings dynamic load hoti hain (phone number/business ke basis par), aur Opus API integration se clinic/treatment/timeslot related data fetch hota hai.

## 2) High-Level Flow

1. Voice session start hota hai (`agent.py` entrypoint).
2. Room/participant se caller phone identify hota hai.
3. Business settings fetch hoti hain (`innstillinger.py`).
4. OPUS data (jaise treatments) fetch hota hai (`OPUS_routes.py`).
5. LiveKit session configure hoti hai:
   - STT (OpenAI),
   - LLM (OpenAI),
   - TTS (ElevenLabs),
   - VAD/turn detection (Silero + multilingual turn detector).
6. Assistant tools/functions use karke conversation continue karta hai.

## 3) Tech Stack

### Core
- **Python** (main runtime)
- **LiveKit Agents** (real-time voice agent framework)

### AI/Voice
- **OpenAI**: STT + LLM
- **ElevenLabs**: TTS voice synthesis
- **Silero VAD**: voice activity detection
- **LiveKit Turn Detector**: multilingual turn handling

### APIs & Backend
- **FastAPI + Uvicorn** (API/service hosting related modules)
- **aiohttp** (async HTTP calls)
- **Pydantic** (data validation)
- **PyYAML** (config parsing)
- **python-dotenv** (`.env.local` se env vars load)

### Data/Infra (current status)
- **Qdrant client** dependency present hai, lekin `agent.py` me conversation history ka Qdrant section currently disabled/commented hai.

## 4) Project Structure

```text
agent_work/
  agent.py                 # Main voice agent entrypoint + session wiring
  OPUS_routes.py           # OPUS API calls (treatments/clinicians/timeslots)
  innstillinger.py         # Business settings/config fetch logic
  config/
    constants.py           # Environment/constants/config values
  core/
    assistant.py           # Assistant behavior/tools orchestration
    call_data.py           # Per-call runtime state model
  utils/
    helpers.py             # Utility helpers (phone extraction, etc.)
  requirements.txt         # Python dependencies
  .env.local               # Local environment variables/secrets
  start-agent.ps1          # Agent start script
  stop-agent.ps1           # Agent stop script
```

## 5) Important Config / Environment

New developer ko sabse pehle yeh verify karna chahiye:
- `.env.local` me OpenAI, ElevenLabs, LiveKit, OPUS related keys configured hon.
- `config/constants.py` me required defaults/URLs sahi hon.
- OPUS bearer token set ho; warna OPUS routes empty data return karenge.

## 6) Current Notes for New Developer

- README abhi generic template state me hai; practical handover ke liye yeh file use karein.
- `agent.py` currently LLM model hardcoded `gpt-4o` use karta hai (even though config variable available hai); future cleanup me isko fully config-driven banana useful hoga.
- Qdrant integration dependency me hai but runtime path commented/disabled hai; isko either fix karke enable karein ya dependency cleanup karein.
