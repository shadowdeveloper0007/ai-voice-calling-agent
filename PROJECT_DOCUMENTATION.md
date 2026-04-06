# AI Voice Agent — Complete Project Documentation

> **Language:** Hinglish (Hindi + English mix) — Beginner-friendly  
> **Last Updated:** April 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Core Concepts (Absolute Beginner Level)](#2-core-concepts)
3. [Complete Project Flow](#3-complete-project-flow)
4. [Folder & File Structure](#4-folder--file-structure)
5. [Key Modules Explanation](#5-key-modules-explanation)
6. [Environment Setup](#6-environment-setup)
7. [How to Run the Project](#7-how-to-run-the-project)
8. [Example Walkthrough](#8-example-walkthrough)
9. [Common Errors & Debugging](#9-common-errors--debugging)
10. [Summary](#10-summary)

---

## 1. Project Overview

### Yeh project kya hai?

Yeh ek **AI Voice Receptionist** hai — matlab ek aise software agent jo **phone calls receive** karta hai aur ek real receptionist ki tarah baat karta hai. Jaise kisi dental clinic mein receptionist hota hai jo:

- Aapko greet karta hai
- Aapki problem sunta hai
- Appointment book karta hai
- Information deta hai (prices, timings, services)

Wahi kaam yeh AI agent automated tarike se karta hai — bina kisi human ke.

### Kya problem solve karta hai?

- Clinic band hone ke baad bhi calls answer hoti hain
- Wait time zero — turant response milta hai
- Multiple calls simultaneously handle ho sakti hain
- Norwegian aur English dono languages mein baat kar sakta hai

### High-Level Architecture (Simple Words)

```
   Customer ka Phone
        |
        v
  +------------+
  |  Telnyx    |  <-- Phone network se call receive karta hai
  +------------+
        |
        v
  +------------+
  |  LiveKit   |  <-- Audio stream manage karta hai (real-time)
  +------------+
        |
        v
  +------------------------------------------+
  |           AI Agent Pipeline              |
  |                                          |
  |  [STT] --> [LLM] --> [TTS]              |
  |  Audio     Brain     Audio               |
  |  to Text   Thinks    to Speech           |
  |                                          |
  |  + Qdrant DB (business data)             |
  |  + Opus API (appointments)               |
  +------------------------------------------+
        |
        v
   Customer ko jawab sunai deta hai
```

**Simple words mein:**
1. Customer phone karta hai
2. Telnyx call receive karta hai
3. LiveKit audio stream handle karta hai
4. AI sunti hai (STT), sochti hai (LLM), bolti hai (TTS)
5. Qdrant se business info fetch hoti hai
6. Opus API se appointments book/cancel/change hoti hain

---

## 2. Core Concepts

### LiveKit

#### Kya hai LiveKit?

LiveKit ek **real-time audio/video communication platform** hai. Jaise Zoom ya Google Meet audio/video handle karta hai — waise hi LiveKit hamari AI agent ke liye audio handle karta hai.

#### Kyun use karte hain?

- Phone call ka audio real-time mein agent tak pahunchana
- Agent ka response audio real-time mein customer tak pahunchana
- Low latency — matlab bahut fast, customer ko lag feel nahi hota

#### Is project mein kaise kaam karta hai?

```
Customer bolta hai  --->  LiveKit audio stream  --->  AI Agent sunta hai
                                                          |
AI Agent bolta hai  <---  LiveKit audio stream  <---  Agent ka response
```

LiveKit ek "Room" create karta hai — imagine karo ek virtual meeting room jahan customer aur AI agent dono hain. Agent `livekit.agents` library use karta hai isse connect hone ke liye.

**Code mein (agent.py):**
```python
from livekit import agents, rtc
from livekit.agents import AgentSession

session = AgentSession(
    stt=openai.STT(...),   # Sunne ke liye
    llm=openai.LLM(...),   # Sochne ke liye
    tts=elevenlabs.TTS(...) # Bolne ke liye
)

await session.start(room=ctx.room, agent=assistant)
```

---

### Telnyx

#### Kya hai Telnyx?

Telnyx ek **telephony provider** hai — matlab yeh phone numbers deta hai aur phone calls ko internet (VoIP/SIP) se connect karta hai.

#### Telephony kyun chahiye?

Socho: customer apne normal phone se call karega — usse pata bhi nahi hoga ki wo AI se baat kar raha hai. Telnyx hi wo bridge hai jo:

- Customer ka phone call receive karta hai
- Usse internet par LiveKit room mein route karta hai (SIP protocol ke through)

#### Calls kaise handle hoti hain?

```
Customer dials +47 XXXXXXXX (Norway number)
          |
          v
    Telnyx receives call via SIP trunk
          |
          v
    Routes to LiveKit Room
          |
          v
    AI Agent connects to room
          |
          v
    Conversation starts!
```

**SIP Trunk** = Telephone line ka digital version. Jaise purane zamane mein telephone ke wire hote the, waise SIP trunk internet par digital wire hai.

Project mein yeh `SIP_TRUNK_ID` environment variable se configure hota hai.

---

### AI Pipeline (STT → LLM → TTS)

Yeh sabse important part hai — samjho isko step by step:

#### Step 1: STT (Speech-to-Text) — "Sunna"

**Kya karta hai?** Customer jo bolta hai (audio), usse text mein convert karta hai.

**Jaise:**  
Customer bola: "Mujhe ek appointment chahiye" (audio)  
STT output: `"Mujhe ek appointment chahiye"` (text)

**Kaun sa STT?** OpenAI ka `gpt-4o-transcribe` model

```python
stt=openai.STT(
    model='gpt-4o-transcribe',
    prompt='This is a conversation between an AI receptionist and a customer...'
)
```

#### Step 2: LLM (Large Language Model) — "Sochna"

**Kya karta hai?** Text message padh ke samajhta hai aur smart response generate karta hai. Yeh AI ka "brain" hai.

**Jaise:**  
Input text: "Mujhe dental checkup ka appointment chahiye"  
LLM soochta hai: "Ok, isko appointment book karni hai. Pehle date preference puuchta hoon, fir personnummer collect karta hoon..."

**Kaun sa LLM?** OpenAI ka `gpt-4o`

```python
llm=openai.LLM(
    model='gpt-4o',
    temperature=0.4  # Low = consistent answers, High = creative answers
)
```

#### Step 3: TTS (Text-to-Speech) — "Bolna"

**Kya karta hai?** LLM ka text response leke usse natural-sounding audio mein convert karta hai.

**Jaise:**  
Text: "Bilkul! Pehle bataiye, aapko pehli available appointment chahiye ya koi specific date?"  
TTS output: Natural human-like voice audio

**Kaun sa TTS?** ElevenLabs ka `eleven_turbo_v2_5` model (very natural voice)

```python
tts=elevenlabs.TTS(
    voice_id='uNsWM1StCcpydKYOjKyu',
    model='eleven_turbo_v2_5',
    voice_settings=elevenlabs.VoiceSettings(
        stability=0.5,
        similarity_boost=0.75,
        speed=1.0
    )
)
```

#### Complete Pipeline Flow

```
Customer bolta hai
    |
    v
[AUDIO] ---> [STT: Speech to Text] ---> "text string"
                                              |
                                              v
                                    [LLM: Brain/Thinking]
                                         |        |
                                         |        +--> Qdrant (business info)
                                         |        +--> Opus API (appointments)
                                         |
                                         v
                                   "response text"
                                         |
                                         v
                              [TTS: Text to Speech] ---> [AUDIO]
                                                              |
                                                              v
                                                    Customer sunta hai
```

#### Bonus: VAD (Voice Activity Detection)

```python
vad=silero.VAD.load()
```

VAD detect karta hai ki customer kab bol raha hai aur kab chup hai. Isse agent pata chalta hai ki customer ki baat khatam ho gayi, ab response dena hai.

#### Bonus: Turn Detection

```python
turn_detection=MultilingualModel()
```

Yeh detect karta hai ki customer ne apna "turn" khatam kar diya — matlab ab AI bol sakti hai. Norwegian aur English dono ke liye kaam karta hai.

---

### Qdrant (Vector Database)

#### Vector Database kya hai?

Normal database (jaise MySQL, PostgreSQL) mein data rows aur columns mein store hota hai — jaise Excel sheet.

**Vector Database** mein data "vectors" (numbers ki list) ke roop mein store hota hai. Yeh AI ke liye special hai kyunki:

- Text ko numbers mein convert karke store karta hai (embeddings)
- "Similar" data dhundhna bahut fast hota hai
- Example: "dental clinic in Oslo" search karo toh "tannklinikk i Oslo" bhi mil jayega (meaning similar hai)

#### Normal DB kyun nahi?

Normal DB mein exact match chahiye — `WHERE name = 'dental'`

Vector DB mein **meaning-based search** hoti hai — "dental" search karne par "tannlege" (Norwegian word for dentist) bhi mil sakta hai.

#### Is project mein kaise use hota hai?

Qdrant mein do type ka data store hai:

**1. `agent_data_chunk` — Business Settings**

```
Phone Number: +4723507256
Business Name: Oslo Dental Clinic
Agent Name: Sofia
Voice Settings: { id: "...", stability: 0.5 }
STT Model: gpt-4o-transcribe
LLM Model: gpt-4o
```

Jab call aati hai, phone number se Qdrant mein search hota hai → business settings mil jaati hain.

**2. `website_knowledge_chunk` — Business Information**

```
Page: "Services"
Content: "We offer dental cleaning, whitening, root canal..."

Page: "Pricing"  
Content: "Examination costs 1250 NOK including x-ray..."

Page: "Opening Hours"
Content: "Monday-Friday 8:00-16:00, Saturday closed..."
```

Jab customer kuch puuchta hai business ke baare mein → Qdrant se relevant info fetch hoti hai.

#### Code mein (innstillinger.py):

```python
# Phone number se business settings fetch karo
records = await _query_agent_data_chunk(client, phone_number)

# Business ID se website knowledge fetch karo
website_knowledge = await fetch_website_knowledge_by_business_id(business_id)
```

---

### Opus API Integration

#### Kya hai Opus?

Opus ek **clinic management system** hai — jaise ek digital diary jismein:

- Saari appointments stored hain
- Doctors/Clinicians ki availability hai
- Patients ka record hai
- Treatments ki list hai

#### Kyun use karte hain?

Real appointments book karne ke liye! AI agent sirf baat nahi karta — wo actually system mein appointment create/cancel/update karta hai Opus API ke through.

#### API Calls kaise hoti hain?

Opus API ke 4 main endpoints hain:

**1. Get Treatments** — Clinic ki saari treatments ki list
```
GET /api/Opus/treatments?businessId=XXX
Response: [
    { "Name": "Recall hos tannlege", "Price": 1250, "Duration": 45 },
    { "Name": "Tannbleking", "Price": 3500, "Duration": 60 },
    ...
]
```

**2. Find Patient Slot** — Patient ke liye available time slots dhundho
```
POST /api/Opus/patient/find-slot
Body: {
    "businessId": "...",
    "pid": "27826099165",       # Patient ID (personnummer)
    "treatmentName": "Recall hos tannlege",
    "preferredDate": "2026-07-20T07:00:00.000Z"
}
Response: {
    "found": true,
    "slotStart": "2026-07-20T09:00:00",
    "slotEnd": "2026-07-20T09:30:00",
    "clinicianName": "Dr. Kjetil Høye",
    "isExistingPatient": true
}
```

**3. Book Existing Patient** — Jo patient pehle se registered hai
```
POST /api/Opus/existing-patient/book
Body: { businessId, pid, treatmentId, clinicianId, slotStart, slotEnd }
```

**4. Book New Patient** — Naya patient
```
POST /api/Opus/new-patient/book
Body: { businessId, pid, firstName, lastName, phone, email, treatmentId, clinicianId, slotStart, slotEnd }
```

#### Data Flow Diagram

```
AI Agent                          Opus API
   |                                 |
   |-- GET treatments ------------->|
   |<-- Treatment list -------------|
   |                                 |
   |-- POST find-slot ------------->|
   |<-- Available slots ------------|
   |                                 |
   |-- POST book ------------------>|
   |<-- Booking confirmation -------|
```

**Authentication:** Bearer Token — har request mein `Authorization: Bearer <token>` header jaata hai.

---

## 3. Complete Project Flow

Yeh sabse important section hai — puri journey step-by-step:

### Call ka pura lifecycle:

```
 STEP 1                    STEP 2                   STEP 3
+--------+          +---------------+         +-------------+
|Customer|  calls   |    Telnyx     |  routes  |   LiveKit   |
| Phone  | -------> | (SIP Gateway) | -------> |   (Room)    |
+--------+          +---------------+         +-------------+
                                                     |
                                                     | connects
                                                     v
                                              +-----------+
                                              | AI Agent  |
                                              +-----------+
```

### Step-by-Step Flow:

**Step 1: Customer Phone Karta Hai**
- Customer Norway ka number dial karta hai (e.g., +47 23507256)
- Normal phone call — customer ko pata nahi ki AI se baat hogi

**Step 2: Telnyx Call Receive Karta Hai**
- Telnyx ka SIP trunk call receive karta hai
- Call ko LiveKit room mein route karta hai
- Room name mein phone number hota hai (e.g., `_+4723507256_FccScBRpKxpE`)

**Step 3: LiveKit Room Create Hota Hai**
- LiveKit ek virtual "room" create karta hai
- Customer aur AI agent dono is room mein join hote hain
- Audio streaming start hoti hai

**Step 4: Agent Startup**
- `agent.py` ka `entrypoint()` function call hota hai
- Room name se phone number extract hota hai
- Qdrant se business settings fetch hoti hain (phone number se)
- Opus API se treatments list fetch hoti hai
- Agent session create hota hai (STT + LLM + TTS)
- Noise cancellation enable hota hai (phone calls ke liye optimized)

**Step 5: Greeting**
- Agent customer ko greet karta hai: "Hei, jeg heter Sofia og er en AI resepsjonist for Oslo Dental Clinic. Hva kan jeg hjelpe deg med?"

**Step 6: Customer Bolta Hai**
- Customer bolta hai (audio)
- VAD detect karta hai ki customer bol raha hai
- Turn Detection samajhta hai ki customer ki baat khatam hui

**Step 7: STT — Audio to Text**
- OpenAI STT audio ko text mein convert karta hai
- Example: Audio → `"Jeg vil bestille en time for undersøkelse"`

**Step 8: LLM — Text Process Karta Hai**
- GPT-4o text padhta hai
- Business context (Qdrant se) dekhta hai
- Decide karta hai kya karna hai: book appointment? give info? transfer call?
- Tools/Functions call karta hai agar zarurat hai

**Step 9: Tool Execution (if needed)**
- Agar appointment book karni hai → Opus API call hoti hai
- Agar info chahiye → Qdrant/cached data se response banta hai
- Agar personnummer chahiye → DTMF collection start hota hai

**Step 10: TTS — Text to Audio**
- ElevenLabs LLM ka response text ko natural voice mein convert karta hai
- Example: `"Flott! Vil du ha første ledige time?"` → Natural Norwegian audio

**Step 11: Customer Sunta Hai**
- Audio LiveKit ke through customer ke phone par jaata hai
- Customer ko lagta hai jaise real person se baat ho rahi hai

**Step 12: Loop Continues**
- Steps 6-11 repeat hote hain jab tak conversation chal rahi hai

**Step 13: Call End**
- Customer hang up karta hai
- Participant disconnected event fire hota hai
- Call log save hota hai (if enabled)
- Session clean up hota hai

---

## 4. Folder & File Structure

```
agent_work/
├── agent.py                  # Main entry point - yahan se sab shuru hota hai
├── innstillinger.py          # Qdrant se business settings fetch karta hai
├── OPUS_routes.py            # Opus API calls (treatments, slots, booking)
├── test.yaml                 # Prompt template (AI ko instructions)
│
├── config/                   # Configuration files
│   ├── __init__.py
│   ├── constants.py          # Saare environment variables aur constants
│   └── prompts.py            # Prompt building logic
│
├── core/                     # Core business logic
│   ├── __init__.py
│   ├── assistant.py          # Main AI Assistant class (brain)
│   ├── call_data.py          # Call session data structure
│   └── language_texts.py     # Bilingual text messages (Norwegian + English)
│
├── tools/                    # AI Agent ke tools (functions jo LLM call karta hai)
│   ├── __init__.py
│   ├── booking.py            # Appointment booking tools
│   ├── client.py             # Client management tools (cancel, change, details)
│   ├── communication.py      # Communication tools (transfer, messages, DTMF)
│   └── general.py            # General tools (business info, language, history)
│
├── utils/                    # Utility/helper functions
│   ├── __init__.py
│   └── helpers.py            # Phone extraction, conversation summary
│
├── scripts/                  # Testing scripts
│   └── api_testing_script.py # Opus API manual testing
│
├── .env.global               # Global environment variables
├── .env.local                # Local overrides (gitignored)
└── venv/                     # Python virtual environment
```

### Detailed File Descriptions:

---

### `agent.py` — Main Entry Point

**Kya karta hai:** Yeh puri application ka starting point hai. Jab project start hota hai, yeh file sabse pehle run hoti hai.

**Kab run hota hai:** Project start hone par.

**Kya kya karta hai:**
1. Room name se phone number extract karta hai
2. Qdrant se business settings fetch karta hai (`fetch_business_settings_by_phone`)
3. Opus API se clinic treatments fetch karta hai (`get_clinic_treatments`)
4. Voice settings configure karta hai (ElevenLabs voice ID, stability, speed)
5. STT + LLM + TTS pipeline setup karta hai (`AgentSession`)
6. `CallData` object create karta hai (call ki state track karne ke liye)
7. LiveKit room se connect karta hai
8. SIP participants ka phone number extract karta hai (caller identification)
9. DTMF events listen karta hai (phone keypad press detection)
10. Assistant object create karta hai (prompt + tools)
11. Initial greeting generate karta hai

**Connection:** `innstillinger.py`, `OPUS_routes.py`, `config/constants.py`, `core/assistant.py`, `core/call_data.py`, `utils/helpers.py`

---

### `innstillinger.py` — Business Settings (Qdrant)

**Kya karta hai:** Qdrant vector database se business ka saara configuration fetch karta hai.

**Kab run hota hai:** Call start hone par (`entrypoint` se call hota hai).

**Key Functions:**
- `initialize_qdrant_client()` — Qdrant se connection banata hai
- `ensure_indexes()` — Required indexes create karta hai (fast search ke liye)
- `_query_agent_data_chunk()` — Phone number se business settings dhundta hai
- `_query_website_knowledge_chunk()` — Business ID se website info dhundta hai
- `fetch_business_settings_by_phone()` — Main function — phone number dena hai, pura config milta hai
- `fetch_website_knowledge_by_business_id()` — Website content fetch karta hai

**Return karta hai ek dictionary jismein:**
```python
{
    "business_id": "9ebf79ad-...",
    "business_name": "Oslo Dental Clinic",
    "agent_navn": "Sofia",
    "voice": { "id": "...", "stability": 0.5, ... },
    "stt_model": "gpt-4o-transcribe",
    "llm_model": "gpt-4o",
    "business_info": "We offer dental cleaning...",
    # ... aur bahut kuch
}
```

---

### `OPUS_routes.py` — Opus API Integration

**Kya karta hai:** Opus clinic management system se baat karta hai — treatments, slots, bookings.

**Kab run hota hai:** Jab bhi appointment-related kaam karna ho.

**Key Functions:**

| Function | Kya karta hai |
|----------|---------------|
| `get_clinic_treatments(business_id)` | Clinic ki saari treatments list fetch karta hai |
| `get_clinicians(business_id, clinic_id, treatment_id)` | Treatment ke liye available dentists dhundta hai |
| `find_patient_slot(business_id, pid, treatment_name, preferred_date)` | Patient ke liye available time slot dhundta hai |
| `book_existing_patient(...)` | Pehle se registered patient ke liye booking karta hai |
| `book_new_patient(...)` | Naye patient ke liye booking karta hai (extra info chahiye) |

**Connection:** `config/constants.py` se API URL aur Bearer Token aata hai. `tools/booking.py` se call hota hai.

---

### `test.yaml` — Prompt Template

**Kya karta hai:** AI agent ko detailed instructions deta hai — kaise behave karna hai, kya bolna hai, kaunse rules follow karne hain.

**Kab run hota hai:** Agent startup ke time load hota hai.

**Kya contain karta hai:**
- System context (date, time, business name)
- Language rules (Norwegian/English)
- Communication style guidelines
- Booking workflow (step-by-step)
- Data collection rules (name, phone, personnummer)
- Examples of conversations
- Critical rules

---

### `config/constants.py` — Environment Variables

**Kya karta hai:** Saare secrets aur configuration values ek jagah se load karta hai.

**Key Variables:**

| Variable | Purpose |
|----------|---------|
| `LIVEKIT_URL` | LiveKit server ka address |
| `LIVEKIT_API_KEY` | LiveKit authentication key |
| `LIVEKIT_API_SECRET` | LiveKit secret key |
| `AGENT_NAME` | Agent ka naam (default: 'ai-receptionist') |
| `SIP_TRUNK_ID` | Telnyx SIP trunk ID (call routing ke liye) |
| `OPENAI_API_KEY` | OpenAI API key (STT + LLM ke liye) |
| `ELEVEN_API_KEY` | ElevenLabs API key (TTS ke liye) |
| `QDRANT_URL` | Qdrant database ka URL |
| `QDRANT_API_KEY` | Qdrant authentication key |
| `OPUS_API_URL` | Opus API base URL |
| `OPUS_BEARER_TOKEN` | Opus API authentication token |
| `ANBEFALT` | Default prompt template (test.yaml se loaded) |

---

### `config/prompts.py` — Prompt Builder

**Kya karta hai:** Dynamic prompt build karta hai jo LLM ko instructions deta hai.

**Key Functions:**
- `build_multilingual_instructions()` — Language handling rules (Norwegian/English)
- `build_business_prompt()` — Business-specific terms replace karta hai prompt mein

---

### `core/assistant.py` — Main Assistant Class (THE BRAIN)

**Kya karta hai:** Yeh sabse important file hai — yeh AI agent ka "brain" hai. Saari logic yahan hai.

**Class:** `Assistant` — inherits from:
- `BookingToolsMixin` — Booking tools
- `ClientToolsMixin` — Client management tools
- `CommunicationToolsMixin` — Communication tools
- `GeneralToolsMixin` — General tools
- `Agent` (LiveKit) — Base agent class

**`__init__` mein kya hota hai:**
1. Norwegian timezone set karta hai (Oslo)
2. Current date/time Norwegian mein format karta hai
3. Multilingual instructions build karta hai
4. Prompt template mein placeholders replace karta hai (`{BUSINESS_NAME}`, `{AGENT_NAME}`, etc.)
5. Full prompt print karta hai (debugging ke liye)
6. Saare properties store karta hai (booking_config, call_data, etc.)

**Helper Methods:**
- `_language_code()` — Current language check karta hai ("no" or "en")
- `_get_text(key)` — Bilingual text messages fetch karta hai
- `_call_webhook_with_retry()` — Webhook calls with retry logic (timeout handling)
- `_opus_find_timeslot()` — Opus API se slots dhundta hai
- `_capture_customer_message()` — Customer ka message capture karta hai
- `_ensure_customer_name()` — Customer ka naam collect karta hai
- `_prepare_dtmf_event()` — DTMF (keypad) event setup karta hai

---

### `core/call_data.py` — Call Session State

**Kya karta hai:** Ek call ke dauran saari information track karta hai.

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `phone_number` | str | Caller ka phone number |
| `business_id` | str | Business ka ID |
| `call_start_time` | datetime | Call kab shuru hui |
| `appointment_booked` | bool | Booking ho gayi ya nahi |
| `conversation_messages` | list | Puri conversation ka record |
| `dtmf_digits` | list | Phone keypad se press hue digits |
| `collected_personnummer` | str | Collected personal ID number |
| `alternative_phone_number` | str | Agar customer alag number de |
| `language` | str | Current language ("no"/"en") |
| `booking_preference` | str | "first_available" ya "specific_date" |
| `selected_treatment_id` | int | Selected treatment ka ID |
| `selected_timeslot` | dict | Selected time slot |
| `selected_clinician` | dict | Selected doctor/clinician |
| `collected_email` | str | Customer ka email |
| `customer_first_name` | str | Customer ka naam |

---

### `core/language_texts.py` — Bilingual Messages

**Kya karta hai:** Saare UI messages Norwegian aur English dono mein store karta hai.

**Format:**
```python
LANGUAGE_TEXTS = {
    "booking_success": {
        "no": "Time er nå booket for {name}.",
        "en": "The appointment is now booked for {name}."
    },
    "transfer_failed": {
        "no": "Videresending feilet. La meg heller ta en beskjed.",
        "en": "Transfer failed. Let me take a message instead."
    },
    # ... 40+ messages
}
```

---

### `tools/booking.py` — Booking Tools

**Kya karta hai:** Appointment booking se related saare tools — LLM in tools ko call karta hai conversation ke dauran.

**Tools (Functions):**

| Tool | Kya karta hai |
|------|---------------|
| `get_available_treatments()` | Clinic ki saari treatments list deta hai |
| `get_available_timeslots(treatment_name, desired_date)` | Available time slots dhundta hai |
| `select_timeslot(slot_number)` | Customer ka chosen slot store karta hai |
| `samle_email(email)` | Email validate aur store karta hai |
| `sett_booking_preference(preference)` | Booking preference store karta hai |
| `sjekk_forste_ledige_time()` | Pehla available slot dhundta hai |
| `sjekk_onsket_time(OnsketDato)` | Specific date par slots dhundta hai |
| `book_time(...)` | Actually appointment book karta hai |

---

### `tools/client.py` — Client Management Tools

**Kya karta hai:** Existing bookings manage karta hai — details fetch, cancel, change.

**Tools:**

| Tool | Kya karta hai |
|------|---------------|
| `get_client_detail(personnr)` | Customer ki booking details fetch karta hai |
| `cancel_booking(...)` | Booking cancel karta hai |
| `change_appointment_date()` | Appointment date change ka workflow |
| `update_appointment_date(...)` | Actually appointment update karta hai |

---

### `tools/communication.py` — Communication Tools

**Kya karta hai:** Call transfer, message leaving, aur DTMF (keypad input) collection.

**Tools:**

| Tool | Kya karta hai |
|------|---------------|
| `videresend_til_menneske(grunn)` | Call ko human agent ko transfer karta hai (SIP) |
| `legg_igjen_beskjed(...)` | Customer ka message record karta hai staff ke liye |
| `samle_personnummer_med_dtmf()` | 11-digit personnummer phone keypad se collect karta hai |
| `samle_telefonnummer_med_dtmf()` | Phone number keypad se collect karta hai |
| `hent_telefonnummer_fra_samtale()` | Caller ka phone number return karta hai |

**DTMF kya hai?**
DTMF = Dual-Tone Multi-Frequency — jab aap phone par number press karte ho toh jo "beep" aati hai woh DTMF tone hai. Is project mein customer personnummer (national ID) phone keypad se enter karta hai — secure aur accurate.

---

### `tools/general.py` — General Tools

**Kya karta hai:** Business info, conversation history, language switching.

**Tools:**

| Tool | Kya karta hai |
|------|---------------|
| `get_business_info()` | Business ki info deta hai (hours, prices, services) |
| `sjekk_samtalehistorikk()` | Previous conversations check karta hai |
| `switch_language(language)` | Norwegian ↔ English switch karta hai |

---

### `utils/helpers.py` — Utility Functions

**Functions:**
- `extract_phone_from_room_name()` — Room name se phone number nikalta hai
  - Input: `_+4747788636_FccScBRpKxpE`
  - Output: `+4747788636`
- `generate_conversation_summary()` — Conversation ka short summary generate karta hai (GPT-4o-mini se)

---

### `scripts/api_testing_script.py` — API Testing

**Kya karta hai:** Opus API ko manually test karta hai — saari treatments ke liye slots dhundta hai agle 6 months mein.

**Kab run karna hai:** Development/debugging ke time — jab check karna ho ki Opus API sahi kaam kar raha hai.

---

## 5. Key Modules Explanation

### Agent Logic (core/assistant.py)

Agent ka kaam hai:

1. **Customer ki intent samajhna** — kya chahta hai? Booking? Info? Cancel?
2. **Sahi tool call karna** — booking chahiye toh booking tools, info chahiye toh business info tool
3. **Conversation maintain karna** — context remember karna, follow-up questions poochna
4. **Language handle karna** — Norwegian default, English on request

```
Customer says something
         |
         v
    LLM reads text
    + System prompt (instructions)
    + Business context (from Qdrant)
    + Conversation history
         |
         v
    Decision: What to do?
    ├── Answer question → Generate response
    ├── Book appointment → Call booking tools
    ├── Cancel booking → Call client tools
    ├── Transfer call → Call communication tools
    └── Collect data → Call DTMF tools
```

### Personnummer (National ID) Collection via DTMF

Yeh ek interesting module hai. Norway mein har person ka 11-digit national ID hota hai (personnummer). Booking ke liye yeh zaroori hai.

**Kyun DTMF? Kyun voice se nahi?**
- 11 digits voice mein bolna error-prone hai
- STT kabhi kabhi digits galat sun sakta hai
- DTMF (keypad) 100% accurate hai — har digit exact detect hoti hai

**Flow:**
```
1. Agent bolta hai: "Tast inn personnummeret ditt etterfulgt av firkanttegnet"
   (Enter your personal number followed by the hash key)

2. Customer phone par type karta hai: 2 7 8 2 6 0 9 9 1 6 5 #

3. System detect karta hai:
   - Buffer: ['2','7','8','2','6','0','9','9','1','6','5','#']
   - Hash detected! 
   - 11 digits before hash: 27826099165
   - Valid! Store karo.

4. Agent bolta hai: "Takk, mottatt personnummer som slutter på 9165"
```

**Error Handling:**
- Agar 11 se kam/zyada digits → "Try again"
- Agar non-digits → "Invalid, try again"
- Timeout (30 seconds) → "Could not collect"
- Multiple attempts allowed

### Qdrant Search Logic (innstillinger.py)

```
Phone number: +4723507256
        |
        v
Qdrant Filter:
  kind = "agent_data_chunk"
  AND (phone_number = "+4723507256" OR PhoneNumber = "4723507256")
        |
        v
Result: Business settings dict
        |
        v
Qdrant Filter (second query):
  kind = "website_knowledge_chunk"
  AND BusinessId = "9ebf79ad-..."
        |
        v
Result: Combined website content string
```

### API Integration Layer (OPUS_routes.py)

Har API call same pattern follow karti hai:

```python
async def some_api_call(params):
    # 1. Check token exists
    if not OPUS_BEARER_TOKEN:
        return []
    
    # 2. Build URL and headers
    url = f"{OPUS_API_URL}/api/Opus/endpoint"
    headers = {"Authorization": f"Bearer {OPUS_BEARER_TOKEN}"}
    
    # 3. Make HTTP request (aiohttp - async)
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                return []
    
    # 4. Error handling
    except Exception as e:
        print(f"Error: {e}")
        return []
```

---

## 6. Environment Setup

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.12+ | Main programming language |
| **pip** | Latest | Python package manager |
| **venv** | Built-in | Virtual environment |
| **Git** | Latest | Version control |

### Environment Variables (.env files)

Project mein do .env files hain:

**`.env.global`** — Saare environments ke liye common variables  
**`.env.local`** — Local overrides (yeh `.gitignore` mein hona chahiye)

#### Required API Keys:

```bash
# ── LiveKit (Real-time audio) ──
LIVEKIT_URL=wss://your-livekit-server.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxx
LIVEKIT_API_SECRET=your-secret-here
AGENT_NAME=ai-receptionist
SIP_TRUNK_ID=ST_xxxxxxxxxxxxx

# ── OpenAI (STT + LLM) ──
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx

# ── ElevenLabs (TTS - Text to Speech) ──
ELEVEN_API_KEY=your-elevenlabs-key

# ── Qdrant (Vector Database) ──
QDRANT_URL=https://your-qdrant-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-key
QDRANT_COLLECTION_NAME=business_knowledge

# ── Opus API (Clinic Management) ──
OPUS_API_URL=https://api.resepsjon.framsynt.com
OPUS_BEARER_TOKEN=your-opus-jwt-token
OPUS_USE_TEST_ENV=true
OPUS_PREFERRED_CLINICIAN_ID=8692
OPUS_CLINIC_ID=471-15f8ea64-137c-4483-835e-144919e58149

# ── Webhook URLs (n8n - fallback) ──
BOOK_TIME=https://n8n.csdevhub.com/webhook/book-time
LEGG_IGJEN_BESKJED=https://n8n.csdevhub.com/webhook/leave_message
GET_CLIENT_DETAIL=https://n8n.csdevhub.com/webhook/get_client_detail
CANCEL_BOOKING=https://n8n.csdevhub.com/webhook/cancel_booking
UPDATE_APPOINTMENT=https://n8n.csdevhub.com/webhook/update_appointment_date
```

#### Har Key ka Purpose:

| Key | Kahan se milega | Kya karta hai |
|-----|-----------------|---------------|
| LIVEKIT_URL | [livekit.io](https://livekit.io) dashboard | LiveKit server se connect karta hai |
| OPENAI_API_KEY | [platform.openai.com](https://platform.openai.com) | STT + LLM ke liye (sunna + sochna) |
| ELEVEN_API_KEY | [elevenlabs.io](https://elevenlabs.io) | TTS ke liye (bolna) |
| QDRANT_URL | [qdrant.io](https://qdrant.io) dashboard | Business data store karta hai |
| OPUS_BEARER_TOKEN | Opus admin se milega | Clinic system se baat karta hai |
| SIP_TRUNK_ID | LiveKit dashboard → SIP | Phone calls route karta hai |

---

## 7. How to Run the Project

### Local Development

**Step 1: Repository clone karo**
```bash
git clone <repository-url>
cd agent_work
```

**Step 2: Virtual environment create karo**
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

**Step 3: Dependencies install karo**
```bash
pip install -r requirements.txt
```

**Step 4: Environment variables set karo**
```bash
# .env.global file create karo aur saare variables add karo
# (upar section 6 mein list hai)
```

**Step 5: Agent start karo**

**Worker Mode** (actual calls handle karta hai):
```bash
python agent.py start
```

**Console Mode** (testing ke liye — microphone se baat karo):
```bash
python agent.py console
```

#### Kya kya run hota hai:

| Component | Port | Purpose |
|-----------|------|---------|
| Agent Worker | 8082 | LiveKit se connect hota hai |
| LiveKit Server | Remote (cloud) | Audio routing |
| Qdrant | Remote (cloud) | Business data |
| Opus API | Remote (cloud) | Appointments |

### Console Flow — Kya hota hai jab project start hota hai

```
$ python agent.py console

[ENTRYPOINT] Initial phone number from room name: +4723507256
[INNSTILLINGER] Querying agent_data_chunk for phone: +4723507256
[INNSTILLINGER] Full data: { "business_name": "Oslo Dental", ... }
[ENTRYPOINT] Successfully fetched business settings
[OPUS] Fetching treatments for business: 9ebf79ad-...
[OPUS] Successfully fetched 13 treatments.
[CALL DATA] business_id: 9ebf79ad-...
[CALL DATA] Phone number from room: +4723507256

============================================================
[FULL PROMPT]
============================================================
CRITICAL LANGUAGE HANDLING:
- You are bilingual (Norwegian + English)...
...
Du er Sofia, AI-resepsjonist hos Oslo Dental Clinic.
============================================================

Agent is ready! Speak into your microphone...
```

**Log lines ka matlab:**
- `[ENTRYPOINT]` — Main startup logs
- `[INNSTILLINGER]` — Qdrant/settings related
- `[OPUS]` — Opus API calls
- `[CALL DATA]` — Call session info
- `[FULL PROMPT]` — LLM ko di gayi instructions
- `[TOOL]` — Tool execution logs
- `[WEBHOOK]` — Webhook API calls
- `[DTMF]` — Keypad input detection
- `[PERSONNUMMER]` — Personal ID collection
- `[PHONE]` — Phone number collection

### Production Setup

**Deployment typically involves:**

1. **Docker container** mein agent package karo
2. **LiveKit Cloud** use karo (ya self-hosted LiveKit server)
3. **Telnyx** par SIP trunk configure karo → LiveKit room ko point karo
4. **Environment variables** production values se set karo
5. **Multiple workers** run karo (scaling ke liye)

**Scaling basics:**
- Har agent worker ek time mein ek call handle karta hai
- Zyada concurrent calls chahiye → zyada workers start karo
- LiveKit automatically calls ko available workers mein distribute karta hai
- Qdrant aur Opus API stateless hain → scale karne mein problem nahi

---

## 8. Example Walkthrough

### Scenario: Customer wants to book a dental examination

**Customer calls +47 23507256**

---

**Step 1: System Startup**

```
[Internal] Telnyx receives call → routes to LiveKit room
[Internal] agent.py entrypoint() fires
[Internal] Phone: +4723507256 → Qdrant fetch → Oslo Dental Clinic settings
[Internal] Opus API → 13 treatments fetched
[Internal] Agent session created (STT + LLM + TTS)
```

**Step 2: Greeting**

```
Agent: "Hei, jeg heter Sofia og er en AI resepsjonist for Oslo Dental Clinic. 
        Hva kan jeg hjelpe deg med?"
```

**Step 3: Customer request**

```
Customer: "I want to book an appointment for a dental checkup"
```

```
[Internal] STT converts audio to text: "I want to book an appointment for a dental checkup"
[Internal] LLM reads text → detects: booking request + treatment type = examination
[Internal] LLM decides: ask about date preference
```

**Step 4: Date preference**

```
Agent: "Great! Would you like the first available appointment, or do you have 
        a specific date in mind?"

Customer: "First available please"
```

```
[Internal] LLM → calls sett_booking_preference("first_available")
[Internal] LLM → NOW calls samle_personnummer_med_dtmf() immediately
```

**Step 5: Personnummer collection (DTMF)**

```
Agent: "Please enter your personal identification number on your phone 
        followed by the hash key."

Customer: [Types on phone keypad: 2-7-8-2-6-0-9-9-1-6-5-#]

[Internal] DTMF digits received: ['2','7','8','2','6','0','9','9','1','6','5','#']
[Internal] Hash detected → 11 digits before hash → Valid!

Agent: "Thank you, received personal ID number ending in 9165."
```

**Step 6: Find available slots**

```
[Internal] LLM → calls get_available_timeslots("Recall hos tannlege")
[Internal] → Opus API POST /api/Opus/patient/find-slot
[Internal] → Response: 2 slots found with Dr. Kjetil Høye

Agent: "I found two available time slots with Kjetil Høye (Dentist):
        1. Monday, July 20 from 09:00 to 09:30
        2. Monday, July 20 from 09:30 to 10:00
        Which one would you like to book?"

Customer: "I'll take the first one"
```

```
[Internal] LLM → calls select_timeslot(1)
[Internal] → Slot stored: 09:00-09:30 with Dr. Kjetil Høye
[Internal] → isExistingPatient = true (patient already registered!)
```

**Step 7: Existing patient — direct booking**

```
Agent: "You selected the 09:00 to 09:30 slot with Kjetil Høye. 
        I see you're already registered as Ola Nordmann. 
        Shall I go ahead and book this for you?"

Customer: "Yes please"
```

```
[Internal] LLM → calls book_time()
[Internal] → book_existing_patient() → POST /api/Opus/existing-patient/book
[Internal] → Response: { success: true, bookingId: "BK-12345" }

Agent: "Your appointment is booked, Ola. Your dentist is 
        Kjetil Høye (Dentist). Is there anything else I can help you with?"

Customer: "No, that's all. Thank you!"

Agent: "Thank you for calling Oslo Dental Clinic. Have a great day!"
```

**Step 8: Call ends**

```
[Internal] Customer hangs up
[Internal] participant_disconnected event → save_log()
[Internal] Session cleanup
```

---

## 9. Common Errors & Debugging

### Error 1: "Could not fetch business settings"

```
[ENTRYPOINT] ERROR: Failed to fetch business settings: ...
```

**Kya hua:** Qdrant se business data nahi mila.

**Fix:**
- Check karo QDRANT_URL aur QDRANT_API_KEY sahi hain
- Check karo phone number Qdrant mein exist karta hai
- Check karo collection name sahi hai (`business_knowledge`)

---

### Error 2: "OPUS_BEARER_TOKEN not set"

```
[OPUS] Warning: OPUS_BEARER_TOKEN not set in environment variables.
```

**Kya hua:** Opus API ka token set nahi hai.

**Fix:**
- `.env.global` ya `.env.local` mein `OPUS_BEARER_TOKEN=your-token` add karo
- Token expired ho sakta hai — naya token generate karo

---

### Error 3: DTMF not working / Personnummer not collecting

```
[PERSONNUMMER] Timeout after 30 seconds
```

**Kya hua:** Customer ne phone keypad se digits nahi daale ya # nahi press kiya.

**Fix:**
- Console mode mein DTMF kaam nahi karta (auto-fill hota hai: `23212123212`)
- Real call mein check karo ki SIP trunk DTMF support karta hai
- Customer ko clearly bolna chahiye: "Press digits followed by hash key"

---

### Error 4: "SIP trunk not found"

```
TwirpError creating SIP participant: Code=not_found
```

**Kya hua:** Call transfer ke time SIP trunk nahi mila.

**Fix:**
- `SIP_TRUNK_ID` environment variable check karo
- LiveKit dashboard mein SIP trunk verify karo
- SIP trunk ID format check karo (usually `ST_` se start hota hai)

---

### Error 5: "No treatments available"

```
[OPUS] Error fetching treatments. Status: 401
```

**Kya hua:** Opus API authentication fail ho gayi.

**Fix:**
- `OPUS_BEARER_TOKEN` check karo — expired ho sakta hai
- `OPUS_API_URL` sahi hai check karo
- `OPUS_USE_TEST_ENV` sahi value hai check karo

---

### Error 6: Webhook timeout

```
[WEBHOOK] All 3 attempts timed out
```

**Kya hua:** n8n webhook respond nahi kar raha.

**Fix:**
- n8n server running hai check karo
- Webhook URLs sahi hain check karo
- Network connectivity check karo

---

### General Debugging Tips:

1. **Logs padho** — saare logs `[TAG]` ke saath aate hain, filter kar sakte ho
2. **Console mode use karo** — `python agent.py console` — bina real call ke test karo
3. **Opus test script** — `scripts/api_testing_script.py` run karo API check karne ke liye
4. **Environment variables** — sabse pehle check karo ki saare variables set hain
5. **Qdrant data** — verify karo ki phone number ke against data exist karta hai

---

## 10. Summary

### Pura system ek line mein:

> **Customer phone karta hai → Telnyx receive karta hai → LiveKit audio stream karta hai → AI sunti hai (STT) → sochti hai (LLM + Qdrant + Opus) → bolti hai (TTS) → Customer sunta hai**

### Technology Stack:

```
+-------------------+------------------------------------+
| Component         | Technology                         |
+-------------------+------------------------------------+
| Phone Network     | Telnyx (SIP)                       |
| Real-time Audio   | LiveKit                            |
| Speech-to-Text    | OpenAI gpt-4o-transcribe           |
| AI Brain (LLM)    | OpenAI GPT-4o                      |
| Text-to-Speech    | ElevenLabs eleven_turbo_v2_5       |
| Voice Detection   | Silero VAD                         |
| Turn Detection    | LiveKit Multilingual Model         |
| Business Data     | Qdrant Vector Database             |
| Clinic System     | Opus API                           |
| Noise Cancel      | LiveKit BVC Telephony              |
| Language          | Python 3.12 (async)                |
| Webhooks          | n8n (fallback)                     |
+-------------------+------------------------------------+
```

### Key Features:

- Bilingual: Norwegian (default) + English
- DTMF-based secure data collection (personnummer, phone)
- Real-time appointment booking/cancellation/rescheduling
- Natural voice (ElevenLabs)
- Noise cancellation for phone calls
- Automatic caller identification
- Fallback to human agent (call transfer)
- Message leaving when agent can't help
- Conversation history tracking

### Architecture Pattern:

```
[Telnyx] → [LiveKit] → [Agent Session]
                              |
                    +---------+---------+
                    |         |         |
                  [STT]    [LLM]    [TTS]
                            |
                     +------+------+
                     |             |
                  [Tools]      [Prompt]
                     |
              +------+------+------+
              |      |      |      |
          Booking  Client  Comm  General
              |      |      |
           [Opus]  [n8n]  [SIP]
              |      |
           [Qdrant for business data]
```

---

> **Note:** Yeh ek living document hai. Jab bhi project mein changes aayein, yeh documentation bhi update honi chahiye.
