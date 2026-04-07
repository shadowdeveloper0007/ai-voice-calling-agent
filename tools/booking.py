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
        Return the full treatment menu (numbered, with durations).
        Call ONLY when the user explicitly asks what treatments you offer, or matching failed after a clarifying question.
        Do NOT call when the user already named a treatment mappable from the CLINIC TREATMENT CATALOG in system instructions — use get_available_timeslots with the exact Name instead.
        """
        if not self.clinic_treatments:
             lang = self._language_code()
             return "No treatment information available." if lang == "en" else "Ingen behandlingsinformasjon tilgjengelig."
        
        try:
            lang = self._language_code()
            if lang == "en":
                # English-friendly, numbered list with durations.
                # Keep the exact Norwegian name in parentheses for precise selection/matching.
                def _to_en(name_no: str, desc_no: str) -> str:
                    # Dynamic "good enough" translation via keyword/phrase mapping.
                    # (We keep the exact Norwegian name separately for selection.)
                    raw = (name_no or "").strip()
                    if not raw:
                        raw = (desc_no or "").strip()
                    if not raw:
                        return "Treatment"

                    # Remove leading list numbers like "1. " or "9. "
                    raw = re.sub(r"^\s*\d+\.\s*", "", raw)

                    s = raw.lower()
                    d = (desc_no or "").lower()

                    # If it already looks English, keep it.
                    if any(tok in s for tok in ("consultation", "invisalign", "recall", "checkup", "emergency", "whitening", "cleaning")):
                        return raw

                    # Prefer strong signals from description if name is vague.
                    signals = s + " " + d

                    phrase_map = [
                        ("recall hos tannlege", "Routine dentist checkup (recall)"),
                        ("kontroll (recall)", "Checkup (recall)"),
                        ("akutt tannbehandling", "Emergency dental treatment"),
                        ("konsultasjon ny pasient", "New patient consultation"),
                        ("time hos tannlege", "Dentist appointment (specific problem)"),
                        ("smiledesign / invisalign", "Smiledesign / Invisalign consultation"),
                        ("bleking av tenner", "Teeth whitening"),
                    ]
                    for no_phrase, en_phrase in phrase_map:
                        if no_phrase in signals:
                            return en_phrase

                    # Word-level mapping (order matters; longer first).
                    word_map = [
                        ("tannpleier", "dental hygienist"),
                        ("tannlege", "dentist"),
                        ("konsultasjon", "consultation"),
                        ("kontroll", "checkup"),
                        ("undersøkelse", "examination"),
                        ("rutineundersøkelse", "routine examination"),
                        ("akutt", "emergency"),
                        ("rens", "cleaning"),
                        ("bleking", "whitening"),
                        ("tenner", "teeth"),
                        ("implantatbro", "implant bridge"),
                        ("implantat", "implant"),
                        ("periodontitt", "periodontitis"),
                        ("perio", "periodontal"),
                        ("behandling", "treatment"),
                        ("smiledesign", "smiledesign"),
                        ("hos", "with"),
                        ("ny pasient", "new patient"),
                        ("budapest", "budapest"),
                    ]

                    out = s
                    for no_word, en_word in word_map:
                        out = out.replace(no_word, en_word)

                    # Cleanup spacing/punctuation, then title-case lightly.
                    out = re.sub(r"\s+", " ", out).strip(" -–—")
                    if not out:
                        return raw
                    return out[:1].upper() + out[1:]

                lines = []
                for i, t in enumerate(self.clinic_treatments, 1):
                    name_no = (t.get("Name") or t.get("name") or "").strip()
                    desc_no = (t.get("Description") or t.get("description") or "").strip()
                    duration = t.get("Duration")
                    duration_str = f"{duration} min" if isinstance(duration, int) else "duration unknown"
                    name_en = _to_en(name_no, desc_no)
                    lines.append(f"{i}. {name_en} ({duration_str}) — {name_no}")

                result = "Available treatments:\n" + "\n".join(lines)
                print(f"[TOOL] get_available_treatments returning {len(result)} chars (Total treatments: {len(self.clinic_treatments)})")
                return result

            lines_no = []
            for i, t in enumerate(self.clinic_treatments, 1):
                name = (t.get("Name") or t.get("name") or "").strip()
                if not name:
                    continue
                dur = t.get("Duration")
                dur_s = f"{int(dur)} min" if isinstance(dur, (int, float)) else ""
                lines_no.append(f"{i}. {name} — {dur_s}" if dur_s else f"{i}. {name}")
            result_no = "Tilgjengelige behandlinger:\n" + "\n".join(lines_no)
            print(f"[TOOL] get_available_treatments returning {len(result_no)} chars (Total treatments: {len(self.clinic_treatments)})")
            return result_no
        except Exception as e:
            print(f"[TOOL] Error listing treatments: {e}")
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
            return {
                "patient_type": "existing_patient",
                "isExistingPatient": True,
                "message": msg,
            }
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
            return {
                "patient_type": "new_patient",
                "isExistingPatient": False,
                "message": msg,
            }

    @function_tool()
    async def samle_email(self, ctx: RunContext, email: str) -> str:
        """Validate and store the customer's email address for booking.
        ONLY call this when the customer has explicitly stated their email address out loud.
        NEVER guess, infer, or construct an email from the customer's name or any other information.
        If the customer has not yet provided an email, ask them for it first and wait for their response.

        Args:
            email: The exact email address spoken by the customer. Must be explicitly provided by the customer.
        
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
    async def samle_navn(self, ctx: RunContext, fornavn: str, etternavn: str) -> str:
        """Capture and confirm the customer's full name for a new patient booking.
        ONLY call this when the customer has explicitly stated their first and last name.
        NEVER guess or infer a name. After calling, you MUST wait for the user to confirm
        yes or no before proceeding.

        Args:
            fornavn: The first name as spoken by the customer.
            etternavn: The last name as spoken by the customer.

        Returns:
            Confirmation message asking the user to verify the name.
        """
        lang = self._language_code()
        fornavn = fornavn.strip().title()
        etternavn = etternavn.strip().title()

        if self.call_data:
            self.call_data.customer_first_name = fornavn
            self.call_data.customer_last_name = etternavn

        if lang == "en":
            return f"I have your name as {fornavn} {etternavn}. Is that correct?"
        return f"Jeg har registrert navnet ditt som {fornavn} {etternavn}. Stemmer det?"

    @function_tool()
    async def get_available_timeslots(self, ctx: RunContext, treatment_name: str, desired_date: str = "") -> str:
        """
        Find available timeslots for a treatment.
        PREREQUISITES (all must be met before calling):
          1. A specific treatment must be identified — NEVER call with a guessed treatment. Ask the customer first.
          2. The customer must have stated their preference (first available vs specific date).
          3. Personnummer must be collected via samle_personnummer_med_dtmf().
        Use the EXACT treatment Name from the CLINIC TREATMENT CATALOG when possible.

        Args:
            treatment_name: Exact catalog Name or close phrase (e.g., "Recall hos tannlege", "undersøkelse"). Must not be empty or guessed.
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
                'dentist': ['tannlege', 'dentist', 'dentist appointment', 'dental appointment', 'dental'],
                'hygienist': ['tannpleier', 'hygienist', 'dental hygienist'],
                'periodontal': ['periodontal', 'periodontal-treatment', 'parodontitt'],
                'implant': ['implant', 'implantat', 'implantbro'],
                'recall': ['recall', 'kontroll'],
            }
            
            for key, variants in translations.items():
                if any(v in treatment_name_lower for v in variants):
                    matches = []
                    for treatment in self.clinic_treatments:
                        t_name = (treatment.get('Name') or treatment.get('name') or '').lower()
                        t_desc = (treatment.get('Description') or treatment.get('description') or '').lower()
                        if any(v in t_name or v in t_desc for v in variants):
                            matches.append(treatment)

                    if key == "dentist" and matches:
                        # "dentist appointment" is ambiguous. If the caller didn't say recall/checkup,
                        # prefer "Time hos tannlege" (specific problem). If they said recall/checkup,
                        # prefer recall/control treatments.
                        wants_recall = any(
                            k in treatment_name_lower
                            for k in ("recall", "checkup", "check-up", "routine", "kontroll", "undersøk", "undersok")
                        )
                        if wants_recall:
                            for t in matches:
                                n = (t.get("Name") or t.get("name") or "").lower()
                                d = (t.get("Description") or t.get("description") or "").lower()
                                if "recall" in n or "kontroll" in n or "undersøk" in n or ("recall" in d and "tannlege" in d):
                                    matched_treatment = t
                                    break
                        else:
                            for t in matches:
                                n = (t.get("Name") or t.get("name") or "").lower()
                                d = (t.get("Description") or t.get("description") or "").lower()
                                if "time hos tannlege" in n or "spesifikt problem" in d:
                                    matched_treatment = t
                                    break

                        if not matched_treatment:
                            matched_treatment = matches[0]
                    elif matches:
                        matched_treatment = matches[0]
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
                            f"with {clinician_name} ({title_en}). Would you like to select this slot?")
                else:
                    day_names_no = ['mandag','tirsdag','onsdag','torsdag','fredag','lørdag','søndag']
                    month_names_no = ['januar','februar','mars','april','mai','juni','juli','august','september','oktober','november','desember']
                    return (f"Jeg fant en ledig time for {treatment_display_name} på {day_names_no[dt.weekday()]} "
                            f"{dt.day}. {month_names_no[dt.month-1]} fra klokken {dt.strftime('%H:%M')} til {dt_end.strftime('%H:%M')} "
                            f"hos {clinician_name} ({clinician_title}). Ønsker du å velge denne timen?")

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
            await self.samle_personnummer_med_dtmf(context, purpose="booking")
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
            await self.samle_personnummer_med_dtmf(context, purpose="booking")
            if not self.call_data.collected_personnummer:
                return {
                    "suksess": False,
                    "melding": self._get_text("personnummer_failed")
                }
            _ = self.call_data.collected_personnummer

        # Resolve treatment from free-text message when missing.
        # (Without selected_treatment_id, OPUS flow cannot derive treatment_name and will abort.)
        if self.call_data and not self.call_data.selected_treatment_id and self.clinic_treatments and kundeMelding:
            msg_lower = kundeMelding.lower()

            def _pick_treatment(predicate):
                for t in self.clinic_treatments:
                    t_name = (t.get("Name") or t.get("name") or "")
                    t_desc = (t.get("Description") or t.get("description") or "")
                    if predicate(t_name.lower(), t_desc.lower()):
                        tid = t.get("ID") or t.get("id")
                        if tid:
                            self.call_data.selected_treatment_id = tid
                            print(f"[OPUS FLOW] sjekk_onsket_time: resolved treatment_id={tid} from kundeMelding")
                            return True
                return False

            # Emergency / acute
            if any(k in msg_lower for k in ("emergency", "acute", "pain", "toothache", "akutt", "smerte")):
                _pick_treatment(lambda n, d: "akutt" in n or "akutt" in d or "emergency" in n or "emergency" in d)

            # New patient / consultation
            if not self.call_data.selected_treatment_id and any(k in msg_lower for k in ("new patient", "new", "første", "førstegang", "konsultasjon", "consultation")):
                _pick_treatment(lambda n, d: "ny pasient" in n or "konsultasjon" in n or "consult" in n or "new patient" in d)

            # Whitening
            if not self.call_data.selected_treatment_id and any(k in msg_lower for k in ("whitening", "bleking")):
                _pick_treatment(lambda n, d: "bleking" in n or "whitening" in n or "blek" in d)

            # Cleaning / perio
            if not self.call_data.selected_treatment_id and any(k in msg_lower for k in ("cleaning", "rens", "perio", "periodont", "tannrens")):
                _pick_treatment(lambda n, d: "rens" in n or "perio" in n or "periodont" in d or "tannrens" in d)

            # Dentist appointment is ambiguous:
            # - If recall/checkup/routine words exist -> pick recall/control type.
            # - Otherwise -> pick "Time hos tannlege" (specific problem) when present.
            if not self.call_data.selected_treatment_id and any(
                k in msg_lower for k in ("dentist", "dental", "tannlege", "appointment", "time")
            ):
                wants_recall = any(
                    k in msg_lower
                    for k in ("recall", "checkup", "check-up", "check up", "routine", "kontroll", "sjekk", "undersøk", "undersok")
                )
                if wants_recall:
                    if not _pick_treatment(
                        lambda n, d: ("tannlege" in n and ("recall" in n or "kontroll" in n or "undersøk" in n))
                        or ("recall" in d and "tannlege" in d)
                    ):
                        _pick_treatment(lambda n, d: "recall" in n or "kontroll" in n or "undersøk" in n or "check" in d)
                else:
                    # Prefer specific problem dentist appointment.
                    if not _pick_treatment(lambda n, d: "time hos tannlege" in n or "spesifikt problem" in d):
                        # Fallback: any tannlege entry that is NOT recall/control.
                        _pick_treatment(lambda n, d: "tannlege" in n and not ("recall" in n or "kontroll" in n))
        
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
            await self.samle_personnummer_med_dtmf(context, purpose="booking")
            if not self.call_data.collected_personnummer:
                return {
                    "suksess": False,
                    "melding": self._get_text("personnummer_failed")
                }
            personnr = self.call_data.collected_personnummer
        
        # Phone number choice must be explicitly confirmed for new patients.
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

                if (not is_existing) and self.call_data and (not self.call_data.phone_choice_confirmed):
                    calling = self.call_data.caller_phone or ""
                    if self._language_code() == "en":
                        return {
                            "suksess": False,
                            "melding": f"Before I book it, do you want to use the number you're calling from ({calling}), or do you want to provide a different number?",
                        }
                    return {
                        "suksess": False,
                        "melding": f"Før jeg booker, vil du at jeg skal bruke nummeret du ringer fra ({calling}), eller vil du oppgi et annet nummer?",
                    }

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

                if is_existing and (not opus_result or not opus_result.get("success")):
                    msg = (opus_result or {}).get("message", "") or ""
                    # Treat conflict as "already booked" and stop (never try new-patient booking).
                    if "conflict" in msg.lower():
                        if self._language_code() == "en":
                            return {
                                "suksess": False,
                                "melding": "It looks like this appointment was already booked (conflict). If I can help with anything else, feel free to ask.",
                            }
                        return {
                            "suksess": False,
                            "melding": "Det ser ut som timen allerede er booket (konflikt). Hvis jeg kan hjelpe med noe annet, er det bare å si ifra.",
                        }

                    failure_prefix = self._get_text("booking_failure") or "Klarte ikke å booke timen i systemet."
                    return {
                        "suksess": False,
                        "melding": f"{failure_prefix} {msg}".strip(),
                    }

                if (not is_existing) and (not opus_result or not opus_result.get("success")):
                    # New patient booking requires full name + email.
                    first_name = (patient_first or Fornavn or "").strip()
                    last_name = (patient_last or Etternavn or "").strip()
                    email = (self.call_data.collected_email.strip() if self.call_data else "")

                    if not first_name or not last_name:
                        if self._language_code() == "en":
                            return {
                                "suksess": False,
                                "melding": "I need your full name before I can book this appointment. Please tell me your first and last name.",
                            }
                        return {
                            "suksess": False,
                            "melding": "Jeg trenger fullt navn før jeg kan booke timen. Kan du oppgi fornavn og etternavn?",
                        }

                    if not email:
                        if self._language_code() == "en":
                            return {
                                "suksess": False,
                                "melding": "Email is required to complete the booking. Please provide your email address.",
                            }
                        return {
                            "suksess": False,
                            "melding": "E-post er påkrevd for å fullføre bookingen. Kan du oppgi e-postadressen din?",
                        }

                    opus_result = await book_new_patient(
                        business_id=self.call_data.business_id,
                        pid=personnr,
                        first_name=first_name,
                        last_name=last_name,
                        phone=mobilnr,
                        email=email,
                        treatment_id=int(treatment_id_val),
                        clinician_id=int(clinician_id_val),
                        slot_start=slot_start,
                        slot_end=slot_end,
                    )

                if opus_result.get("success"):
                    if self.call_data:
                        self.call_data.appointment_booked = True

                    booking_id = opus_result.get("bookingId") or opus_result.get("booking_id")
                    confirmation_number = opus_result.get("confirmationNumber") or opus_result.get("confirmation_number")

                    clinician_info = self.call_data.selected_clinician if self.call_data else None
                    if clinician_info and clinician_info.get("name"):
                        c_name = clinician_info["name"]
                        c_title = clinician_info.get("title", "Tannlege")
                        if self._language_code() == "en":
                            title_en = "Dentist" if "tannlege" in c_title.lower() else c_title
                            success_message = f"Your booking is confirmed, {display_name}. Your dentist is {c_name} ({title_en})."
                        else:
                            success_message = f"Timen din er bekreftet, {display_name}. Din tannlege er {c_name} ({c_title})."
                    else:
                        success_template = self._get_text("booking_success") or "Time er nå booket for {name}."
                        success_message = success_template.format(name=display_name)

                    # Append booking reference if available
                    if booking_id:
                        if self._language_code() == "en":
                            success_message += f" Your booking ID is {booking_id}."
                        else:
                            success_message += f" Booking-ID er {booking_id}."
                    if confirmation_number:
                        if self._language_code() == "en":
                            success_message += f" Confirmation number: {confirmation_number}."
                        else:
                            success_message += f" Bekreftelsesnummer: {confirmation_number}."

                    if self._language_code() == "en":
                        success_message += " If you need anything else regarding this booking, feel free to ask."
                    else:
                        success_message += " Hvis du trenger mer hjelp med denne bookingen, er det bare å si ifra."

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
