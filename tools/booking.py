import re
import json
import asyncio
import random
from datetime import datetime

from livekit.agents import function_tool, RunContext

import config.constants as cfg
from OPUS_routes import (
    find_patient_slot,
    book_existing_patient, book_new_patient,
)
from config.constants import BOOK_TIME_URL


class BookingToolsMixin:
    """Mixin containing all booking-related function tools."""

    @function_tool()
    async def get_available_treatments(self, ctx: RunContext) -> str:
        """
        Get list of available treatments/services at the clinic.
        Call this when user asks what treatments/services are provided or asks if a specific treatment is available.
        """
        if not self.clinic_treatments:
             lang = self._language_code()
             return "No treatment information available." if lang == "en" else "Ingen behandlingsinformasjon tilgjengelig."
        
        try:
            treatments_json = json.dumps(self.clinic_treatments, ensure_ascii=False, indent=2)
            print(f"[TOOL] get_available_treatments returning {len(treatments_json)} chars (Total treatments: {len(self.clinic_treatments)})")
            
            lang = self._language_code()
            prefix = "Available Treatments JSON:" if lang == "en" else "Tilgjengelige Behandlinger JSON:"
            return f"{prefix}\n{treatments_json}"
        except Exception as e:
            print(f"[TOOL] Error dumping treatments to JSON: {e}")
            return "Error retrieving treatments."
        

    @function_tool()
    async def select_timeslot(self, ctx: RunContext, slot_number: int) -> str:
        """
        Select a timeslot from the list presented to the customer.
        Call this when customer chooses a specific slot (e.g., "the first one", "7 AM slot", "slot 2").

        Args:
            slot_number: 1-based index of the slot (1 = first slot, 2 = second slot, etc.)
        """
        lang = self._language_code()
        if not self.call_data or not self.call_data.available_timeslots:
            return "No available timeslots to select from." if lang == "en" else "Ingen tilgjengelige timer å velge fra."

        slots = self.call_data.available_timeslots
        if slot_number < 1 or slot_number > len(slots):
            return f"Please choose a slot between 1 and {len(slots)}." if lang == "en" else f"Vennligst velg en time mellom 1 og {len(slots)}."

        chosen = slots[slot_number - 1]
        self.call_data.selected_timeslot = chosen

        start = chosen.get('slotStart') or chosen.get('Start') or chosen.get('start') or ''
        end = chosen.get('slotEnd') or chosen.get('End') or chosen.get('end') or ''
        try:
            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            dt = datetime.strptime(start[:19], "%Y-%m-%dT%H:%M:%S")

        time_str = dt.strftime("%H:%M")
        try:
            dt_end = datetime.fromisoformat(end.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            dt_end = datetime.strptime(end[:19], "%Y-%m-%dT%H:%M:%S")
        end_str = dt_end.strftime("%H:%M")

        clinician_name = ""
        if self.call_data.selected_clinician:
            clinician_name = self.call_data.selected_clinician.get("name", "")

        is_existing = chosen.get("isExistingPatient", False)
        patient_first = chosen.get("patientFirstName", "") or ""
        patient_last = chosen.get("patientLastName", "") or ""
        patient_name = f"{patient_first} {patient_last}".strip()

        if is_existing and patient_name:
            if lang == "en":
                msg = f"You selected the {time_str} to {end_str} slot"
                if clinician_name:
                    msg += f" with {clinician_name}"
                msg += f". I see you're already registered as {patient_name}. Shall I go ahead and book this for you?"
            else:
                msg = f"Du valgte timen fra klokken {time_str} til {end_str}"
                if clinician_name:
                    msg += f" hos {clinician_name}"
                msg += f". Jeg ser du allerede er registrert som {patient_name}. Skal jeg booke denne for deg?"
        else:
            if lang == "en":
                msg = f"You selected the {time_str} to {end_str} slot"
                if clinician_name:
                    msg += f" with {clinician_name}"
                msg += ". Can I have your full name please?"
            else:
                msg = f"Du valgte timen fra klokken {time_str} til {end_str}"
                if clinician_name:
                    msg += f" hos {clinician_name}"
                msg += ". Kan jeg få fulle navnet ditt?"
        return msg

    @function_tool()
    async def samle_email(self, ctx: RunContext, email: str) -> str:
        """Validate and store the customer's email address for booking.
        Call this when the customer provides their email. Validates format before storing.
        If the email is invalid, returns an error asking the customer to provide it again.

        Args:
            email: The email address provided by the customer (e.g. "tarun@gmail.com").
        
        Returns:
            Confirmation message if valid, or error message if invalid format.
        """
        lang = self._language_code()
        cleaned = email.strip().lower()

        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, cleaned):
            if lang == "en":
                return f"The email '{email}' doesn't seem to be valid. Could you please provide it again? It should be in the format name@example.com."
            return f"E-postadressen '{email}' ser ikke ut til å være gyldig. Kan du oppgi den på nytt? Formatet skal være navn@eksempel.com."

        if self.call_data:
            self.call_data.collected_email = cleaned

        if lang == "en":
            return f"I have your email as {cleaned}. Is that correct?"
        return f"Jeg har registrert e-postadressen din som {cleaned}. Stemmer det?"

    @function_tool()
    async def get_available_timeslots(self, ctx: RunContext, treatment_name: str, desired_date: str = "") -> str:
        """
        Find available timeslots for a treatment. IMPORTANT: Before calling this, you MUST first ask the customer
        whether they want the first available appointment or a specific date. Never call without asking preference.
        Returns multiple slots if available so the customer can choose.

        Args:
            treatment_name: The name of the treatment (e.g., "Recall hos tannlege", "undersøkelse")
            desired_date: Specific date in YYYY-MM-DD format (e.g., "2026-07-20"). If empty, finds first available from now.
        """
        lang = self._language_code()
        
        if not self.clinic_treatments:
            return "No treatments available. Please try again later." if lang == "en" else "Ingen behandlinger tilgjengelig. Vennligst prøv igjen senere."
        
        treatment_name_lower = treatment_name.lower()
        matched_treatment = None
        
        for treatment in self.clinic_treatments:
            t_name = treatment.get('Name') or treatment.get('name') or ''
            t_desc = treatment.get('Description') or treatment.get('description') or ''
            
            if treatment_name_lower in t_name.lower() or treatment_name_lower in t_desc.lower():
                matched_treatment = treatment
                break
        
        if not matched_treatment:
            translations = {
                'examination': ['undersøkelse', 'examination', 'check-up', 'checkup'],
                'cleaning': ['rens', 'cleaning', 'tannrens'],
                'whitening': ['bleking', 'whitening', 'tannbleking'],
                'emergency': ['akutt', 'emergency', 'acute'],
                'introduction': ['introduksjon', 'introduction', 'ny pasient', 'new patient', 'førstegang'],
            }
            
            for key, variants in translations.items():
                if any(v in treatment_name_lower for v in variants):
                    for treatment in self.clinic_treatments:
                        t_name = (treatment.get('Name') or treatment.get('name') or '').lower()
                        t_desc = (treatment.get('Description') or treatment.get('description') or '').lower()
                        if any(v in t_name or v in t_desc for v in variants):
                            matched_treatment = treatment
                            break
                    break
        
        if not matched_treatment:
            if lang == "en":
                return f"I couldn't find a treatment matching '{treatment_name}'. Please ask about our available treatments first."
            return f"Jeg fant ingen behandling som matcher '{treatment_name}'. Vennligst spør om våre tilgjengelige behandlinger først."
        
        treatment_id = matched_treatment.get('ID') or matched_treatment.get('id')
        treatment_display_name = matched_treatment.get('Name') or matched_treatment.get('name')
        
        if not treatment_id:
            return "Could not identify the treatment. Please try again." if lang == "en" else "Kunne ikke identifisere behandlingen. Vennligst prøv igjen."
        
        if self.call_data:
            self.call_data.selected_treatment_id = treatment_id
        
        business_id = self.call_data.business_id if self.call_data else None
        
        if not business_id:
            print("[TOOL] get_available_timeslots: No business_id in call_data")
            return "Unable to check availability at the moment." if lang == "en" else "Kan ikke sjekke tilgjengelighet for øyeblikket."
        
        pid = self.call_data.collected_personnummer if self.call_data else ""
        if not pid:
            print("[TOOL] get_available_timeslots: No personnummer collected yet")
            if lang == "en":
                return "I need your personal ID number before I can check availability. Please provide it first."
            return "Jeg trenger personnummeret ditt før jeg kan sjekke tilgjengelighet. Vennligst oppgi det først."

        print(f"[TOOL] get_available_timeslots: Finding slot for treatment='{treatment_display_name}', business_id={business_id}")

        starting_from = None
        if desired_date and desired_date.strip():
            try:
                parsed = datetime.strptime(desired_date.strip()[:10], "%Y-%m-%d")
                starting_from = parsed.strftime("%Y-%m-%dT07:00:00")
            except ValueError:
                print(f"[TOOL] get_available_timeslots: invalid desired_date '{desired_date}', using current time")

        try:
            slots = await find_patient_slot(business_id, pid, treatment_display_name, starting_from)
            found_slots = [s for s in slots if s.get("found")]

            if not found_slots:
                not_found_reason = next((s.get("reason") for s in slots if not s.get("found") and s.get("reason")), None)
                print(f"[TOOL] get_available_timeslots: no slots found. Reason: {not_found_reason}")
                if lang == "en":
                    return f"Sorry, the dentist has no available appointments for {treatment_display_name} right now. Would you like to check another date?"
                return f"Beklager, tannlegen har ingen ledige timer for {treatment_display_name} akkurat nå. Vil du prøve en annen dato?"

            first_slot = found_slots[0]
            clinician_name = first_slot.get("clinicianName", "")
            clinician_title = "Tannlege"

            if self.call_data:
                if first_slot.get("treatmentId"):
                    self.call_data.selected_treatment_id = first_slot["treatmentId"]
                if first_slot.get("patientFirstName"):
                    self.call_data.customer_first_name = first_slot["patientFirstName"]
                if first_slot.get("patientLastName"):
                    self.call_data.customer_last_name = first_slot["patientLastName"]
                self.call_data.selected_clinician = {
                    "id": first_slot.get("clinicianId"),
                    "name": clinician_name,
                    "title": clinician_title,
                }

            max_slots = min(len(found_slots), 5)
            display_slots = found_slots[:max_slots]

            if self.call_data:
                self.call_data.available_timeslots = display_slots
                self.call_data.selected_timeslot = display_slots[0] if len(display_slots) == 1 else None

            def _format_slot(s):
                st = s.get('slotStart') or s.get('start') or s.get('Start') or ''
                en = s.get('slotEnd') or s.get('end') or s.get('End') or ''
                try:
                    d = datetime.fromisoformat(st.replace('Z', '+00:00'))
                except Exception:
                    d = datetime.strptime(st[:19], "%Y-%m-%dT%H:%M:%S")
                try:
                    d2 = datetime.fromisoformat(en.replace('Z', '+00:00'))
                except Exception:
                    d2 = datetime.strptime(en[:19], "%Y-%m-%dT%H:%M:%S")
                return d, d2

            if len(display_slots) == 1:
                dt, dt_end = _format_slot(display_slots[0])
                title_en = "Dentist" if "tannlege" in clinician_title.lower() else clinician_title
                if lang == "en":
                    return (f"I found an appointment for {treatment_display_name} on {dt.strftime('%A, %B %d')} "
                            f"from {dt.strftime('%H:%M')} to {dt_end.strftime('%H:%M')} "
                            f"with {clinician_name} ({title_en}). Should I book that for you?")
                else:
                    day_names_no = ['mandag','tirsdag','onsdag','torsdag','fredag','lørdag','søndag']
                    month_names_no = ['januar','februar','mars','april','mai','juni','juli','august','september','oktober','november','desember']
                    return (f"Jeg fant en ledig time for {treatment_display_name} på {day_names_no[dt.weekday()]} "
                            f"{dt.day}. {month_names_no[dt.month-1]} fra klokken {dt.strftime('%H:%M')} til {dt_end.strftime('%H:%M')} "
                            f"hos {clinician_name} ({clinician_title}). Skal jeg booke den for deg?")

            slot_lines = []
            for i, s in enumerate(display_slots, 1):
                dt, dt_end = _format_slot(s)
                if lang == "en":
                    slot_lines.append(f"{i}. {dt.strftime('%A, %B %d')} from {dt.strftime('%H:%M')} to {dt_end.strftime('%H:%M')}")
                else:
                    day_names_no = ['mandag','tirsdag','onsdag','torsdag','fredag','lørdag','søndag']
                    month_names_no = ['januar','februar','mars','april','mai','juni','juli','august','september','oktober','november','desember']
                    slot_lines.append(f"{i}. {day_names_no[dt.weekday()]} {dt.day}. {month_names_no[dt.month-1]} fra klokken {dt.strftime('%H:%M')} til {dt_end.strftime('%H:%M')}")

            title_en = "Dentist" if "tannlege" in clinician_title.lower() else clinician_title
            if lang == "en":
                header = f"I found {len(display_slots)} available time slots for {treatment_display_name} with {clinician_name} ({title_en}):"
                footer = "Which one would you like to book?"
            else:
                header = f"Jeg fant {len(display_slots)} ledige timer for {treatment_display_name} hos {clinician_name} ({clinician_title}):"
                footer = "Hvilken ønsker du å booke?"

            return f"{header}\n" + "\n".join(slot_lines) + f"\n{footer}"

        except Exception as e:
            print(f"[TOOL] get_available_timeslots error: {e}")
            return "A technical error occurred while checking availability." if lang == "en" else "En teknisk feil oppstod ved sjekking av tilgjengelighet."

    @function_tool()
    async def sett_booking_preference(
        self,
        context: RunContext,
        preference: str
    ) -> str:
        """Store the customer's booking preference before searching for timeslots.
        
        Args:
            preference: One of "first_available" (earliest slot), "specific_date" (customer has a date in mind), or "unknown".
        
        Returns:
            Confirmation message in the active language.
        """
        if not self.call_data:
            return "Ingen aktive samtaledata tilgjengelig."

        normalized = preference.strip().lower()
        if normalized in {"first", "first_available", "earliest", "earliest_available"}:
            self.call_data.booking_preference = "first_available"
            return self._get_text("booking_preference_set_first")
        if normalized in {"specific", "specific_date", "date", "dato", "desired_date"}:
            self.call_data.booking_preference = "specific_date"
            return self._get_text("booking_preference_set_date")
        if normalized in {"unknown", "unsure", "not_sure", "later"}:
            self.call_data.booking_preference = None
            return self._get_text("booking_preference_set_unknown")

        return self._get_text("booking_preference_invalid")

    @function_tool()
    async def sjekk_forste_ledige_time(
        self, context: RunContext, 
        personnr: str = "", 
        kundeMelding: str = ""
        ):
        """Find the first available appointment slot for the patient.
        Call ONLY after sett_booking_preference("first_available") and samle_personnummer_med_dtmf().

        Args:
            personnr: Patient's personal ID number (optional, auto-collected via DTMF if missing).
            kundeMelding: Description of what the patient needs (e.g. "Recall with Dentist").
        
        Returns:
            dict with 'suksess' (bool) and 'melding' (str) containing available slots or error message.
        """
        
        if self.call_data and self.call_data.booking_preference != "first_available":
            return {
                "suksess": False,
                "melding": self._get_text("booking_preference_missing_first")
            }

        if self.call_data and self.call_data.collected_personnummer:
            _ = self.call_data.collected_personnummer
        elif self.call_data:
            await self.samle_personnummer_med_dtmf(context)
            if not self.call_data.collected_personnummer:
                return {
                    "suksess": False,
                    "melding": self._get_text("personnummer_failed")
                }
            _ = self.call_data.collected_personnummer

        if self.call_data and not self.call_data.selected_treatment_id and self.clinic_treatments and kundeMelding:
            msg_lower = kundeMelding.lower()
            for t in self.clinic_treatments:
                t_name = (t.get("Name") or t.get("name") or "").lower()
                t_desc = (t.get("Description") or t.get("description") or "").lower()
                if "recall" in msg_lower and ("recall" in t_name or "recall" in t_desc):
                    tid = t.get("ID") or t.get("id")
                    if tid:
                        self.call_data.selected_treatment_id = tid
                        print(f"[OPUS FLOW] sjekk_forste_ledige_time: resolved treatment_id={tid} from kundeMelding (recall)")
                        break
                if "routine" in msg_lower or "check" in msg_lower or "check-up" in msg_lower:
                    if "recall" in t_name or "kontroll" in t_name or "undersøkelse" in t_name:
                        tid = t.get("ID") or t.get("id")
                        if tid:
                            self.call_data.selected_treatment_id = tid
                            print(f"[OPUS FLOW] sjekk_forste_ledige_time: resolved treatment_id={tid} from kundeMelding (routine/check)")
                            break
        
        update_task = None

        async def periodic_updates():
            """Gir brukeren oppdateringer hvert 2.-3,5. sekund"""
            update_messages = self._get_text_list("first_slot_updates")
            if not update_messages:
                update_messages = [
                    "Et lite øyeblikk, jeg søker etter første ledige time...",
                    "Vi søker fortsatt...",
                    "Takk for din tålmodighet...",
                    "Jeg sjekker flere alternativer for deg...",
                    "Bare et øyeblikk til...",
                    "Fortsetter å lete etter beste tidspunkt...",
                    "Snart ferdig med søket...",
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
                    await asyncio.sleep(random.uniform(2.0, 3.5))
                except asyncio.CancelledError:
                    break
                except Exception:
                    break

        try:
            update_task = asyncio.create_task(periodic_updates())

            context.session.say(
                self._get_text("first_slot_intro") or "Absolutt, la meg finne den første ledige timen vi har tilgjengelig for deg...",
                allow_interruptions=False
            )
            await context.wait_for_playout()

            result = await self._opus_find_timeslot(starting_from=None)
            return result

        finally:
            if update_task:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass

    @function_tool()
    async def sjekk_onsket_time(
        self, context: RunContext, 
        personnr: str = "", 
        kundeMelding: str = "",
        OnsketDato: str = ""
        ):
        """Check available appointment slots on a specific requested date.
        Call ONLY after sett_booking_preference("specific_date") and samle_personnummer_med_dtmf().

        Args:
            personnr: Patient's personal ID number (optional, auto-collected via DTMF if missing).
            kundeMelding: Description of what the patient needs (e.g. "Routine checkup on 20 July").
            OnsketDato: Requested date in YYYY-MM-DD format (e.g. "2026-07-20").
        
        Returns:
            dict with 'suksess' (bool) and 'melding' (str) containing available slots or error message.
        """
        
        if self.call_data and self.call_data.booking_preference != "specific_date":
            return {
                "suksess": False,
                "melding": self._get_text("booking_preference_missing_date")
            }

        if self.call_data and self.call_data.collected_personnummer:
            _ = self.call_data.collected_personnummer
        elif self.call_data:
            await self.samle_personnummer_med_dtmf(context)
            if not self.call_data.collected_personnummer:
                return {
                    "suksess": False,
                    "melding": self._get_text("personnummer_failed")
                }
            _ = self.call_data.collected_personnummer
        
        update_task = None

        async def periodic_updates():
            update_messages = self._get_text_list("desired_slot_updates")
            if not update_messages:
                update_messages = [
                    "Et øyeblikk, jeg søker etter ledig time for deg...",
                    "Vi søker fortsatt...",
                    "Takk for at du venter...",
                    "Ser etter ledige tidspunkter...",
                    "Bare litt til, snart ferdig...",
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
                    await asyncio.sleep(random.uniform(2.0, 3.5))
                except asyncio.CancelledError:
                    break
                except Exception:
                    break

        try:
            update_task = asyncio.create_task(periodic_updates())

            context.session.say(
                self._get_text("desired_slot_intro") or "Absolutt, la meg sjekke tilgjengeligheten vår...",
                allow_interruptions=False
            )
            await context.wait_for_playout()

            starting_from = None
            if OnsketDato and OnsketDato.strip():
                try:
                    parsed = datetime.strptime(OnsketDato.strip()[:10], "%Y-%m-%d")
                    starting_from = parsed.strftime("%Y-%m-%dT07:00:00")
                except ValueError:
                    print(f"[TOOL] sjekk_onsket_time: invalid OnsketDato '{OnsketDato}', using current time")

            result = await self._opus_find_timeslot(starting_from=starting_from)
            return result

        finally:
            if update_task:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass

    @function_tool()
    async def book_time(
        self, context: RunContext, 
        personnr: str = "",
        Fornavn: str = "", 
        Etternavn: str = "",
        mobilnr: str = "",
        ClinicIDForValgtTime: str = "",
        TreatmentIDForValgtTime: str = "",
        ClinicianIDForValgtTime: str = "",        
        StartTid: str = "",
        SluttTid: str = "",
        Dato: str = "",
        ):
        """Book an appointment for the patient.

        For EXISTING patients (isExistingPatient=true from find-slot):
          Only personnummer is needed. Name is auto-filled from the system.
          Call this directly after the patient confirms the slot.

        For NEW patients (isExistingPatient=false):
          You MUST collect all of these BEFORE calling:
          1. Personnummer via samle_personnummer_med_dtmf()
          2. Full name (Fornavn + Etternavn)
          3. Email via samle_email()
          4. Phone number (mobilnr)
        """
        
        if self.call_data and self.call_data.collected_personnummer:
            personnr = self.call_data.collected_personnummer
        elif self.call_data:
            await self.samle_personnummer_med_dtmf(context)
            if not self.call_data.collected_personnummer:
                return {
                    "suksess": False,
                    "melding": self._get_text("personnummer_failed")
                }
            personnr = self.call_data.collected_personnummer
        
        mobilnr = self.get_phone_number_for_booking()
        
        update_task = None

        async def periodic_updates():
            """Gir brukeren oppdateringer hvert 2.-3,5. sekund"""
            update_messages = self._get_text_list("booking_updates")
            if not update_messages:
                update_messages = [
                    "Bare et øyeblikk, jeg registrerer timen din...",
                    "Jobber med bookingen...",
                    "Takk for tålmodigheten...",
                    "Snart ferdig med registreringen...",
                    "Fullfører bookingen nå...",
                    "Siste detaljer...",
                    "Nesten klar...",
                ]
            message_index = 0

            await asyncio.sleep(3.0)

            while True:
                try:
                    await context.session.say(
                        update_messages[message_index],
                        allow_interruptions=False
                    )
                    message_index = (message_index + 1) % len(update_messages)
                    await asyncio.sleep(random.uniform(2.0, 3.5))
                except asyncio.CancelledError:
                    break
                except Exception:
                    break

        try:
            update_task = asyncio.create_task(periodic_updates())

            context.session.say(
                 self._get_text("booking_intro") or "Flott, la meg booke den timen for deg med en gang...",
                allow_interruptions=False
            )
            await context.wait_for_playout()
            
            use_opus = (
                self.call_data
                and self.call_data.selected_timeslot
                and self.call_data.business_id
                and cfg.OPUS_BEARER_TOKEN
            )
            
            if use_opus:
                slot = self.call_data.selected_timeslot
                clinician_id_val = slot.get('clinicianId') or slot.get('ClinicianID') or slot.get('clinician_id') or ClinicianIDForValgtTime
                treatment_id_val = slot.get('treatmentId') or slot.get('TreatmentID') or slot.get('treatment_id') or TreatmentIDForValgtTime
                slot_start = slot.get('slotStart') or slot.get('Start') or slot.get('start') or StartTid
                slot_end = slot.get('slotEnd') or slot.get('End') or slot.get('end') or SluttTid

                is_existing = slot.get('isExistingPatient', False)
                patient_first = slot.get('patientFirstName', '') or Fornavn
                patient_last = slot.get('patientLastName', '') or Etternavn
                display_name = patient_first or Fornavn

                opus_result = None

                if is_existing:
                    print("[OPUS FLOW] Existing patient detected — trying existing-patient/book")
                    opus_result = await book_existing_patient(
                        business_id=self.call_data.business_id,
                        pid=personnr,
                        treatment_id=int(treatment_id_val),
                        clinician_id=int(clinician_id_val),
                        slot_start=slot_start,
                        slot_end=slot_end,
                    )

                if not opus_result or not opus_result.get("success"):
                    if is_existing:
                        print("[OPUS FLOW] existing-patient/book failed — falling back to new-patient/book")
                    opus_result = await book_new_patient(
                        business_id=self.call_data.business_id,
                        pid=personnr,
                        first_name=patient_first or Fornavn,
                        last_name=patient_last or Etternavn,
                        phone=mobilnr,
                        email=self.call_data.collected_email if self.call_data else "",
                        treatment_id=int(treatment_id_val),
                        clinician_id=int(clinician_id_val),
                        slot_start=slot_start,
                        slot_end=slot_end,
                    )

                if opus_result.get("success"):
                    if self.call_data:
                        self.call_data.appointment_booked = True

                    clinician_info = self.call_data.selected_clinician if self.call_data else None
                    if clinician_info and clinician_info.get("name"):
                        c_name = clinician_info["name"]
                        c_title = clinician_info.get("title", "Tannlege")
                        if self._language_code() == "en":
                            title_en = "Dentist" if "tannlege" in c_title.lower() else c_title
                            success_message = f"Your appointment is booked, {display_name}. Your dentist is {c_name} ({title_en})."
                        else:
                            success_message = f"Timen din er booket, {display_name}. Din tannlege er {c_name} ({c_title})."
                    else:
                        success_template = self._get_text("booking_success") or "Time er nå booket for {name}."
                        success_message = success_template.format(name=display_name)

                    return {
                        "suksess": True,
                        "data": opus_result,
                        "melding": success_message
                    }
                else:
                    failure_prefix = self._get_text("booking_failure") or "Klarte ikke å booke timen i systemet."
                    return {
                        "suksess": False,
                        "melding": f"{failure_prefix} {opus_result.get('message', '')}"
                    }
            
            # Fallback: n8n webhook
            webhook_url = BOOK_TIME_URL
            
            data = {
                "personnr": personnr,
                "Fornavn": Fornavn,
                "Etternavn": Etternavn,
                "mobilnr": mobilnr,
                "ClinicIDForValgtTime": ClinicIDForValgtTime,
                "TreatmentIDForValgtTime": TreatmentIDForValgtTime,
                "ClinicianIDForValgtTime": ClinicianIDForValgtTime,
                "StartTid": StartTid,
                "SluttTid": SluttTid
            }
            
            if Dato:
                data["Dato"] = Dato
            
            data.update(self.booking_config)
            
            print(f"[WEBHOOK] POST {webhook_url}")
            print(f"[WEBHOOK PAYLOAD] {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            webhook_response = await self._call_webhook_with_retry('POST', webhook_url, data)
            
            if webhook_response is None:
                return {
                    "suksess": False,
                    "melding": self._technical_error_message("booking")
                }
            
            response_status = webhook_response['status']
            response_text = webhook_response['text']
            result = webhook_response['json'] if webhook_response['json'] is not None else response_text
            
            print(f"[WEBHOOK RESPONSE] Status: {response_status}")
            print(f"[WEBHOOK RESPONSE] Body: {json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, dict) else response_text}")
            
            if response_status == 200:
                if self.call_data:
                    self.call_data.appointment_booked = True
                success_template = self._get_text("booking_success") or "Time er nå booket for {name}."
                success_message = success_template.format(name=Fornavn)
                return {
                    "suksess": True,
                    "data": result,
                    "melding": success_message
                }
            else:
                failure_prefix = self._get_text("booking_failure") or "Klarte ikke å booke timen i systemet."
                return {
                    "suksess": False,
                    "melding": f"{failure_prefix} {self._status_error_message(response_status)}"
                }
            
        finally:
            if update_task:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass
