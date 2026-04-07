import asyncio
import aiohttp
import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

from livekit.agents import Agent, RunContext

from core.call_data import CallData
from core.language_texts import LANGUAGE_TEXTS
from config.prompts import (
    build_multilingual_instructions,
    build_business_prompt,
    format_clinic_treatments_catalog,
)
from OPUS_routes import (
    find_patient_slot,
    OPUS_PREFERRED_CLINICIAN_ID, OPUS_CLINIC_ID,
)
from tools.booking import BookingToolsMixin
from tools.client import ClientToolsMixin
from tools.communication import CommunicationToolsMixin
from tools.general import GeneralToolsMixin


class Assistant(
    BookingToolsMixin,
    ClientToolsMixin,
    CommunicationToolsMixin,
    GeneralToolsMixin,
    Agent,
):
    def __init__(
        self,
        prompt_template: str,
        persona_prompt: str,
        business_name: str,
        booking_config: dict,
        call_data: CallData = None,
        business_info: Optional[Any] = None,
        job_context=None,
        agent_name: str = None,
        conversation_history: dict = None,
        business_type: str = "clinic",
        booking_term: str = "booking",
        custom_terms: Optional[Dict[str, str]] = None,
        clinic_treatments: List[Dict] = None,
    ) -> None:
        import pytz
        norwegian_tz = pytz.timezone('Europe/Oslo')
        current_time = datetime.now(norwegian_tz)
        
        day_names = {
            'Monday': 'mandag',
            'Tuesday': 'tirsdag', 
            'Wednesday': 'onsdag',
            'Thursday': 'torsdag',
            'Friday': 'fredag',
            'Saturday': 'lørdag',
            'Sunday': 'søndag'
        }
        
        month_names = {
            1: 'januar', 2: 'februar', 3: 'mars', 4: 'april',
            5: 'mai', 6: 'juni', 7: 'juli', 8: 'august',
            9: 'september', 10: 'oktober', 11: 'november', 12: 'desember'
        }
        
        day_name = day_names[current_time.strftime('%A')]
        date_str = f"{current_time.day} {month_names[current_time.month]} {current_time.year}"
        time_str = current_time.strftime('%H:%M')
        
        day_name_with_date = f"{day_name} {date_str}"
        time_str_with_label = f"{time_str} (lokal tid)"

        treatment_catalog = format_clinic_treatments_catalog(clinic_treatments or [])
        multilingual_instructions = build_multilingual_instructions(
            treatment_catalog=treatment_catalog
        )
        
        conversation_history_text = ""
        
        replacements = {
            '{CURRENT_DAY_NAME}': day_name_with_date,
            '{CURRENT_DATE}': date_str,
            '{CURRENT_TIME}': time_str_with_label,
            '{AGENT_NAME}': agent_name or 'AI Resepsjonist',
            '{BUSINESS_NAME}': business_name,
            '{CLINIC_NAME}': business_name,
            '{PERSONA_PROMPT}': persona_prompt or '',
            '{BUSINESS_INFO_JSON}': "",
            '{CONVERSATION_HISTORY}': conversation_history_text,
        }
        
        if prompt_template:
            full_prompt = prompt_template
            for placeholder, value in replacements.items():
                full_prompt = full_prompt.replace(placeholder, value)
            
            if '[SLUTT SYSTEMKONTEKST]' in full_prompt:
                parts = full_prompt.split('[SLUTT SYSTEMKONTEKST]', 1)
                if len(parts) == 2:
                    full_prompt = parts[0] + '[SLUTT SYSTEMKONTEKST]\n\n' + multilingual_instructions + '\n' + parts[1]
                else:
                    full_prompt = multilingual_instructions + '\n\n' + full_prompt
            else:
                full_prompt = multilingual_instructions + '\n\n' + full_prompt
        else:
            full_prompt = multilingual_instructions + f"\n\nDu er {agent_name or 'AI Resepsjonist'}, en AI resepsjonist hos {business_name}. {persona_prompt or ''}"
        
        print("\n" + "=" * 100)
        print("[FULL PROMPT]")
        print("=" * 100)
        print(full_prompt)
        print("=" * 100 + "\n")
        
        super().__init__(instructions=full_prompt)
        self.booking_config = booking_config
        self.business_name = business_name
        self.business_type = business_type
        self.call_data = call_data
        self.job_context = job_context
        self.conversation_history = conversation_history
        self.cached_business_info = business_info or ""
        self.clinic_treatments = clinic_treatments or []

    # ── shared private helpers (used by mixins via self) ──────────────

    def _language_code(self) -> str:
        if self.call_data and self.call_data.language == "en":
            return "en"
        return "no"

    def _get_text(self, key: str):
        entry = LANGUAGE_TEXTS.get(key)
        if not entry:
            return ""
        lang = self._language_code()
        return entry.get(lang) or entry.get("no") or ""

    def _get_text_list(self, key: str) -> List[str]:
        value = self._get_text(key)
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str) and value:
            return [value]
        return []

    def _status_error_message(self, status: int) -> str:
        template = self._get_text("status_error")
        if template:
            return template.replace("{status}", str(status))
        if self._language_code() == "en":
            return f"Could not contact the booking system. Status code: {status}"
        return f"Fikk ikke kontakt med bookingsystemet. Statuskode: {status}"

    def _technical_error_message(self, context_type: str) -> str:
        if context_type == "availability":
            return self._get_text("technical_error_availability") or ("A technical error occurred while checking available times." if self._language_code() == "en" else "En teknisk feil oppstod ved sjekking av ledige timer.")
        if context_type == "booking":
            return self._get_text("technical_error_booking") or ("A technical error occurred while booking the appointment." if self._language_code() == "en" else "En teknisk feil oppstod under booking.")
        if context_type == "message":
            return self._get_text("technical_error_message") or ("A technical error occurred while sending the message." if self._language_code() == "en" else "En teknisk feil oppstod ved sending av beskjed.")
        if context_type == "update_appointment":
            return self._get_text("update_appointment_failure") or ("En teknisk feil oppstod ved oppdatering av timen." if self._language_code() == "no" else "A technical error occurred while updating the appointment.")
        return self._get_text("technical_error_generic") or ("A technical error occurred." if self._language_code() == "en" else "En teknisk feil oppstod.")

    def _default_message_summary(self) -> str:
        """Fallback summary when no explicit customer message was captured."""
        return self._get_text("default_message_summary") or ("Customer asked for a callback. No additional details were provided." if self._language_code() == "en" else "Kunden ønsket å bli kontaktet. Ingen ytterligere detaljer ble gitt.")

    async def _call_webhook_with_retry(
        self,
        method: str,
        url: str,
        data: dict,
        max_retries: int = 2,
        timeout: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """
        Call webhook with timeout and retry logic.
        
        Args:
            method: HTTP method ('GET', 'POST', 'PUT')
            url: Webhook URL
            data: Request data (JSON payload)
            max_retries: Maximum number of retries (default: 2, so 1 initial + 2 retries = 3 total attempts)
            timeout: Timeout in seconds (default: 10.0)
        
        Returns:
            Dict with 'status', 'text', and 'json' keys if successful, None if all retries failed
        """
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        
        for attempt in range(max_retries + 1):
            try:
                print(f"[WEBHOOK] Attempt {attempt + 1}/{max_retries + 1} - {method} {url}")
                if attempt > 0:
                    print(f"[WEBHOOK] Retrying after timeout...")
                
                async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                    if method.upper() == 'GET':
                        async with session.get(url, json=data) as response:
                            response_text = await response.text()
                            try:
                                response_json = await response.json()
                            except:
                                response_json = None
                            return {
                                'status': response.status,
                                'text': response_text,
                                'json': response_json
                            }
                    elif method.upper() == 'POST':
                        async with session.post(url, json=data) as response:
                            response_text = await response.text()
                            try:
                                response_json = await response.json()
                            except:
                                response_json = None
                            return {
                                'status': response.status,
                                'text': response_text,
                                'json': response_json
                            }
                    elif method.upper() == 'PUT':
                        async with session.put(url, json=data) as response:
                            response_text = await response.text()
                            try:
                                response_json = await response.json()
                            except:
                                response_json = None
                            return {
                                'status': response.status,
                                'text': response_text,
                                'json': response_json
                            }
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")
                        
            except asyncio.TimeoutError:
                print(f"[WEBHOOK] Timeout on attempt {attempt + 1}/{max_retries + 1} (>{timeout}s)")
                if attempt < max_retries:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    print(f"[WEBHOOK] All {max_retries + 1} attempts timed out")
                    return None
            except Exception as e:
                print(f"[WEBHOOK] Error on attempt {attempt + 1}/{max_retries + 1}: {str(e)}")
                if attempt < max_retries:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    print(f"[WEBHOOK] All {max_retries + 1} attempts failed")
                    return None
        
        return None

    def _normalize_string(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return str(value)

    def _parse_iso_datetime(self, value: str) -> Tuple[Optional[str], Optional[str]]:
        if not isinstance(value, str):
            return (None, None)
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return (dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"))
        except ValueError:
            return (None, None)

    def _extract_time_slots(self, payload: Any) -> List[tuple]:
        slots: List[tuple] = []
        date_keys = ("dato", "Dato", "date", "Date")
        time_keys = ("tid", "Tid", "time", "Time")
        start_keys = ("start", "Start", "start_time", "startTime", "StartTid", "StartTime")

        def add_slot(date_value, time_value):
            date_norm = self._normalize_string(date_value)
            time_norm = self._normalize_string(time_value)
            if date_norm or time_norm:
                slots.append((date_norm, time_norm))

        def handle_entry(entry):
            if isinstance(entry, dict):
                date_val = next((entry.get(k) for k in date_keys if entry.get(k)), None)
                time_val = next((entry.get(k) for k in time_keys if entry.get(k)), None)
                start_val = next((entry.get(k) for k in start_keys if entry.get(k)), None)
                if start_val:
                    parsed_date, parsed_time = self._parse_iso_datetime(start_val)
                    date_val = date_val or parsed_date
                    time_val = time_val or parsed_time
                if date_val or time_val:
                    add_slot(date_val, time_val)
                for key in ("data", "available_times", "availableTimes", "available_slots", "availableSlots", "slots", "times", "availability", "result"):
                    if key in entry:
                        handle_entry(entry[key])
            elif isinstance(entry, list):
                for item in entry:
                    handle_entry(item)
            elif isinstance(entry, str):
                parsed_date, parsed_time = self._parse_iso_datetime(entry)
                if parsed_date or parsed_time:
                    add_slot(parsed_date, parsed_time)

        handle_entry(payload)
        return slots

    def _format_date_for_language(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        lang = self._language_code()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                dt = datetime.strptime(date_str, fmt)
                if lang == "en":
                    return dt.strftime("%B %d, %Y")
                return dt.strftime("%d.%m.%Y")
            except ValueError:
                continue
        return date_str

    def _format_time_for_language(self, time_str: Optional[str]) -> Optional[str]:
        if not time_str:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.strftime("%H:%M")
            except ValueError:
                continue
        return time_str

    def _format_first_slot_text(self, slots: List[tuple]) -> str:
        if not slots:
            return ""
        date_text = self._format_date_for_language(slots[0][0])
        time_text = self._format_time_for_language(slots[0][1])
        lang = self._language_code()
        if lang == "en":
            if date_text and time_text:
                return f" The earliest available slot is {date_text} at {time_text}."
            if date_text:
                return f" The earliest available slot is on {date_text}."
            if time_text:
                return f" The earliest available slot is at {time_text}."
            return ""
        else:
            if date_text and time_text:
                return f" Den første ledige tiden er {date_text} klokken {time_text}."
            if date_text:
                return f" Den første ledige tiden er {date_text}."
            if time_text:
                return f" Den første ledige tiden er klokken {time_text}."
            return ""

    def _format_multi_slot_text(self, slots: List[tuple], limit: int = 3) -> str:
        if not slots:
            return ""
        lang = self._language_code()
        items = []
        for date_value, time_value in slots[:limit]:
            date_text = self._format_date_for_language(date_value)
            time_text = self._format_time_for_language(time_value)
            if lang == "en":
                if date_text and time_text:
                    items.append(f"{date_text} at {time_text}")
                elif date_text:
                    items.append(date_text)
                elif time_text:
                    items.append(f"at {time_text}")
            else:
                if date_text and time_text:
                    items.append(f"{date_text} klokken {time_text}")
                elif date_text:
                    items.append(date_text)
                elif time_text:
                    items.append(f"klokken {time_text}")
        if not items:
            return ""
        if lang == "en":
            return f" Available times: {', '.join(items)}."
        return f" Ledige timer: {', '.join(items)}."

    async def _wait_for_customer_message_input(self, timeout: float = 35.0) -> Optional[str]:
        """Wait for the next finalized user utterance to use as the recorded message."""
        if not self.call_data:
            return None
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        pending = getattr(self.call_data, "pending_message_future", None)
        if pending and not pending.done():
            pending.cancel()

        self.call_data.pending_message_future = future
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            if self.call_data:
                self.call_data.pending_message_future = None

    async def _capture_customer_message(self, context: RunContext, force_new: bool = False) -> Optional[str]:
        """
        Prompt the customer to dictate a message and capture the next completed
        transcript. Returns None if nothing was captured.
        """
        if self.call_data and self.call_data.recorded_message and not force_new:
            return self.call_data.recorded_message

        prompt = self._get_text("leave_message_capture_prompt")
        if prompt:
            context.session.say(prompt, allow_interruptions=False)
            await context.wait_for_playout()

        captured = await self._wait_for_customer_message_input()
        if captured:
            confirm = self._get_text("leave_message_capture_confirm")
            if confirm:
                context.session.say(confirm, allow_interruptions=False)
                await context.wait_for_playout()
            captured_clean = captured.strip()
            if self.call_data:
                self.call_data.recorded_message = captured_clean
            return captured_clean

        timeout_text = self._get_text("leave_message_capture_timeout")
        if timeout_text:
            context.session.say(timeout_text, allow_interruptions=False)
            await context.wait_for_playout()
        return None

    async def _ensure_customer_name(
        self,
        context: RunContext,
        provided_first: str,
        provided_last: str,
        force_prompt: bool = False
    ) -> Tuple[str, str]:
        """Ensure we have at least the customer's first name (last name optional)."""
        first = self._normalize_string(provided_first)
        last = self._normalize_string(provided_last)

        if not force_prompt and self.call_data:
            if not first and self._normalize_string(self.call_data.customer_first_name):
                first = self.call_data.customer_first_name.strip()
            if not last and self._normalize_string(self.call_data.customer_last_name):
                last = self.call_data.customer_last_name.strip()

        if first and not force_prompt:
            if self.call_data:
                self.call_data.customer_first_name = first
                self.call_data.customer_last_name = last or self.call_data.customer_last_name
            return first, last or ""

        attempts = 0
        while attempts < 2 and not first:
            prompt = self._get_text("leave_message_name_prompt") or "Kan jeg få navnet ditt?"
            context.session.say(prompt, allow_interruptions=False)
            await context.wait_for_playout()

            captured = await self._wait_for_customer_message_input()
            if captured:
                parts = [p for p in captured.strip().split() if p]
                if parts:
                    first = parts[0]
                    if len(parts) > 1:
                        last = " ".join(parts[1:])
                    confirm = self._get_text("leave_message_name_confirm")
                    if confirm:
                        context.session.say(confirm.format(name=first), allow_interruptions=False)
                        await context.wait_for_playout()
                    break

            attempts += 1
            if not first:
                retry = self._get_text("leave_message_name_retry")
                if retry:
                    context.session.say(retry, allow_interruptions=False)
                    await context.wait_for_playout()

        if not first:
            first = self._get_text("default_customer_name") or ("Customer" if self._language_code() == "en" else "Kunde")

        if self.call_data:
            self.call_data.customer_first_name = first
            if last:
                self.call_data.customer_last_name = last

        return first, last or ""

    def _resolve_requested_date(self, preferred: Optional[str], payload: Any) -> Optional[str]:
        candidate = self._normalize_string(preferred)
        if not candidate and isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                for key in ("requested_date", "requestedDate", "date", "Dato", "dato"):
                    val = self._normalize_string(data.get(key))
                    if val:
                        candidate = val
                        break
        if not candidate and isinstance(payload, dict):
            for key in ("requested_date", "requestedDate", "date", "Dato", "dato"):
                val = self._normalize_string(payload.get(key))
                if val:
                    candidate = val
                    break
        if candidate:
            return self._format_date_for_language(candidate) or candidate
        return None

    def _no_availability_first_message(self, extra: Optional[str] = None) -> str:
        base = self._get_text("no_availability_first")
        if not base:
            base = "Beklager, jeg fant ingen ledige timer akkurat nå."
            if self._language_code() == "en":
                base = "I'm sorry, I couldn't find any available appointments right now."
        return base

    def _no_availability_date_message(self, payload: Any, preferred_date: Optional[str]) -> str:
        date_text = self._resolve_requested_date(preferred_date, payload)
        if not date_text:
            date_text = self._get_text("requested_date_placeholder") or ("the requested date" if self._language_code() == "en" else "den ønskede datoen")
        template = self._get_text("no_availability_date")
        if template:
            return template.replace("{date}", date_text)
        if self._language_code() == "en":
            return f"I'm sorry, we don't have availability on {date_text}."
        return f"Beklager, vi har ingen ledige timer {date_text}."

    def _prepare_dtmf_event(self) -> Optional[asyncio.Event]:
        if not self.call_data:
            return None
        if self.call_data.dtmf_event is None:
            try:
                self.call_data.dtmf_event = asyncio.Event()
            except RuntimeError:
                return None
        else:
            self.call_data.dtmf_event.clear()
        return self.call_data.dtmf_event

    async def _wait_for_dtmf(self, dtmf_event: Optional[asyncio.Event], timeout_seconds: float) -> bool:
        if not dtmf_event:
            await asyncio.sleep(0.05)
            return True
        try:
            await asyncio.wait_for(dtmf_event.wait(), timeout=timeout_seconds)
            dtmf_event.clear()
            return True
        except asyncio.TimeoutError:
            return False

    async def _opus_find_timeslot(self, starting_from: Optional[str] = None) -> dict:
        """Shared OPUS API logic: find slot via POST /api/Opus/patient/find-slot."""
        lang = self._language_code()
        business_id = self.call_data.business_id if self.call_data else None
        treatment_id = self.call_data.selected_treatment_id if self.call_data else None
        pid = self.call_data.collected_personnummer if self.call_data else ""

        treatment_name = None
        if treatment_id and self.clinic_treatments:
            for t in self.clinic_treatments:
                if (t.get("ID") or t.get("id")) == treatment_id:
                    treatment_name = t.get("Name") or t.get("name")
                    break

        if not treatment_name and self.call_data and self.call_data.treatment_type_for_change and self.clinic_treatments:
            name_hint = (self.call_data.treatment_type_for_change or "").strip().lower()
            for t in self.clinic_treatments:
                t_name = (t.get("Name") or t.get("name") or "").lower()
                t_desc = (t.get("Description") or t.get("description") or "").lower()
                if name_hint in t_name or name_hint in t_desc or "recall" in t_name or "recall" in t_desc:
                    treatment_name = t.get("Name") or t.get("name")
                    treatment_id = t.get("ID") or t.get("id")
                    if treatment_id and self.call_data:
                        self.call_data.selected_treatment_id = treatment_id
                    break

        print(f"[OPUS FLOW] _opus_find_timeslot called: business_id={business_id}, treatment_name={treatment_name}, pid={'***' if pid else 'MISSING'}, starting_from={starting_from}")

        if not business_id or not treatment_name:
            print(f"[OPUS FLOW] Abort: missing business_id or treatment_name")
            return {
                "suksess": False,
                "melding": "Unable to check availability." if lang == "en" else "Kan ikke sjekke tilgjengelighet for øyeblikket."
            }

        if not pid:
            print("[OPUS FLOW] Abort: missing personnummer (pid)")
            return {
                "suksess": False,
                "melding": "Personal ID number is required to check availability. Please collect it first." if lang == "en" else "Personnummer er påkrevd for å sjekke tilgjengelighet. Vennligst samle det inn først."
            }

        try:
            print("[OPUS FLOW] Calling find_patient_slot API...")
            slots = await find_patient_slot(business_id, pid, treatment_name, starting_from)

            found_slots = [s for s in slots if s.get("found")]

            if not found_slots:
                not_found_reason = next((s.get("reason") for s in slots if not s.get("found") and s.get("reason")), None)
                print(f"[OPUS FLOW] No available slots. Reason: {not_found_reason}")
                if lang == "en":
                    return {"suksess": False, "melding": "Sorry, the dentist has no available appointments right now. Would you like to check another date?"}
                return {"suksess": False, "melding": "Beklager, tannlegen har ingen ledige timer akkurat nå. Vil du prøve en annen dato?"}

            first_slot = found_slots[0]
            clinician_name = first_slot.get("clinicianName", "")
            clinician_id = first_slot.get("clinicianId")
            clinician_title = "Tannlege"

            if self.call_data:
                if first_slot.get("patientFirstName"):
                    self.call_data.customer_first_name = first_slot["patientFirstName"]
                if first_slot.get("patientLastName"):
                    self.call_data.customer_last_name = first_slot["patientLastName"]
                if first_slot.get("treatmentId"):
                    self.call_data.selected_treatment_id = first_slot["treatmentId"]

            if self.call_data:
                self.call_data.selected_clinician = {
                    "id": clinician_id,
                    "name": clinician_name,
                    "title": clinician_title,
                }

            max_slots = min(len(found_slots), 5)
            display_slots = found_slots[:max_slots]

            if self.call_data:
                self.call_data.available_timeslots = display_slots
                self.call_data.selected_timeslot = display_slots[0] if len(display_slots) == 1 else None

            def _fmt(s):
                st = s.get('slotStart') or s.get('start') or s.get('Start') or ''
                en = s.get('slotEnd') or s.get('end') or s.get('End') or ''
                try:
                    d = datetime.fromisoformat(st.replace('Z', '+00:00'))
                except:
                    d = datetime.strptime(st[:19], "%Y-%m-%dT%H:%M:%S")
                try:
                    d2 = datetime.fromisoformat(en.replace('Z', '+00:00'))
                except:
                    d2 = datetime.strptime(en[:19], "%Y-%m-%dT%H:%M:%S")
                return d, d2

            title_en = "Dentist" if "tannlege" in clinician_title.lower() else clinician_title

            if len(display_slots) == 1:
                dt, dt_end = _fmt(display_slots[0])
                if lang == "en":
                    msg = (f"I found an appointment from {dt.strftime('%H:%M')} to {dt_end.strftime('%H:%M')} "
                           f"on {dt.strftime('%A, %B %d')} with {clinician_name} ({title_en}). Should I book that for you?")
                else:
                    day_names_no = ['mandag','tirsdag','onsdag','torsdag','fredag','lørdag','søndag']
                    month_names_no = ['januar','februar','mars','april','mai','juni','juli','august','september','oktober','november','desember']
                    msg = (f"Jeg fant en ledig time fra klokken {dt.strftime('%H:%M')} til {dt_end.strftime('%H:%M')} "
                           f"på {day_names_no[dt.weekday()]} {dt.day}. {month_names_no[dt.month-1]} "
                           f"hos {clinician_name} ({clinician_title}). Skal jeg booke den for deg?")
                return {"suksess": True, "melding": msg, "data": display_slots[0]}

            slot_lines = []
            for i, s in enumerate(display_slots, 1):
                dt, dt_end = _fmt(s)
                if lang == "en":
                    slot_lines.append(f"{i}. {dt.strftime('%A, %B %d')} from {dt.strftime('%H:%M')} to {dt_end.strftime('%H:%M')}")
                else:
                    day_names_no = ['mandag','tirsdag','onsdag','torsdag','fredag','lørdag','søndag']
                    month_names_no = ['januar','februar','mars','april','mai','juni','juli','august','september','oktober','november','desember']
                    slot_lines.append(f"{i}. {day_names_no[dt.weekday()]} {dt.day}. {month_names_no[dt.month-1]} fra klokken {dt.strftime('%H:%M')} til {dt_end.strftime('%H:%M')}")

            if lang == "en":
                header = f"I found {len(display_slots)} available time slots with {clinician_name} ({title_en}):"
                footer = "Which one would you like to book?"
            else:
                header = f"Jeg fant {len(display_slots)} ledige timer hos {clinician_name} ({clinician_title}):"
                footer = "Hvilken ønsker du å booke?"

            msg = f"{header}\n" + "\n".join(slot_lines) + f"\n{footer}"
            return {"suksess": True, "melding": msg, "data": display_slots}

        except Exception as e:
            print(f"[TOOL] _opus_find_timeslot error: {e}")
            return {"suksess": False, "melding": "A technical error occurred." if lang == "en" else "En teknisk feil oppstod."}
