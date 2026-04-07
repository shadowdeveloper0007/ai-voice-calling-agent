import sys
import re
import asyncio
import signal
import threading

from livekit import agents, rtc
from livekit.agents import AgentSession, APIConnectOptions, RoomInputOptions
from livekit.agents.voice.agent_session import SessionConnectOptions
from livekit.agents.job import JobProcess
from livekit.plugins import (
    openai,
    elevenlabs,
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import config.constants as cfg
from config.constants import ANBEFALT
from core.call_data import CallData
from core.assistant import Assistant
from utils.helpers import parse_room_name
from utils.cache import TTLCache
from innstillinger import fetch_business_settings_by_phone
from OPUS_routes import get_clinic_treatments

# Latency optimization
MIN_ENDPOINTING_DELAY = 0.08
MAX_ENDPOINTING_DELAY = 0.35
PREEMPTIVE_GENERATION = True
FALSE_INTERRUPTION_TIMEOUT = 0.25
MIN_INTERRUPTION_DURATION = 0.12


def prewarm(proc: JobProcess) -> None:
    # Cache heavy model initialization per worker process/thread.
    proc.userdata["vad"] = silero.VAD.load()
    # MultilingualModel needs JobContext (inference_executor); init in entrypoint only.

async def entrypoint(ctx: agents.JobContext):
    is_console_mode = "console" in sys.argv
    
    room_data = parse_room_name(ctx.room.name)
    phone_number = room_data.get("agent_number")
    caller_phone = room_data.get("user_number") or ""
    room_business_id = room_data.get("business_id") or ""

    if not phone_number:
        phone_number = "+4723507256"

    print(f"[ENTRYPOINT] Room parse: agent_number={phone_number}, caller_phone={caller_phone}, business_id={room_business_id}")
    
    def _norm_phone(n: str) -> str:
        return ("+" + "".join(ch for ch in (n or "") if ch.isdigit())) if n else ""

    # 30-min in-memory cache (per worker process), bucketed by agent_number
    if "settings_cache_by_agent" not in ctx.proc.userdata:
        ctx.proc.userdata["settings_cache_by_agent"] = {}
    if "treatments_cache_by_agent" not in ctx.proc.userdata:
        ctx.proc.userdata["treatments_cache_by_agent"] = {}

    agent_bucket = _norm_phone(phone_number)
    if not agent_bucket:
        agent_bucket = "unknown-agent"

    settings_cache_by_agent = ctx.proc.userdata["settings_cache_by_agent"]
    treatments_cache_by_agent = ctx.proc.userdata["treatments_cache_by_agent"]

    if agent_bucket not in settings_cache_by_agent:
        settings_cache_by_agent[agent_bucket] = TTLCache(ttl_seconds=1800.0, max_items=256)
    if agent_bucket not in treatments_cache_by_agent:
        treatments_cache_by_agent[agent_bucket] = TTLCache(ttl_seconds=1800.0, max_items=256)

    settings_cache: TTLCache[str, dict] = settings_cache_by_agent[agent_bucket]
    treatments_cache: TTLCache[str, list] = treatments_cache_by_agent[agent_bucket]

    # Fetch business settings at startup using agent/business phone number
    cache_key_settings = f"settings:phone:{agent_bucket}"
    business_settings = settings_cache.get(cache_key_settings)
    if business_settings:
        print(f"[CACHE] business_settings HIT bucket={agent_bucket} key={cache_key_settings}")
    else:
        print(f"[CACHE] business_settings MISS bucket={agent_bucket} key={cache_key_settings}")
        try:
            business_settings = await fetch_business_settings_by_phone(phone_number)
            settings_cache.set(cache_key_settings, business_settings)
            print(f"[ENTRYPOINT] Successfully fetched business settings for phone: {phone_number}")
        except Exception as e:
            print(f"[ENTRYPOINT] ERROR: Failed to fetch business settings: {e}")
            raise RuntimeError(f"Could not fetch business settings for phone number: {phone_number}. Error: {e}")

    cfg.business_settings = business_settings

    # Fetch clinic treatments (Opus API)
    clinic_treatments = []
    if business_settings and "business_id" in business_settings:
        bid = str(business_settings["business_id"])
        cache_key_treatments = f"treatments:business_id:{bid}"
        clinic_treatments = treatments_cache.get(cache_key_treatments) or []
        if clinic_treatments:
            print(f"[CACHE] clinic_treatments HIT bucket={agent_bucket} key={cache_key_treatments} ({len(clinic_treatments)})")
        else:
            print(f"[CACHE] clinic_treatments MISS bucket={agent_bucket} key={cache_key_treatments}")
            try:
                clinic_treatments = await get_clinic_treatments(bid)
                treatments_cache.set(cache_key_treatments, clinic_treatments)
                print(f"[ENTRYPOINT] Fetched {len(clinic_treatments)} treatments for business {bid}")
            except Exception as e:
                print(f"[ENTRYPOINT] Warning: Failed to fetch treatments: {e}")
    
    # QDRANT CONVERSATION HISTORY COMMENTED OUT - QDRANT NOT WORKING
    conversation_history = None
    
    # Get voice settings from business configuration
    voice_config = business_settings.get('voice', {})
    voice_id = voice_config.get('id', 'uNsWM1StCcpydKYOjKyu')
    voice_stability = voice_config.get('stability', 0.5)
    voice_similarity = voice_config.get('similarity_boost', 0.75)
    voice_speed = voice_config.get('speed', 1.0)
    
    # Get model settings from business configuration
    stt_model = business_settings.get('stt_model', 'gpt-4o-transcribe')
    # llm_model = business_settings.get('llm_model', 'gpt-4o')
    stt_prompt = business_settings.get('stt_prompt', 'This is a conversation between an AI receptionist and a customer. The conversation can be in either Norwegian or English. Transcribe accurately in the language being spoken with correct punctuation and formatting.')

    session = AgentSession(
        stt=openai.STT(
            model=stt_model,
            prompt=stt_prompt
        ),
        llm=openai.LLM(
            model='gpt-4o',
            temperature=0.15,
            max_completion_tokens=500,
        ),
        tts=elevenlabs.TTS(
            voice_id=voice_id,
            model="eleven_turbo_v2_5",
            voice_settings=elevenlabs.VoiceSettings(
                stability=voice_stability,
                similarity_boost=voice_similarity,
                speed=voice_speed,
            )
        ),
        vad=ctx.proc.userdata.get("vad") or silero.VAD.load(),
        turn_detection=ctx.proc.userdata.get("turn_detection") or MultilingualModel(),
        max_tool_steps=8,
        conn_options=SessionConnectOptions(
            llm_conn_options=APIConnectOptions(timeout=60.0),
        ),
        min_endpointing_delay=MIN_ENDPOINTING_DELAY,
        max_endpointing_delay=MAX_ENDPOINTING_DELAY,
        preemptive_generation=PREEMPTIVE_GENERATION,
        false_interruption_timeout=FALSE_INTERRUPTION_TIMEOUT,
        min_interruption_duration=MIN_INTERRUPTION_DURATION,
    )

    # Initialize CallData for the session
    business_id = room_business_id or (business_settings.get('business_id', '') if business_settings else '')
    call_data = CallData(phone_number=phone_number or "", caller_phone=caller_phone, business_id=business_id, is_console_mode=is_console_mode)
    if call_data.dtmf_event is None:
        call_data.dtmf_event = asyncio.Event()
    
    print(f"[CALL DATA] business_id: {call_data.business_id}")
    print(f"[CALL DATA] Phone number from room: {phone_number}")
    print(f"[CALL DATA] CallData phone_number: {call_data.phone_number}")
    
    await ctx.connect()
    
    # Check existing participants for caller's phone number
    async def check_existing_participants():
        """Check existing participants to extract caller's phone number into caller_phone."""
        await asyncio.sleep(0.5)
        if ctx.room:
            for participant in ctx.room.remote_participants.values():
                if participant.identity.startswith('sip_'):
                    identity = participant.identity
                    print(f"[EXISTING PARTICIPANT] Identity: {identity}")
                    phone_match = re.search(r'\+47\d{8}', identity) or re.search(r'\+?\d{8,15}', identity)
                    if phone_match:
                        extracted_number = phone_match.group(0)
                        if not extracted_number.startswith('+'):
                            extracted_number = f"+{extracted_number}"
                        if call_data:
                            print(f"[EXISTING PARTICIPANT] Caller phone: {extracted_number} (was: {call_data.caller_phone})")
                            call_data.caller_phone = extracted_number
                            print(f"[CALL DATA] Updated caller_phone to: {call_data.caller_phone}")
                            return
    
    asyncio.create_task(check_existing_participants())
    
    @ctx.room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        """Extract caller's phone number from SIP participant into caller_phone."""
        if participant.identity.startswith('sip_'):
            identity = participant.identity
            print(f"[PARTICIPANT CONNECTED] Identity: {identity}")

            phone_match = re.search(r'\+47\d{8}', identity) or re.search(r'\+?\d{8,15}', identity)
            if phone_match:
                extracted_number = phone_match.group(0)
                if not extracted_number.startswith('+'):
                    extracted_number = f"+{extracted_number}"
                if call_data:
                    print(f"[PARTICIPANT CONNECTED] Caller phone: {extracted_number} (was: {call_data.caller_phone})")
                    call_data.caller_phone = extracted_number
                    print(f"[CALL DATA] Updated caller_phone to: {call_data.caller_phone}")
                    return

            for source_name in ("metadata", "name"):
                source_val = getattr(participant, source_name, None)
                if source_val:
                    m = re.search(r'\+?\d{8,15}', str(source_val))
                    if m:
                        extracted_number = m.group(0)
                        if not extracted_number.startswith('+'):
                            extracted_number = f"+{extracted_number}"
                        if call_data:
                            print(f"[PARTICIPANT] Caller phone from {source_name}: {extracted_number}")
                            call_data.caller_phone = extracted_number
                            return

            print(f"[PARTICIPANT] Could not extract caller number. caller_phone={call_data.caller_phone if call_data else 'N/A'}")
    
    def normalize_dtmf_digit(raw_digit):
        """Normalize DTMF digit to standard format. Handles various # representations."""
        if raw_digit is None:
            print("[DTMF NORMALIZE] Input is None")
            return None
        
        value = str(raw_digit).strip()
        if not value:
            print("[DTMF NORMALIZE] Empty value after conversion")
            return None
        
        print(f"[DTMF NORMALIZE] Processing: '{raw_digit}' -> '{value}'")
        
        if value == "#" or value == "*":
            print(f"[DTMF NORMALIZE] Direct match: '{value}'")
            return value
        
        if len(value) == 1:
            char = value
            if char in "0123456789#*":
                print(f"[DTMF NORMALIZE] Single valid character: '{char}'")
                return char
            elif char in "ABCDabcd":
                print(f"[DTMF NORMALIZE] Single letter: '{char.upper()}'")
                return char.upper()
        
        lower = value.lower()
        
        pound_exact = ["pound", "hash", "number_sign", "number-sign", "num_sign", "num-sign"]
        if lower in pound_exact:
            print(f"[DTMF NORMALIZE] Exact pound match: '{value}' -> '#'")
            return "#"
        
        pound_variants = [
            "pound", "hash", "number_sign", "number-sign", "num_sign", "num-sign",
            "digitpound", "digit-pound", "keypound", "key-pound", "poundkey", "pound-key",
            "dtmf_pound", "dtmf-pound", "sip_pound", "sip-pound"
        ]
        for variant in pound_variants:
            if variant in lower:
                print(f"[DTMF NORMALIZE] Pound variant match: '{value}' (contains '{variant}') -> '#'")
                return "#"
        
        star_exact = ["star", "asterisk"]
        if lower in star_exact:
            print(f"[DTMF NORMALIZE] Exact star match: '{value}' -> '*'")
            return "*"
        
        star_variants = [
            "star", "asterisk", "digitstar", "digit-star", "keystar", "key-star",
            "starkey", "star-key", "dtmf_star", "dtmf-star", "sip_star", "sip-star"
        ]
        for variant in star_variants:
            if variant in lower:
                print(f"[DTMF NORMALIZE] Star variant match: '{value}' (contains '{variant}') -> '*'")
                return "*"
        
        if lower.startswith("digit"):
            digit_part = lower[5:]
            if digit_part.isdigit():
                if digit_part == "11":
                    print(f"[DTMF NORMALIZE] Digit11 format: '{value}' -> '#'")
                    return "#"
                elif digit_part == "10":
                    print(f"[DTMF NORMALIZE] Digit10 format: '{value}' -> '*'")
                    return "*"
                elif len(digit_part) == 1:
                    print(f"[DTMF NORMALIZE] Digit format: '{value}' -> '{digit_part}'")
                    return digit_part
        
        if lower.isdigit():
            if lower == "11":
                print(f"[DTMF NORMALIZE] Numeric code 11: '{value}' -> '#'")
                return "#"
            elif lower == "10":
                print(f"[DTMF NORMALIZE] Numeric code 10: '{value}' -> '*'")
                return "*"
            elif len(lower) == 1:
                print(f"[DTMF NORMALIZE] Single digit: '{value}'")
                return lower
        
        if value and value[-1] in "0123456789#*":
            print(f"[DTMF NORMALIZE] Last character fallback: '{value}' -> '{value[-1]}'")
            return value[-1]
        
        print(f"[DTMF NORMALIZE] ✗ Unrecognized DTMF format: '{raw_digit}' (type: {type(raw_digit)}) -> None")
        return None

    @ctx.room.on("sip_dtmf_received")
    def on_dtmf_received(dtmf_event: rtc.SipDTMF):
        """Handle DTMF digits from SIP participants - enhanced for CloudTalk compatibility"""
        if call_data:
            raw_digit = None
            if hasattr(dtmf_event, 'digit'):
                raw_digit = dtmf_event.digit
            elif hasattr(dtmf_event, 'value'):
                raw_digit = dtmf_event.value
            elif hasattr(dtmf_event, 'key'):
                raw_digit = dtmf_event.key
            else:
                raw_digit = str(dtmf_event)
            
            if raw_digit is None:
                print(f"[DTMF] ERROR: Could not extract digit from DTMF event. Available attributes: {dir(dtmf_event)}")
                return
            
            print(f"[DTMF] Received: '{raw_digit}'", end="")
            digit = normalize_dtmf_digit(raw_digit)
            
            if digit:
                call_data.dtmf_digits.append(digit)
                buffer_str = ''.join(call_data.dtmf_digits)
                is_hash = digit == '#'
                print(f" -> Normalized: '{digit}' | Buffer: '{buffer_str}' | Is Hash: {is_hash}")
                if is_hash:
                    print(f"[DTMF] ✓✓✓ HASH KEY ADDED TO BUFFER! Length: {len(call_data.dtmf_digits)}")
                if call_data.dtmf_event:
                    call_data.dtmf_event.set()
            else:
                print(" -> ✗ FAILED TO NORMALIZE (returned None) - THIS DTMF WAS NOT ADDED!")
                print(f"[DTMF] Raw digit was: '{raw_digit}' (type: {type(raw_digit)})")
    
    # QDRANT CONVERSATION HISTORY COMMENTED OUT - QDRANT NOT WORKING
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        """Handle participant disconnection and save call log"""
        if not participant.identity.startswith('sip_'):
            return
            
        async def save_log():
            try:
                # if call_data.phone_number:
                #     await save_call_log(call_data, business_name)
                print("[ENTRYPOINT] save_log: Call data: " + str(call_data))
            except Exception:
                pass
        
        asyncio.create_task(save_log())
    
    booking_config = business_settings.get('bookingkonfigurasjoner', {})
     # prompt_template = business_settings.get('prompt', '')
    prompt_template = ANBEFALT
    business_type = business_settings.get('business_type', 'business')
    business_name = business_settings.get('business_name', 'Business')
    booking_term = business_settings.get('booking_term', 'booking')
    # custom_terms = business_settings.get('custom_terms', None)
    agent_name = business_settings.get('agent_navn', 'AI Resepsjonist')
    
    assistant = Assistant(
        prompt_template=prompt_template,
        persona_prompt="",
        business_name=business_name,
        booking_config=booking_config,
        call_data=call_data,
        business_info=business_settings.get('business_info', ''),
        job_context=ctx,
        agent_name=agent_name,
        conversation_history=conversation_history,
        business_type=business_type,
        booking_term=booking_term,
        clinic_treatments=clinic_treatments
    )
    
    @session.on("user_input_transcribed")
    def on_user_transcript(transcript):
        if transcript.is_final and call_data:
            call_data.conversation_messages.append({
                "role": "user",
                "content": transcript.transcript
            })

            pending_future = getattr(call_data, "pending_message_future", None)
            if pending_future and not pending_future.done():
                captured_text = transcript.transcript.strip()
                if captured_text:
                    try:
                        pending_future.set_result(captured_text)
                    except Exception:
                        pass
                    finally:
                        call_data.pending_message_future = None

    await session.start(
        room=ctx.room,
        agent=assistant,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

    initial_greeting_no = f"Hils på kunden og tilby hjelp fra {business_name}. Som en AI Resepsjonist. Eksempel: Hei jeg heter {agent_name} og er en AI resepsjonist for {business_name}. Hva kan jeg hjelpe deg med?"
    
    await session.generate_reply(
        instructions=initial_greeting_no + "\n\nIMPORTANT: Language can ONLY be changed when the user EXPLICITLY requests it (e.g., 'speak English', 'can you speak English', 'snakk norsk'). Do NOT auto-detect or change language based on what language the user is speaking. Only call switch_language when the user explicitly asks for a language change."
    )

if __name__ == "__main__":
    def setup_signal_handlers():
        try:
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, signal.SIG_DFL)
        except (ValueError, AttributeError):
            pass
    
    try:
        from livekit.agents.ipc import supervised_proc
        from contextlib import contextmanager
        
        if hasattr(supervised_proc, '_mask_ctrl_c'):
            original_mask_ctrl_c = supervised_proc._mask_ctrl_c
            
            @contextmanager
            def patched_mask_ctrl_c():
                try:
                    with original_mask_ctrl_c():
                        yield
                except ValueError:
                    yield
            
            supervised_proc._mask_ctrl_c = patched_mask_ctrl_c
    except (ImportError, AttributeError):
        pass
    
    setup_signal_handlers()
    
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
        initialize_process_timeout=60.0,
        port=8082,
        ws_url=cfg.LIVEKIT_URL or None,
        api_key=cfg.LIVEKIT_API_KEY or None,
        api_secret=cfg.LIVEKIT_API_SECRET or None,
        agent_name=cfg.AGENT_NAME,
        
    ))


# def main():
#     """Entry point for running the AI receptionist agent."""
#     agent_name = os.getenv('AGENT_NAME', 'DefaultAgent')

#     print(f"Starting AI receptionist agent: {agent_name}")
#     print(f"Running mode: {'console' if 'console' in sys.argv else 'worker'}")

#     if len(sys.argv) > 1 and sys.argv[1] == "console":
#         print("Console mode active — running LiveKit agent normally via CLI.")
    
#     agents.cli.run_app(
#         agents.WorkerOptions(
#             entrypoint_fnc=entrypoint,
#             initialize_process_timeout=60.0,
#             agent_name=agent_name
#         )
#     )

# if __name__ == "__main__":
#     main()
