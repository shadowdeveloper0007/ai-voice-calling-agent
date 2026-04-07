import json
import asyncio
import random

from livekit.agents import function_tool, RunContext

from config.constants import UPDATE_APPOINTMENT_URL
from OPUS_routes import get_patient_bookings, cancel_booking_opus


class ClientToolsMixin:
    """Mixin containing client management tools (get details, cancel, change, update)."""

    def _speak_booking_id(self, booking_id: str) -> str:
        """Format booking id for TTS (e.g. '124426' -> '1 2 4 4 2 6')."""
        s = "".join(ch for ch in str(booking_id) if ch.isdigit())
        if not s:
            return ""
        return " ".join(list(s))

    @function_tool()
    async def get_client_detail(
        self, 
        context: RunContext,
        personnr: str = ""
    ):
        """
        Fetches client booking details from Excel sheet using personal number (SSN).
        This function should be called when customer wants to cancel their booking.
        IMPORTANT: This function will automatically collect SSN via DTMF if not already collected.
        However, it is recommended to call samle_personnummer_med_dtmf() first for better user experience.
        """
        
        if self.call_data and self.call_data.collected_personnummer:
            personnr = self.call_data.collected_personnummer
        elif self.call_data:
            await self.samle_personnummer_med_dtmf(context, purpose="cancellation")
            if not self.call_data.collected_personnummer:
                return {
                    "suksess": False,
                    "melding": self._get_text("personnummer_failed")
                }
            personnr = self.call_data.collected_personnummer
        
        update_task = None

        async def periodic_updates():
            """Gir brukeren oppdateringer hvert 2.-3,5. sekund"""
            update_messages = self._get_text_list("get_client_detail_updates")
            if not update_messages:
                if self._language_code() == "en":
                    update_messages = [
                        "Searching for your booking...",
                        "One moment, I'm checking...",
                        "Thank you for your patience..."
                    ]
                else:
                    update_messages = [
                        "Søker etter bookingen din...",
                        "Et øyeblikk, jeg sjekker...",
                        "Takk for tålmodigheten..."
                    ]
            message_index = 0

            await asyncio.sleep(1.0)

            while True:
                try:
                    context.session.say(
                        update_messages[message_index],
                        allow_interruptions=False
                    )
                    await context.wait_for_playout()
                    message_index = (message_index + 1) % len(update_messages)
                    await asyncio.sleep(random.uniform(1.5, 2.5))
                except asyncio.CancelledError:
                    break
                except Exception:
                    break

        try:
            update_task = asyncio.create_task(periodic_updates())

            intro_text = self._get_text("get_client_detail_intro")
            if not intro_text:
                intro_text = "La meg søke etter bookingen din for deg." if self._language_code() == "no" else "Let me look up your booking for you."
            context.session.say(
                intro_text,
                allow_interruptions=False
            )
            await context.wait_for_playout()

            if not self.call_data or not self.call_data.business_id:
                return {
                    "suksess": False,
                    "melding": self._technical_error_message("get_client_detail") or ("Missing business_id" if self._language_code() == "en" else "Mangler business_id"),
                }

            bookings = await get_patient_bookings(
                business_id=self.call_data.business_id,
                pid=personnr,
            )

            if not bookings:
                not_found_text = self._get_text("client_detail_not_found")
                if not not_found_text:
                    not_found_text = "Jeg fant ingen aktiv booking for dette personnummeret." if self._language_code() == "no" else "I couldn't find any active booking for this personal number."
                return {"suksess": False, "melding": not_found_text}

            def _is_cancelled(b: dict) -> bool:
                status = (b.get("status") or b.get("Status") or "").lower()
                return status in {"cancelled", "canceled", "avlyst"} or b.get("alreadyCancelled") is True or b.get("already_cancelled") is True

            booking = next((b for b in bookings if not _is_cancelled(b)), bookings[0])
            status = (booking.get("status") or booking.get("Status") or "").lower()
            is_cancelled = _is_cancelled(booking)

            # OPUS bookings response shape (expected):
            # {
            #   "ID": 124426,
            #   "Patient": {...},
            #   "TimeSlot": {"Start": "...", "End": "...", "ClinicID": "...", "ClinicianID": 8692, "TreatmentID": 52292},
            #   "FreeTextMessage": "...",
            # }
            booking_id = str(
                booking.get("bookingId")
                or booking.get("BookingID")
                or booking.get("id")
                or booking.get("ID")
                or ""
            )

            patient = booking.get("Patient") if isinstance(booking.get("Patient"), dict) else {}
            timeslot = booking.get("TimeSlot") if isinstance(booking.get("TimeSlot"), dict) else {}

            start_time = (
                timeslot.get("Start")
                or booking.get("startTime")
                or booking.get("StartTime")
                or booking.get("slotStart")
                or booking.get("start")
                or booking.get("start_time")
                or ""
            )
            end_time = (
                timeslot.get("End")
                or booking.get("endTime")
                or booking.get("EndTime")
                or booking.get("slotEnd")
                or booking.get("end")
                or booking.get("end_time")
                or ""
            )
            date = booking.get("date") or booking.get("Date") or (start_time[:10] if isinstance(start_time, str) and len(start_time) >= 10 else "")

            # Treatment name is not included in this OPUS response; keep stable fallback for speech.
            treatment = booking.get("treatmentName") or booking.get("treatment") or booking.get("treatment_type") or "behandling"

            date_text = self._format_date_for_language(date) if date else date
            time_text = self._format_time_for_language(start_time) if start_time else start_time

            if is_cancelled:
                cancelled_template = self._get_text("booking_already_cancelled")
                if not cancelled_template:
                    cancelled_template = "Du har allerede avlyst timen for {treatment} den {date} klokken {time}." if self._language_code() == "no" else "You have already cancelled the appointment for {treatment} on {date} at {time}."
                cancelled_message = cancelled_template.format(treatment=treatment, date=date_text or date, time=time_text or start_time)
                details = {
                    "BookingID": booking_id,
                    "treatment": treatment,
                    "date": date,
                    "time": start_time,
                    "StartTime": start_time,
                    "EndTime": end_time,
                    "ClinicID": str(timeslot.get("ClinicID") or booking.get("clinicId") or booking.get("ClinicID") or booking.get("clinic_id") or ""),
                    "TreatmentID": str(timeslot.get("TreatmentID") or booking.get("treatmentId") or booking.get("TreatmentID") or booking.get("treatment_id") or ""),
                    "ClinicianID": str(timeslot.get("ClinicianID") or booking.get("clinicianId") or booking.get("ClinicianID") or booking.get("clinician_id") or ""),
                    "FirstName": patient.get("FirstName") or booking.get("firstName") or booking.get("FirstName") or booking.get("first_name") or "",
                    "LastName": patient.get("LastName") or booking.get("lastName") or booking.get("LastName") or booking.get("last_name") or "",
                    "PhoneNumber": str(patient.get("MobilePhoneNumber") or booking.get("mobilePhoneNumber") or booking.get("PhoneNumber") or booking.get("phone_number") or ""),
                    "SSN": patient.get("PatientPersonalIdentification") or personnr,
                    "Status": status,
                }
                if self.call_data:
                    self.call_data.old_appointment_details = details

                return {
                    "suksess": True,
                    "data": booking,
                    "melding": cancelled_message,
                    "already_cancelled": True,
                    "booking_details": details,
                }

            success_template = self._get_text("client_detail_found")
            if not success_template:
                if self._language_code() == "en":
                    success_template = "Perfect! I found your booking ID {booking_id_spoken}. You have an appointment for {treatment} on {date} at {time}."
                else:
                    success_template = "Perfekt! Jeg fant bookingen din. Booking-ID er {booking_id}. Du har en time for {treatment} den {date} klokken {time}."

            success_message = success_template.format(
                booking_id=booking_id,
                booking_id_spoken=self._speak_booking_id(booking_id),
                treatment=treatment,
                date=date_text or date,
                time=time_text or start_time,
            )
            details = {
                "BookingID": booking_id,
                "treatment": treatment,
                "date": date,
                "time": start_time,
                "StartTime": start_time,
                "EndTime": end_time,
                "ClinicID": str(timeslot.get("ClinicID") or booking.get("clinicId") or booking.get("ClinicID") or booking.get("clinic_id") or ""),
                "TreatmentID": str(timeslot.get("TreatmentID") or booking.get("treatmentId") or booking.get("TreatmentID") or booking.get("treatment_id") or ""),
                "ClinicianID": str(timeslot.get("ClinicianID") or booking.get("clinicianId") or booking.get("ClinicianID") or booking.get("clinician_id") or ""),
                "FirstName": patient.get("FirstName") or booking.get("firstName") or booking.get("FirstName") or booking.get("first_name") or "",
                "LastName": patient.get("LastName") or booking.get("lastName") or booking.get("LastName") or booking.get("last_name") or "",
                "PhoneNumber": str(patient.get("MobilePhoneNumber") or booking.get("mobilePhoneNumber") or booking.get("PhoneNumber") or booking.get("phone_number") or ""),
                "SSN": patient.get("PatientPersonalIdentification") or personnr,
                "Status": status,
            }
            if self.call_data:
                self.call_data.old_appointment_details = details

            return {
                "suksess": True,
                "data": booking,
                "melding": success_message,
                "already_cancelled": False,
                "booking_details": details,
            }
            
        finally:
            if update_task:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass

    @function_tool()
    async def cancel_booking(
        self,
        context: RunContext,
        ssn: str = "",
        start_time: str = "",
        end_time: str = "",
        clinic_id: str = "",
        treatment_id: str = "",
        clinician_id: str = "",
        confirm: bool = False
    ):
        """
        Cancels a booking after customer confirmation.
        Uses OPUS cancellation endpoint (no n8n).

        Requires: ssn + bookingId (available from get_client_detail booking_details["BookingID"]).
        Legacy params (start/end/clinic/treatment/clinician) are still accepted for prompt compatibility.
        confirm should be True when customer confirms cancellation.
        """
        
        if not confirm:
            cancelled_text = self._get_text("cancel_booking_cancelled")
            if not cancelled_text:
                cancelled_text = "Avlysningen ble avbrutt. Bookingen din er fortsatt aktiv." if self._language_code() == "no" else "Cancellation was cancelled. Your booking is still active."
            return {
                "suksess": False,
                "melding": cancelled_text
            }
        
        booking_id = ""
        if self.call_data and self.call_data.old_appointment_details:
            booking_id = str(self.call_data.old_appointment_details.get("BookingID") or self.call_data.old_appointment_details.get("bookingId") or "")
        # also allow passing bookingId via treatment_id field is NOT allowed; must come from details

        if not booking_id:
            # try to derive from the most recent get_client_detail response stored on call_data if present
            if self.call_data and isinstance(getattr(self.call_data, "old_appointment_details", None), dict):
                booking_id = str(self.call_data.old_appointment_details.get("BookingID") or "")

        if not booking_id:
            error_text = "Booking ID is required to cancel." if self._language_code() == "en" else "Booking-ID er påkrevd for å avlyse."
            return {
                "suksess": False,
                "melding": error_text
            }
        
        update_task = None

        async def periodic_updates():
            """Gir brukeren oppdateringer"""
            if self._language_code() == "en":
                update_messages = [
                    "I'm cancelling your booking now...",
                    "Just a moment, processing your cancellation...",
                    "Thank you for waiting, almost done..."
                ]
            else:
                update_messages = [
                    "Jeg avlyser bookingen din nå...",
                    "Bare et øyeblikk, jeg behandler avlysningen...",
                    "Takk for tålmodigheten, nesten ferdig..."
                ]
            message_index = 0

            await asyncio.sleep(2.0)

            while True:
                try:
                    context.session.say(
                        update_messages[message_index],
                        allow_interruptions=False
                    )
                    await context.wait_for_playout()
                    message_index = (message_index + 1) % len(update_messages)
                    await asyncio.sleep(random.uniform(2.0, 3.5))
                except asyncio.CancelledError:
                    break
                except Exception:
                    break

        try:
            update_task = asyncio.create_task(periodic_updates())

            if not self.call_data or not self.call_data.business_id:
                return {
                    "suksess": False,
                    "melding": self._technical_error_message("message") or ("Missing business_id" if self._language_code() == "en" else "Mangler business_id"),
                }

            opus_result = await cancel_booking_opus(
                business_id=self.call_data.business_id,
                booking_id=booking_id,
                pid=ssn,
            )

            if opus_result.get("success"):
                success_text = self._get_text("cancel_booking_success")
                if not success_text:
                    success_text = "Bookingen din er nå avlyst. Er det noe annet jeg kan hjelpe deg med?" if self._language_code() == "no" else "Your booking has been cancelled. Is there anything else I can help you with?"
                return {"suksess": True, "data": opus_result, "melding": success_text}

            failure_text = self._get_text("cancel_booking_failure")
            if not failure_text:
                failure_text = "Beklager, jeg klarte ikke å avlyse bookingen. Prøv igjen senere eller kontakt oss direkte." if self._language_code() == "no" else "Sorry, I couldn't cancel the booking. Please try again later or contact us directly."
            return {"suksess": False, "melding": f"{failure_text} {opus_result.get('message','')}".strip()}
            
        finally:
            if update_task:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass

    @function_tool()
    async def change_appointment_date(
        self,
        context: RunContext
    ):
        """
        Handles appointment date change requests from customers.
        
        WORKFLOW:
        1. If personal number not collected, inform customer and call samle_personnummer_med_dtmf()
        2. Call get_client_detail() to fetch current appointment details
        3. Confirm the appointment details with the customer
        4. If confirmed, ask if they want next available or specific date
        5. The agent should then use sjekk_forste_ledige_time() or sjekk_onsket_time() based on preference
        
        IMPORTANT: 
        - This function will reuse collected_personnummer if already collected
        - Do NOT ask for personal number again if it's already been collected
        - After this function, the agent should proceed with finding new appointment slots
        """
        
        if not self.call_data or not self.call_data.collected_personnummer:
            intro_text = self._get_text("change_appointment_intro")
            if not intro_text:
                intro_text = "Jeg forstår at du vil endre time. For å finne din nåværende time, trenger jeg personnummeret ditt. Kan du vennligst taste inn personnummeret ditt på telefonen?" if self._language_code() == "no" else "I understand you want to change your appointment. To find your current appointment, I need your personal number. Can you please enter your personal number using your phone keypad?"
            
            context.session.say(
                intro_text,
                allow_interruptions=False
            )
            await context.wait_for_playout()
            
            await self.samle_personnummer_med_dtmf(context, purpose="booking")
            
            if not self.call_data.collected_personnummer:
                return {
                    "suksess": False,
                    "melding": self._get_text("personnummer_failed")
                }
        
        detail_result = await self.get_client_detail(context, self.call_data.collected_personnummer)
        
        if not detail_result.get("suksess", False):
            return detail_result
        
        if detail_result.get("already_cancelled", False):
            cancelled_msg = detail_result.get("melding", "")
            return {
                "suksess": False,
                "melding": cancelled_msg
            }
        
        booking_details = detail_result.get("booking_details", {})
        booking_data = detail_result.get("data", {})
        
        if not booking_details:
            not_found_text = self._get_text("change_appointment_no_booking")
            if not not_found_text:
                not_found_text = "Jeg fant ingen aktiv booking for dette personnummeret. Kan du bekrefte at personnummeret er korrekt?" if self._language_code() == "no" else "I couldn't find any active booking for this personal number. Can you confirm the personal number is correct?"
            return {
                "suksess": False,
                "melding": not_found_text
            }
        
        treatment_type = booking_details.get("treatment", booking_data.get("treatment_type", ""))
        if self.call_data and treatment_type:
            self.call_data.treatment_type_for_change = str(treatment_type)
        
        treatment = booking_details.get("treatment", booking_data.get("treatment_type", "behandling"))
        date = booking_details.get("date", booking_data.get("date", ""))
        time = booking_details.get("time", booking_data.get("start_time", ""))
        
        date_text = self._format_date_for_language(date) if date else date
        time_text = self._format_time_for_language(time) if time else time
        
        confirm_template = self._get_text("change_appointment_confirm_details")
        if not confirm_template:
            confirm_template = "Jeg fant bookingen din. Du har en time for {treatment} den {date} klokken {time}. Stemmer dette?" if self._language_code() == "no" else "I found your booking. You have an appointment for {treatment} on {date} at {time}. Is this correct?"
        
        confirm_message = confirm_template.format(
            treatment=treatment,
            date=date_text or date,
            time=time_text or time
        )
        
        if self.call_data:
            self.call_data.old_appointment_details = booking_details
        
        return {
            "suksess": True,
            "melding": confirm_message,
            "booking_details": booking_details,
            "data": booking_data,
            "next_step": "confirm_and_ask_preference",
            "is_appointment_change": True
        }

    @function_tool()
    async def update_appointment_date(
        self,
        context: RunContext,
        ssn: str = "",
        old_start_time: str = "",
        old_end_time: str = "",
        old_date: str = "",
        old_clinic_id: str = "",
        old_treatment_id: str = "",
        old_clinician_id: str = "",
        new_start_time: str = "",
        new_end_time: str = "",
        new_date: str = "",
        new_clinic_id: str = "",
        new_treatment_id: str = "",
        new_clinician_id: str = "",
        confirm: bool = False
    ):
        """
        Updates an existing appointment to a new date/time.
        This function should be called when customer wants to change their appointment date.
        
        Requires:
        - Old appointment details: ssn, old_start_time, old_end_time, old_date, old_clinic_id, old_treatment_id, old_clinician_id
        - New appointment details: new_start_time, new_end_time, new_date, new_clinic_id, new_treatment_id, new_clinician_id
        - new_date should be extracted from available_slots response (appointment_date field)
        - confirm should be True when customer confirms the new appointment time
        """
        
        if not confirm:
            cancelled_text = "Appointment update was cancelled. Your original appointment remains unchanged." if self._language_code() == "en" else "Oppdateringen ble avbrutt. Din opprinnelige time er uendret."
            return {
                "suksess": False,
                "melding": cancelled_text
            }
        
        if self.call_data and self.call_data.collected_personnummer:
            ssn = self.call_data.collected_personnummer
        
        if self.call_data and self.call_data.old_appointment_details:
            old_details = self.call_data.old_appointment_details
            if not old_start_time:
                old_start_time = old_details.get("StartTime", old_details.get("time", ""))
            if not old_end_time:
                old_end_time = old_details.get("EndTime", old_details.get("end_time", ""))
            if not old_date:
                old_date = old_details.get("date", "")
            if not old_clinic_id:
                old_clinic_id = old_details.get("ClinicID", old_details.get("clinic_id", ""))
            if not old_treatment_id:
                old_treatment_id = old_details.get("TreatmentID", old_details.get("treatment_id", ""))
            if not old_clinician_id:
                old_clinician_id = old_details.get("ClinicianID", old_details.get("clinician_id", ""))
        
        if not ssn or not old_start_time or not new_start_time:
            error_text = "Appointment details are required to update." if self._language_code() == "en" else "Bookingdetaljer er påkrevd for å oppdatere."
            return {
                "suksess": False,
                "melding": error_text
            }
        
        update_task = None

        async def periodic_updates():
            """Gir brukeren oppdateringer"""
            update_messages = self._get_text_list("update_appointment_updates")
            if not update_messages:
                if self._language_code() == "en":
                    update_messages = [
                        "Updating your booking now...",
                        "Just a moment, changing the appointment time...",
                        "Thank you for waiting..."
                    ]
                else:
                    update_messages = [
                        "Oppdaterer bookingen din nå...",
                        "Et øyeblikk, jeg endrer tidspunktet...",
                        "Takk for tålmodigheten..."
                    ]
            message_index = 0

            await asyncio.sleep(1.0)

            while True:
                try:
                    context.session.say(
                        update_messages[message_index],
                        allow_interruptions=False
                    )
                    await context.wait_for_playout()
                    message_index = (message_index + 1) % len(update_messages)
                    await asyncio.sleep(random.uniform(1.5, 2.5))
                except asyncio.CancelledError:
                    break
                except Exception:
                    break

        try:
            update_task = asyncio.create_task(periodic_updates())

            intro_text = self._get_text("update_appointment_intro")
            if not intro_text:
                intro_text = "La meg oppdatere timen din..." if self._language_code() == "no" else "Let me update your appointment..."
            context.session.say(
                intro_text,
                allow_interruptions=False
            )
            await context.wait_for_playout()
            
            webhook_url = UPDATE_APPOINTMENT_URL
            
            data = {
                "ssn": ssn,
                "old_start_time": old_start_time,
                "old_end_time": old_end_time,
                "old_date": old_date,
                "old_clinic_id": str(old_clinic_id),
                "old_treatment_id": str(old_treatment_id),
                "old_clinician_id": str(old_clinician_id),
                "new_start_time": new_start_time,
                "new_end_time": new_end_time,
                "new_date": new_date,
                "new_clinic_id": str(new_clinic_id),
                "new_treatment_id": str(new_treatment_id),
                "new_clinician_id": str(new_clinician_id)
            }
            data.update(self.booking_config)
            
            print(f"[WEBHOOK] PUT {webhook_url}")
            print(f"[WEBHOOK PAYLOAD] {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            webhook_response = await self._call_webhook_with_retry('PUT', webhook_url, data)
            
            if webhook_response is None:
                failure_text = self._get_text("update_appointment_failure")
                if not failure_text:
                    failure_text = "Beklager, jeg klarte ikke å oppdatere timen. Prøv igjen senere eller kontakt oss direkte." if self._language_code() == "no" else "Sorry, I couldn't update the appointment. Please try again later or contact us directly."
                return {
                    "suksess": False,
                    "melding": failure_text
                }
            
            response_status = webhook_response['status']
            response_text = webhook_response['text']
            result = webhook_response['json'] if webhook_response['json'] is not None else response_text
            
            print(f"[WEBHOOK RESPONSE] Status: {response_status}")
            print(f"[WEBHOOK RESPONSE] Body: {json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, dict) else response_text}")
            
            if response_status == 200:
                            if isinstance(result, dict) and result.get("suksess", False):
                                new_date = result.get("data", {}).get("new_date", "")
                                new_time = result.get("data", {}).get("new_start_time", new_start_time)
                                
                                date_text = self._format_date_for_language(new_date) if new_date else new_date
                                time_text = self._format_time_for_language(new_time) if new_time else new_time
                                
                                success_template = self._get_text("update_appointment_success")
                                if not success_template:
                                    success_template = "Perfekt! Timen din er nå oppdatert til {date} klokken {time}. Er det noe annet jeg kan hjelpe deg med?" if self._language_code() == "no" else "Perfect! Your appointment has been updated to {date} at {time}. Is there anything else I can help you with?"
                                
                                success_message = success_template.format(
                                    date=date_text or new_date,
                                    time=time_text or new_time
                                )
                                
                                return {
                                    "suksess": True,
                                    "data": result,
                                    "melding": success_message
                                }
                            else:
                                failure_text = self._get_text("update_appointment_failure")
                                if not failure_text:
                                    failure_text = "Beklager, jeg klarte ikke å oppdatere timen. Prøv igjen senere eller kontakt oss direkte." if self._language_code() == "no" else "Sorry, I couldn't update the appointment. Please try again later or contact us directly."
                                return {
                                    "suksess": False,
                                    "melding": failure_text
                                }
            else:
                failure_text = self._get_text("update_appointment_failure")
                if not failure_text:
                    failure_text = "Beklager, jeg klarte ikke å oppdatere timen. Prøv igjen senere eller kontakt oss direkte." if self._language_code() == "no" else "Sorry, I couldn't update the appointment. Please try again later or contact us directly."
                return {
                    "suksess": False,
                    "melding": f"{failure_text} {self._status_error_message(response_status)}"
                }
            
        finally:
            if update_task:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
