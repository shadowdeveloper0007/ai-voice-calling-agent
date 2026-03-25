import sys
import re
import asyncio
import signal
import threading

from livekit import agents, rtc
from livekit.agents import AgentSession, APIConnectOptions, RoomInputOptions
from livekit.agents.voice.agent_session import SessionConnectOptions
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
from utils.helpers import extract_phone_from_room_name
from innstillinger import fetch_business_settings_by_phone
from OPUS_routes import get_clinic_treatments


async def entrypoint(ctx: agents.JobContext):
    is_console_mode = "console" in sys.argv
    
    phone_number = extract_phone_from_room_name(ctx.room.name)
    
    if not phone_number:
        phone_number = "+4723507256"
    
    print(f"[ENTRYPOINT] Initial phone number from room name: {phone_number}")
    
    # Fetch business settings at startup using phone number
    try:
        cfg.business_settings = await fetch_business_settings_by_phone(phone_number)
        print(f"[ENTRYPOINT] Successfully fetched business settings for phone: {phone_number}")
    except Exception as e:
        print(f"[ENTRYPOINT] ERROR: Failed to fetch business settings: {e}")
        raise RuntimeError(f"Could not fetch business settings for phone number: {phone_number}. Error: {e}")
    
    business_settings = cfg.business_settings

    # Fetch clinic treatments (Opus API)
    clinic_treatments = []
    if business_settings and 'business_id' in business_settings:
        try:
            clinic_treatments = await get_clinic_treatments(business_settings['business_id'])
            print(f"[ENTRYPOINT] Fetched {len(clinic_treatments)} treatments for business {business_settings['business_id']}")
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
    llm_model = business_settings.get('llm_model', 'gpt-4o')
    stt_prompt = business_settings.get('stt_prompt', 'This is a conversation between an AI receptionist and a customer. The conversation can be in either Norwegian or English. Transcribe accurately in the language being spoken with correct punctuation and formatting.')

    session = AgentSession(
        stt=openai.STT(
            model=stt_model,
            prompt=stt_prompt
        ),
        llm=openai.LLM(
            model='gpt-4o',
            temperature=0.4
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
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
        max_tool_steps=8,
        preemptive_generation=True,
        conn_options=SessionConnectOptions(
            llm_conn_options=APIConnectOptions(timeout=60.0),
        ),
    )

    # Initialize CallData for the session
    business_id = business_settings.get('business_id', '') if business_settings else ''
    call_data = CallData(phone_number=phone_number or "", business_id=business_id, is_console_mode=is_console_mode)
    if call_data.dtmf_event is None:
        call_data.dtmf_event = asyncio.Event()
    
    print(f"[CALL DATA] business_id: {call_data.business_id}")
    print(f"[CALL DATA] Phone number from room: {phone_number}")
    print(f"[CALL DATA] CallData phone_number: {call_data.phone_number}")
    
    await ctx.connect()
    
    # Check existing participants for caller's phone number
    async def check_existing_participants():
        """Check existing participants to extract caller's phone number - THIS IS THE CORRECT NUMBER TO USE"""
        await asyncio.sleep(0.5)
        if ctx.room:
            for participant in ctx.room.remote_participants.values():
                if participant.identity.startswith('sip_'):
                    identity = participant.identity
                    print(f"[EXISTING PARTICIPANT] Identity: {identity}")
                    phone_match = re.search(r'\+47\d{8}', identity)
                    if phone_match:
                        extracted_number = phone_match.group(0)
                        if call_data:
                            print(f"[EXISTING PARTICIPANT] Using identity number as caller number: {extracted_number} (was: {call_data.phone_number})")
                            call_data.phone_number = extracted_number
                            print(f"[CALL DATA] Updated phone_number to: {call_data.phone_number} - THIS IS THE NUMBER TO USE")
                            return
                    else:
                        phone_match = re.search(r'\+?\d{8,15}', identity)
                        if phone_match:
                            extracted_number = phone_match.group(0)
                            if not extracted_number.startswith('+'):
                                extracted_number = f"+{extracted_number.lstrip('+')}"
                            if call_data:
                                print(f"[EXISTING PARTICIPANT] Using identity number as caller number: {extracted_number} (was: {call_data.phone_number})")
                                call_data.phone_number = extracted_number
                                print(f"[CALL DATA] Updated phone_number to: {call_data.phone_number} - THIS IS THE NUMBER TO USE")
                                return
    
    asyncio.create_task(check_existing_participants())
    
    @ctx.room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        """Extract actual caller's phone number from SIP participant - USE IDENTITY NUMBER"""
        if participant.identity.startswith('sip_'):
            identity = participant.identity
            print(f"[PARTICIPANT CONNECTED] Identity: {identity}")
            print(f"[PARTICIPANT CONNECTED] Name: {getattr(participant, 'name', 'N/A')}")
            print(f"[PARTICIPANT CONNECTED] Metadata: {getattr(participant, 'metadata', 'N/A')}")
            
            phone_match = re.search(r'\+47\d{8}', identity)
            if phone_match:
                extracted_number = phone_match.group(0)
                if call_data:
                    print(f"[PARTICIPANT CONNECTED] Using identity number as caller number: {extracted_number} (was: {call_data.phone_number})")
                    call_data.phone_number = extracted_number
                    print(f"[CALL DATA] Updated phone_number to: {call_data.phone_number} - THIS IS THE NUMBER TO USE")
                    return
            else:
                phone_match = re.search(r'\+?\d{8,15}', identity)
                if phone_match:
                    extracted_number = phone_match.group(0)
                    if not extracted_number.startswith('+'):
                        extracted_number = f"+{extracted_number.lstrip('+')}"
                    if call_data:
                        print(f"[PARTICIPANT CONNECTED] Using identity number as caller number: {extracted_number} (was: {call_data.phone_number})")
                        call_data.phone_number = extracted_number
                        print(f"[CALL DATA] Updated phone_number to: {call_data.phone_number} - THIS IS THE NUMBER TO USE")
                        return
            
            metadata = getattr(participant, 'metadata', None)
            if metadata:
                print(f"[PARTICIPANT] Checking metadata: {metadata}")
                phone_match = re.search(r'\+47\d{8}', metadata)
                if phone_match:
                    extracted_number = phone_match.group(0)
                    if call_data and extracted_number != call_data.phone_number:
                        print(f"[PARTICIPANT] Extracted caller number from metadata: {extracted_number}")
                        call_data.phone_number = extracted_number
                        print(f"[CALL DATA] Updated phone_number to: {call_data.phone_number}")
                        return
            
            name = getattr(participant, 'name', None)
            if name:
                print(f"[PARTICIPANT] Checking name: {name}")
                phone_match = re.search(r'\+47\d{8}', name)
                if phone_match:
                    extracted_number = phone_match.group(0)
                    if call_data and extracted_number != call_data.phone_number:
                        print(f"[PARTICIPANT] Extracted caller number from name: {extracted_number}")
                        call_data.phone_number = extracted_number
                        print(f"[CALL DATA] Updated phone_number to: {call_data.phone_number}")
                        return
            
            print(f"[PARTICIPANT] Could not extract caller number from participant. Using room name number: {call_data.phone_number if call_data else 'N/A'}")
    
    def normalize_dtmf_digit(raw_digit):
        """Normalize DTMF digit to standard format. Handles various # representations."""
        if raw_digit is None:
            print(f"[DTMF NORMALIZE] Input is None")
            return None
        
        value = str(raw_digit).strip()
        if not value:
            print(f"[DTMF NORMALIZE] Empty value after conversion")
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
                print(f" -> ✗ FAILED TO NORMALIZE (returned None) - THIS DTMF WAS NOT ADDED!")
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
            except Exception as e:
                pass
        
        asyncio.create_task(save_log())
    
    booking_config = business_settings.get('bookingkonfigurasjoner', {})
     # prompt_template = business_settings.get('prompt', '')
    prompt_template = ANBEFALT
    business_type = business_settings.get('business_type', 'business')
    business_name = business_settings.get('business_name', 'Business')
    booking_term = business_settings.get('booking_term', 'booking')
    custom_terms = business_settings.get('custom_terms', None)
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
