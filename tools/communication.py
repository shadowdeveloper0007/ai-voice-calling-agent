
import json
import asyncio
import time
import traceback
from datetime import datetime
from typing import Optional

from livekit import api
from livekit.api.twirp_client import TwirpError
from livekit.agents import function_tool, RunContext

import config.constants as cfg


class CommunicationToolsMixin:
    """Mixin containing communication tools (transfer, leave message, DTMF collection)."""

    @function_tool()
    async def videresend_til_menneske(
        self, 
        context: RunContext,
        grunn: str
    ):
        """Overfører samtalen til et menneske"""
        
        ekstern_nummer = cfg.business_settings.get('ekstern_behandler')
        sip_trunk_id = cfg.SIP_TRUNK_ID
        
        if not ekstern_nummer or not sip_trunk_id:
            text = self._get_text("transfer_unavailable") or "Beklager, kan ikke videresende akkurat nå. La meg ta en beskjed."
            context.session.say(
                text,
                allow_interruptions=False
            )
            await context.wait_for_playout()
            return {"suksess": False, "melding": text}
        
        try:
            print(f"Creating SIP participant for {ekstern_nummer} in room {self.job_context.room.name}")
            print(f"SIP trunk ID: {sip_trunk_id}")
            print(f"Room name: {self.job_context.room.name}")
            print(f"Participant identity: {f'transfer_{datetime.now().timestamp()}'}")
            
            if not self.job_context.room or not self.job_context.room.name:
                raise ValueError("Room is not available or room name is missing")
            
            context.session.say(  
                self._get_text("transfer_in_progress") or "Setter deg over nå.",
                allow_interruptions=False
            )
            await context.wait_for_playout()
            
            await self.job_context.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=sip_trunk_id,
                    sip_call_to=ekstern_nummer,
                    room_name=self.job_context.room.name,
                    participant_identity=f"transfer_{datetime.now().timestamp()}",
                    play_dialtone=True
                )
            )
            await context.session.aclose()
            
            return {"suksess": True}
            
        except TwirpError as twirp_exc:
            detailed_error = traceback.format_exc()
            error_code = getattr(twirp_exc, 'code', 'unknown')
            error_message = getattr(twirp_exc, 'message', str(twirp_exc))
            
            print(f"TwirpError creating SIP participant: Code={error_code}, Message={error_message}")
            print(f"Full traceback: {detailed_error}")
            
            if error_code == 'not_found':
                print(f"ERROR: SIP trunk '{sip_trunk_id}' not found in LiveKit. Please verify:")
                print("  1. SIP trunk ID in environment variable SIP_TRUNK_ID is correct")
                print("  2. SIP trunk exists in LiveKit dashboard")
                print("  3. SIP trunk ID format is correct (should start with 'ST_' or similar)")
            elif error_code == 'invalid_argument':
                print("ERROR: Invalid argument provided. Check:")
                print(f"  - Phone number format: {ekstern_nummer}")
                print(f"  - Room name: {self.job_context.room.name if self.job_context.room else 'None'}")
                print(f"  - SIP trunk ID: {sip_trunk_id}")
            
            text = self._get_text("transfer_failed") or "Videresending feilet. La meg heller ta en beskjed."
            context.session.say(
                text,
                allow_interruptions=False
            )
            await context.wait_for_playout()
            return {
                "suksess": False,
                "melding": text,
                "detaljer": f"Error code: {error_code}, Message: {error_message}",
                "error_type": "twirp_error"
            }
        except Exception as exc:
            detailed_error = traceback.format_exc()
            print(f"Unexpected error creating SIP participant: {detailed_error}")
            text = self._get_text("transfer_failed") or "Videresending feilet. La meg heller ta en beskjed."
            context.session.say(
                text,
                allow_interruptions=False
            )
            await context.wait_for_playout()
            return {
                "suksess": False,
                "melding": text,
                "detaljer": str(exc),
                "error_type": "unknown_error"
            }

    @function_tool()
    async def legg_igjen_beskjed(
        self, 
        context: RunContext,
        sammendrag: str,
        telefonnummer: str,
        Fornavn: str,
        Etternavn: str = ""
    ):
        """Legger igjen beskjed til klinikken når agenten ikke kan hjelpe kunden. Oppsummeringen skal være 3-6 setninger som beskriver kundens problem og hvorfor agenten ikke kunne hjelpe."""
        
        if self.call_data and self.call_data.message_sent:
            return {
                "suksess": True,
                "melding": self._get_text("leave_message_success") or ("Your message has already been sent. Is there anything else I can assist you with?" if self._language_code() == "en" else "Beskjeden er allerede sendt. Er det noe mer jeg kan hjelpe deg med?")
            }
        
        telefonnummer = telefonnummer.strip() or self.get_phone_number_for_booking()
        provided_first = Fornavn.strip()
        provided_last = Etternavn.strip()
        summary_value = sammendrag if sammendrag is not None else ""
        
        update_task = None
        
        async def periodic_updates():
            """Gir brukeren oppdateringer hvert 3. sekund"""
            update_messages = self._get_text_list("leave_message_updates")
            if not update_messages:
                update_messages = [
                    "Jeg forstår situasjonen, la meg notere dette for deg...",
                    "Registrerer all informasjonen...",
                    "Sender beskjed til våre ansatte...",
                    "Snart ferdig med å legge igjen beskjeden...",
                    "Vent litt mens jeg fullfører registreringen...",
                    "Sørger for at beskjeden kommer fram...",
                ]
            message_index = 0
            
            await asyncio.sleep(3.0)
            
            while True:
                try:
                    context.session.say(
                        update_messages[message_index],
                        allow_interruptions=False
                    )
                    await context.wait_for_playout()
                    message_index = (message_index + 1) % len(update_messages)
                    await asyncio.sleep(3.0)
                except asyncio.CancelledError:
                    break
                except Exception:
                    break
        
        try:
            context.session.say(
                self._get_text("leave_message_intro") or "Jeg beklager at jeg ikke kan hjelpe deg direkte med dette. La meg legge igjen en beskjed til våre ansatte så de kan kontakte deg.",
                allow_interruptions=False
            )
            await context.wait_for_playout()

            fornavn_clean, etternavn_clean = await self._ensure_customer_name(
                context,
                provided_first,
                provided_last,
                force_prompt=not provided_first and not (self.call_data and self.call_data.customer_first_name)
            )

            captured_message: Optional[str] = None
            if self.call_data and self.call_data.recorded_message:
                captured_message = self.call_data.recorded_message

            if not captured_message and not summary_value:
                captured_message = await self._capture_customer_message(context)
            elif not captured_message and summary_value:
                captured_message = summary_value.strip()

            if captured_message and summary_value:
                base_message = captured_message.strip()
                extra = summary_value.strip()
                if base_message.lower() == extra.lower():
                    summary_value = base_message
                else:
                    summary_value = f"{base_message}\n\nTilleggsinfo: {extra}"
            elif captured_message:
                summary_value = captured_message.strip()
            elif not summary_value:
                summary_value = self._default_message_summary()

            other_info = self._compose_other_info(summary_value)
            update_task = asyncio.create_task(periodic_updates())

            webhook_url = cfg.LEGG_IGJEN_BESKJED_URL
            
            data = {
                "Summary": summary_value,
                "CustomerNumber": telefonnummer,
                "OtherInfo": other_info,
                "StartTime": "",
                "EndTime": "",
                "TreatmentID": "",
                "ClinicianID": "",
                "ClinicID": self.booking_config.get("ClinicID", ""),
                "FirstName": fornavn_clean,
                "LastName": etternavn_clean,
            }

            if not etternavn_clean:
                data.pop("LastName")
            
            data.update(self.booking_config)
            
            print(f"[WEBHOOK] POST {webhook_url}")
            print(f"[WEBHOOK PAYLOAD] {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            webhook_response = await self._call_webhook_with_retry('POST', webhook_url, data)
            
            if webhook_response is None:
                return {
                    "suksess": False,
                    "melding": self._status_error_message(0)
                }
            
            response_status = webhook_response['status']
            response_text = webhook_response['text']
            result = webhook_response['json'] if webhook_response['json'] is not None else response_text
            
            print(f"[WEBHOOK RESPONSE] Status: {response_status}")
            print(f"[WEBHOOK RESPONSE] Body: {json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, dict) else response_text}")
            
            if response_status == 200:
                            if update_task:
                                update_task.cancel()
                                try:
                                    await update_task
                                except asyncio.CancelledError:
                                    pass
                            
                            if self.call_data:
                                self.call_data.conversation_messages.append({
                                    "role": "system",
                                    "content": f"Beskjed lagt igjen til ansatte: {summary_value}"
                                })
                                self.call_data.message_sent = True
                            
                            success_text = self._get_text("leave_message_success")
                            if not success_text:
                                success_text = "Your message has been sent to our staff. Is there anything else I can assist you with?" if self._language_code() == "en" else "Beskjeden er sendt til våre ansatte. Er det noe mer jeg kan hjelpe deg med?"
                            context.session.say(success_text, allow_interruptions=False)
                            await context.wait_for_playout()
                            return {
                                "suksess": True,
                                "melding": success_text
                            }
            else:
                return {
                    "suksess": False,
                    "melding": self._status_error_message(response_status)
                }
                    
        finally:
            if update_task:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
    
    @function_tool()
    async def hent_telefonnummer_fra_samtale(self, context: RunContext) -> str:
        """Henter telefonnummeret kunden ringer fra (caller_phone)."""
        if self.call_data:
            num = self.call_data.caller_phone or self.call_data.phone_number
            if num:
                return num
        return self._get_text("phone_number_unavailable") or ("Phone number not available" if self._language_code() == "en" else "Telefonnummer ikke tilgjengelig")

    @function_tool()
    async def confirm_phone_number_for_booking(self, context: RunContext, use_calling_number: bool) -> str:
        """
        Confirm which phone number to use for booking.

        - If use_calling_number=true: mark confirmed and use caller_phone for booking.
        - If use_calling_number=false: collect a different phone via samle_telefonnummer_med_dtmf() and mark confirmed.
        """
        if not self.call_data:
            return "Ingen aktive samtaledata tilgjengelig." if self._language_code() == "no" else "No call data available."

        if use_calling_number:
            self.call_data.phone_choice_confirmed = True
            return "Takk! Jeg bruker nummeret du ringer fra." if self._language_code() == "no" else "Thanks! I’ll use the number you’re calling from."

        await self.samle_telefonnummer_med_dtmf(context)
        self.call_data.phone_choice_confirmed = True
        if self._language_code() == "en":
            return "Thanks! I’ll use the new number you entered."
        return "Takk! Jeg bruker det nye nummeret du tastet inn."
    
    def _get_language_messages(self) -> dict:
        """Base language-specific messages (instruction may be overridden by purpose)."""
        if self.call_data and self.call_data.language == "en":
            return {
                "already_collected": "Thanks — I already have your personal ID number saved, so you don’t need to enter it again.",
                "instruction": "Please enter your 11-digit personal ID number on your phone keypad, then press #.",
                "confirmation": "Thank you, received personal ID number ending in {last_four}.",
                "timeout": "I didn’t catch that. Please try again: enter 11 digits, then press hash key.",
                "retry": "Sorry — please try again: enter 11 digits, then press hash key.",
                "invalid": "That didn’t look like 11 digits. Please re-enter your personal ID number, then press hash key.",
                "stored": "Thanks — your personal ID number is saved for this call."
            }
        else:
            return {
                "already_collected": "Takk — jeg har allerede lagret personnummeret ditt, så du trenger ikke taste det inn igjen.",
                "instruction": "Tast inn personnummeret ditt (11 siffer), og trykk deretter firkanttast.",
                "confirmation": "Takk, mottatt personnummer som slutter på {last_four}.",
                "timeout": "Jeg fikk ikke med meg det. Prøv igjen: tast 11 siffer, og trykk deretter firkanttast.",
                "retry": "Beklager — prøv igjen: tast 11 siffer, og trykk deretter firkanttast.",
                "invalid": "Det så ikke ut som 11 siffer. Tast personnummeret på nytt, og trykk deretter firkanttast.",
                "stored": "Takk — personnummeret er lagret for denne samtalen."
            }

    @function_tool()
    async def samle_personnummer_med_dtmf(
        self, 
        context: RunContext,
        purpose: str = "booking",
    ) -> str:
        """Collects personal identification number via DTMF for secure and precise registration.
        
        CRITICAL - YOU MUST CALL THIS FUNCTION IMMEDIATELY:
        - ALWAYS call this function when you need the customer's personal ID number (personnummer) for ANY purpose (booking, cancellation, updating, etc.)
        - Call it IMMEDIATELY when customer says "cancel", "delete", or "remove" booking - do NOT ask verbally first
        - Call it BEFORE calling any booking function (book_time, sjekk_forste_ledige_time, sjekk_onsket_time) if you don't have the personal ID
        - DO NOT ask customer to provide personal ID verbally - ALWAYS use this DTMF function
        - DO NOT say "please provide your personal number" - JUST CALL THIS FUNCTION
        - This function can be called multiple times during a conversation - it always restarts from the beginning
        
        The function will:
        - Always start fresh (clears any previously collected data)
        - Automatically prompt customer to enter 11-digit personal ID number using phone keypad
        - Handle all validation automatically
        - Retry if customer makes mistakes (restarts from beginning)
        - Store the number for use in booking functions
        
        IMPORTANT: This function handles ALL customer instructions automatically. You do NOT need to tell the customer to enter their number - the function does that. Just call it immediately when you need the personal number.
        
        DO NOT proceed with booking/cancellation until this function successfully collects and stores the personal ID number.
        If the function returns an error message, you may need to call it again."""
        
        print("[PERSONNUMMER] ===== FUNCTION CALLED =====")
        print(f"[PERSONNUMMER] Current buffer at start: '{''.join(self.call_data.dtmf_digits) if self.call_data else 'NO CALL DATA'}'")
        print(f"[PERSONNUMMER] Previously collected personnummer: '{self.call_data.collected_personnummer if self.call_data else 'N/A'}'")
        
        messages = self._get_language_messages()
        p = (purpose or "booking").strip().lower()
        if p not in {"booking", "cancellation"}:
            p = "booking"
        # Purpose-specific instruction (more human-friendly)
        if self.call_data and self.call_data.language == "en":
            if p == "cancellation":
                messages["instruction"] = "For cancellation, please enter your 11-digit personal ID number on your phone keypad, then press #."
            else:
                messages["instruction"] = "For booking, please enter your 11-digit personal ID number on your phone keypad, then press hash key."
        else:
            if p == "cancellation":
                messages["instruction"] = "For avlysning, tast inn personnummeret ditt (11 siffer), og trykk deretter firkanttast."
            else:
                messages["instruction"] = "For bestilling, tast inn personnummeret ditt (11 siffer), og trykk deretter firkanttast."
        
        if not self.call_data:
            raise ValueError("No call data available for DTMF collection")
        
        print("[PERSONNUMMER] Resetting for fresh collection - clearing previous data")
        self.call_data.collected_personnummer = ""
        self.call_data.dtmf_digits.clear()
        
        if self.call_data.is_console_mode:
            console_personnummer = "12345678912"
            self.call_data.collected_personnummer = console_personnummer
            context.session.say(
                messages["confirmation"].format(last_four=console_personnummer[-4:]),
                allow_interruptions=False
            )
            await context.wait_for_playout()
            return messages["stored"]
        
        print(f"[PERSONNUMMER] Clearing DTMF buffer. Previous buffer: {''.join(self.call_data.dtmf_digits)}")
        self.call_data.dtmf_digits.clear()
        
        context.session.say(
            messages["instruction"],
            allow_interruptions=False
        )
        await context.wait_for_playout()
        
        timeout_seconds = 30
        start_time = time.time()
        dtmf_event = self._prepare_dtmf_event()
        last_buffer_check = ""
        
        print("[PERSONNUMMER] ===== STARTING DTMF COLLECTION LOOP =====")
        print(f"[PERSONNUMMER] Initial buffer: '{''.join(self.call_data.dtmf_digits)}'")
        
        loop_count = 0
        while True:
            loop_count += 1
            if loop_count % 500 == 0:
                print(f"[PERSONNUMMER] Loop running... checking buffer (count: {loop_count}, buffer: '{''.join(self.call_data.dtmf_digits)}')")
            
            current_buffer = ''.join(self.call_data.dtmf_digits)
            if current_buffer != last_buffer_check:
                print(f"[PERSONNUMMER] Buffer updated: '{current_buffer}' (length={len(self.call_data.dtmf_digits)}, list={self.call_data.dtmf_digits})")
                last_buffer_check = current_buffer
            
            has_hash_in_list = '#' in self.call_data.dtmf_digits
            has_hash_in_string = '#' in current_buffer
            
            if len(self.call_data.dtmf_digits) > 0:
                if has_hash_in_list or has_hash_in_string:
                    print(f"[PERSONNUMMER] Hash check: has_hash_in_list={has_hash_in_list}, has_hash_in_string={has_hash_in_string}, buffer='{current_buffer}'")
            
            if has_hash_in_list or has_hash_in_string:
                print("[PERSONNUMMER] ✓✓✓ HASH KEY DETECTED! Processing validation NOW...")
                print(f"[PERSONNUMMER] Buffer: '{current_buffer}', List: {self.call_data.dtmf_digits}")
                
                try:
                    last_hash_index = len(self.call_data.dtmf_digits) - 1 - list(reversed(self.call_data.dtmf_digits)).index('#')
                    digits_before_last_hash = self.call_data.dtmf_digits[:last_hash_index]
                except ValueError:
                    hash_pos = current_buffer.rfind('#')
                    if hash_pos >= 0:
                        digits_before_last_hash_str = current_buffer[:hash_pos]
                        digits_before_last_hash = list(digits_before_last_hash_str)
                        last_hash_index = hash_pos
                    else:
                        await asyncio.sleep(0.1)
                        continue
                
                num_digits = len(digits_before_last_hash)
                print(f"[PERSONNUMMER] Found # at index {last_hash_index}, digits before hash: {num_digits}")
                
                if num_digits == 11:
                    personnummer = ''.join(digits_before_last_hash)
                    
                    if personnummer.isdigit():
                        print(f"[PERSONNUMMER] ✓ Valid personnummer: {personnummer}")
                        context.session.say(
                            messages["confirmation"].format(last_four=personnummer[-4:]),
                            allow_interruptions=False
                        )
                        await context.wait_for_playout()
                        try:
                            context.session.commit_user_turn(transcript_timeout=0.3, stt_flush_duration=0.2)
                        except Exception:
                            pass
                        self.call_data.collected_personnummer = personnummer
                        self.call_data.dtmf_digits.clear()
                        if dtmf_event:
                            dtmf_event.clear()
                        print("[PERSONNUMMER] FUNCTION COMPLETE - Returning immediately")
                        return messages["stored"]
                    else:
                        print("[PERSONNUMMER] ✗ Invalid format (non-digits)")
                        self.call_data.dtmf_digits.clear()
                        context.session.say(
                            messages.get("invalid", messages["retry"]),
                            allow_interruptions=False
                        )
                        await context.wait_for_playout()
                        context.session.say(
                            messages["instruction"],
                            allow_interruptions=False
                        )
                        await context.wait_for_playout()
                        start_time = time.time()
                        dtmf_event = self._prepare_dtmf_event()
                        last_buffer_check = ""
                        continue
                else:
                    print(f"[PERSONNUMMER] ✗ Wrong number of digits: {num_digits} (need 11)")
                    self.call_data.dtmf_digits.clear()
                    context.session.say(
                        messages.get("invalid", messages["retry"]),
                        allow_interruptions=False
                    )
                    await context.wait_for_playout()
                    context.session.say(
                        messages["instruction"],
                        allow_interruptions=False
                    )
                    await context.wait_for_playout()
                    start_time = time.time()
                    dtmf_event = self._prepare_dtmf_event()
                    last_buffer_check = ""
                    continue

            remaining = timeout_seconds - (time.time() - start_time)
            if remaining <= 0:
                print(f"[PERSONNUMMER] Timeout after {timeout_seconds} seconds")
                return messages["timeout"]

            if dtmf_event:
                try:
                    await asyncio.wait_for(dtmf_event.wait(), timeout=0.05)
                    dtmf_event.clear()
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(0.05)
            continue

    def _get_phone_messages(self) -> dict:
        """Get language-specific phone number collection messages"""
        if self.call_data and self.call_data.language == "en":
            return {
                "instruction": "Enter the phone number followed by the hash key.",
                "readback": "I received the number {phone_number}. Is this correct?",
                "not_confirmed": "The number was incorrect. Please call samle_telefonnummer_med_dtmf function again to collect the correct phone number.",
                "timeout": "Sorry, I didn't receive a number. Please try again.",
                "stored": "Phone number {phone_number} is stored."
            }
        else:
            return {
                "instruction": "Tast inn telefonnummeret etterfulgt av firkanttast.",
                "readback": "Jeg mottok nummeret {phone_number}. Er dette riktig?",
                "not_confirmed": "Nummeret var feil. Vennligst kall samle_telefonnummer_med_dtmf funksjonen igjen for å samle inn riktig telefonnummer.",
                "timeout": "Beklager, jeg mottok ikke noe nummer. Prøver på nytt.",
                "stored": "Telefonnummeret {phone_number} er lagret"
            }

    def _compose_other_info(self, summary: str) -> str:
        """Explain why the customer needed to leave a message"""
        text = (summary or "").lower()
        base = f"Samtale fra {self.business_name}"

        slot_keywords = [
            "no slots", "no availability", "not available", "no available",
            "ingen ledige", "ingen timer", "ingen availability", "fully booked",
            "erne ledige", "busy", "ingen ledig tid", "no times", "not able to find",
            "fant ikke", "couldn't find", "unable to find", "nothing available"
        ]
        date_keywords = [
            "requested date", "specific date", "desired date", "onsket dato",
            "ønsket dato", "datoen", "that date", "den datoen", "particular date"
        ]

        reasons = []
        if any(keyword in text for keyword in slot_keywords):
            reasons.append("Ingen ledige timer")
        if any(keyword in text for keyword in date_keywords):
            reasons.append("Ønsket dato var ikke ledig")

        if not reasons:
            reasons.append("Kunden trenger oppfølging")

        reason_text = ", ".join(reasons)
        return f"Årsak: {reason_text}. {base}"

    @function_tool()
    async def samle_telefonnummer_med_dtmf(
        self,
        context: RunContext
    ) -> str:
        """Collects phone number via DTMF when customer wants to use a different number OR when phone number is needed for booking.
        
        CRITICAL: You MUST call this function immediately whenever:
        - Customer says they want to use a different phone number than the calling number
        - Customer asks to provide/enter a phone number
        - You need a phone number for booking and customer indicates they want to provide one
        - Any situation where phone number collection is required
        - This function can be called multiple times during a conversation - it always restarts from the beginning
        
        IMPORTANT: 
        - If the function returns a message saying the number was incorrect, you MUST call this function again immediately to collect the correct phone number.
        - The function always starts fresh (clears any previously collected data) when called
        - Do not continue with booking until the phone number is confirmed as correct.
        
        Do NOT ask the customer to provide phone number verbally - ALWAYS use this DTMF collection function."""
        
        print("[PHONE] ===== FUNCTION CALLED =====")
        print(f"[PHONE] Current buffer at start: '{''.join(self.call_data.dtmf_digits) if self.call_data else 'NO CALL DATA'}'")
        print(f"[PHONE] Previously collected phone number: '{self.call_data.alternative_phone_number if self.call_data else 'N/A'}'")
        
        messages = self._get_phone_messages()
        
        if not self.call_data:
            raise ValueError("No call data available")
        
        print("[PHONE] Resetting for fresh collection - clearing previous data")
        self.call_data.alternative_phone_number = ""
        self.call_data.dtmf_digits.clear()
        
        if self.call_data.is_console_mode:
            console_phone = "44444444"
            self.call_data.alternative_phone_number = console_phone
            context.session.say(
                messages["confirmation"].format(last_four="4444"),
                allow_interruptions=False
            )
            await context.wait_for_playout()
            return messages["stored"].format(phone_number=console_phone)
        
        print(f"[PHONE] Clearing DTMF buffer to start fresh. Previous buffer: '{''.join(self.call_data.dtmf_digits)}'")
        self.call_data.dtmf_digits.clear()
        
        context.session.say(
            messages["instruction"],
            allow_interruptions=False
        )
        await context.wait_for_playout()
        
        timeout_seconds = 30
        start_time = time.time()
        dtmf_event = self._prepare_dtmf_event()
        if dtmf_event is None:
            print("[PHONE] WARNING: dtmf_event is None after _prepare_dtmf_event()")
        last_buffer_check = ""
        
        loop_count = 0
        print("[PHONE] Starting DTMF collection loop...")
        while True:
            loop_count += 1
            if loop_count % 500 == 0:
                print(f"[PHONE] Loop running... checking buffer (count: {loop_count}, buffer: '{''.join(self.call_data.dtmf_digits)}')")
            
            current_buffer = ''.join(self.call_data.dtmf_digits)
            if current_buffer != last_buffer_check:
                print(f"[PHONE] Buffer updated: '{current_buffer}' (length={len(self.call_data.dtmf_digits)}, list={self.call_data.dtmf_digits})")
                last_buffer_check = current_buffer
            
            has_hash_in_list = '#' in self.call_data.dtmf_digits
            has_hash_in_string = '#' in current_buffer
            
            if len(self.call_data.dtmf_digits) > 0:
                if has_hash_in_list or has_hash_in_string:
                    print(f"[PHONE] ✓ HASH FOUND IN BUFFER! has_hash_in_list={has_hash_in_list}, has_hash_in_string={has_hash_in_string}, buffer='{current_buffer}'")
                elif len(self.call_data.dtmf_digits) % 3 == 0:
                    print(f"[PHONE] Waiting for hash... Current digits: '{current_buffer}'")
            
            if has_hash_in_list or has_hash_in_string:
                print("[PHONE] ✓✓✓ HASH KEY DETECTED! Processing validation NOW...")
                print(f"[PHONE] Buffer: '{current_buffer}', List: {self.call_data.dtmf_digits}")
                
                try:
                    last_hash_index = len(self.call_data.dtmf_digits) - 1 - list(reversed(self.call_data.dtmf_digits)).index('#')
                    digits_before_last_hash = self.call_data.dtmf_digits[:last_hash_index]
                except ValueError:
                    hash_pos = current_buffer.rfind('#')
                    if hash_pos >= 0:
                        digits_before_last_hash_str = current_buffer[:hash_pos]
                        digits_before_last_hash = list(digits_before_last_hash_str)
                        last_hash_index = hash_pos
                    else:
                        await asyncio.sleep(0.1)
                        continue
                
                phone_digits = ''.join(digits_before_last_hash)
                print(f"[PHONE] Extracted digits: {phone_digits}")
                
                if not phone_digits.isdigit():
                    print(f"[PHONE] ✗ Contains non-digits: {phone_digits}")
                    self.call_data.dtmf_digits.clear()
                    context.session.say(
                        messages.get("not_confirmed", messages["timeout"]),
                        allow_interruptions=False
                    )
                    await context.wait_for_playout()
                    context.session.say(
                        messages["instruction"],
                        allow_interruptions=False
                    )
                    await context.wait_for_playout()
                    start_time = time.time()
                    dtmf_event = self._prepare_dtmf_event()
                    last_buffer_check = ""
                    continue
                
                phone_number = phone_digits
                print(f"[PHONE] Collected phone number: {phone_number}")
                
                context.session.say(
                    messages["readback"].format(phone_number=phone_number),
                    allow_interruptions=True
                )
                await context.wait_for_playout()
                await asyncio.sleep(0.5)
                
                try:
                    context.session.commit_user_turn(transcript_timeout=5.0, stt_flush_duration=0.2)
                except Exception:
                    pass
                
                try:
                    loop = asyncio.get_running_loop()
                    future = loop.create_future()
                    
                    pending = getattr(self.call_data, "pending_message_future", None)
                    if pending and not pending.done():
                        pending.cancel()
                    
                    self.call_data.pending_message_future = future
                    try:
                        response_text = await asyncio.wait_for(future, timeout=10.0)
                        response_text = response_text.lower() if response_text else ""
                        print(f"[PHONE] User confirmation response: '{response_text}'")
                    except asyncio.TimeoutError:
                        print("[PHONE] Timeout waiting for confirmation, assuming correct")
                        response_text = ""
                    finally:
                        if self.call_data:
                            self.call_data.pending_message_future = None
                    
                    confirmed_keywords = ["yes", "ja", "riktig", "korrekt", "correct", "right", "that's right", "det stemmer", "stemmer"]
                    not_confirmed_keywords = ["no", "nei", "feil", "wrong", "incorrect", "ikke", "prøv igjen", "try again", "feil nummer"]
                    
                    is_confirmed = any(keyword in response_text for keyword in confirmed_keywords)
                    is_not_confirmed = any(keyword in response_text for keyword in not_confirmed_keywords)
                    
                    if is_confirmed:
                        self.call_data.alternative_phone_number = phone_number
                        self.call_data.dtmf_digits.clear()
                        if dtmf_event:
                            dtmf_event.clear()
                        print("[PHONE] FUNCTION COMPLETE - Returning immediately")
                        return messages["stored"].format(phone_number=phone_number)
                    elif is_not_confirmed:
                        print("[PHONE] User said number is incorrect, restarting from beginning...")
                        self.call_data.dtmf_digits.clear()
                        if dtmf_event:
                            dtmf_event.clear()
                        context.session.say(
                            messages["instruction"],
                            allow_interruptions=False
                        )
                        await context.wait_for_playout()
                        start_time = time.time()
                        dtmf_event = self._prepare_dtmf_event()
                        last_buffer_check = ""
                        continue
                    else:
                        await asyncio.sleep(1.0)
                        context.session.say(
                            messages["readback"].format(phone_number=phone_number),
                            allow_interruptions=True
                        )
                        await context.wait_for_playout()
                        try:
                            context.session.commit_user_turn(transcript_timeout=5.0, stt_flush_duration=0.2)
                        except Exception:
                            pass
                        continue
                        
                except Exception as e:
                    print(f"[PHONE] Error during confirmation: {e}")
                    self.call_data.alternative_phone_number = phone_number
                    self.call_data.dtmf_digits.clear()
                    if dtmf_event:
                        dtmf_event.clear()
                    print("[PHONE] FUNCTION COMPLETE - Returning immediately")
                    return messages["stored"].format(phone_number=phone_number)

            remaining = timeout_seconds - (time.time() - start_time)
            if remaining <= 0:
                print(f"[PHONE] Timeout after {timeout_seconds} seconds")
                context.session.say(
                    messages["timeout"],
                    allow_interruptions=False
                )
                await context.wait_for_playout()
                return "Timeout - customer must provide number verbally"

            if dtmf_event:
                try:
                    await asyncio.wait_for(dtmf_event.wait(), timeout=0.05)
                    dtmf_event.clear()
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(0.05)
            continue

    def get_phone_number_for_booking(self) -> str:
        """Get the appropriate phone number for booking: alternative > caller_phone > agent phone."""
        if self.call_data:
            if self.call_data.alternative_phone_number:
                return self.call_data.alternative_phone_number
            elif self.call_data.caller_phone:
                return self.call_data.caller_phone
            elif self.call_data.phone_number:
                return self.call_data.phone_number
        return ""
