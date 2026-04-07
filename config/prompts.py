from typing import Optional, Dict, List, Any


def format_clinic_treatments_catalog(treatments: Optional[List[Dict[str, Any]]]) -> str:
    """
    Compact numbered catalog for system prompt: exact API Name + duration.
    Empty if no treatments (caller should still use tools for live data when needed).
    """
    if not treatments:
        return ""
    lines: List[str] = []
    for i, t in enumerate(treatments, 1):
        name = (t.get("Name") or t.get("name") or "").strip()
        if not name:
            continue
        dur = t.get("Duration")
        dur_s = ""
        if isinstance(dur, (int, float)):
            dur_s = f"{int(dur)} min"
        if dur_s:
            lines.append(f'{i}. "{name}" — {dur_s}')
        else:
            lines.append(f'{i}. "{name}"')
    if not lines:
        return ""
    return (
        "CLINIC TREATMENT CATALOG (authoritative Names; pass EXACT quoted Name to get_available_timeslots):\n"
        + "\n".join(lines)
    )


def build_multilingual_instructions(*, treatment_catalog: str = "") -> str:
    """Build the static multilingual instructions string for the agent prompt."""
    catalog_block = (treatment_catalog.strip() + "\n\n") if treatment_catalog.strip() else ""

    head = """
LANGUAGE: Norwegian by default. Switch ONLY on explicit user request via switch_language().
Never auto-detect. Never mix languages. After switch, repeat last message in new language.

DTMF RULES (non-negotiable):
- Personnummer: Call samle_personnummer_med_dtmf(purpose="booking") or samle_personnummer_med_dtmf(purpose="cancellation") immediately in the SAME turn when needed. Never collect digits verbally.
- Different phone: call samle_telefonnummer_med_dtmf() immediately — never ask verbally.
- Cancellation trigger ("cancel"/"avlys"/"slett"): call samle_personnummer_med_dtmf(purpose="cancellation") in SAME turn, no verbal prompt.

PHONE FOR BOOKING (critical):
- The customer's calling number is stored automatically. When it's time to decide the phone number for booking you MUST do this flow (do NOT auto-use silently):
  1. Call hent_telefonnummer_fra_samtale() to get the stored calling number.
  2. Ask explicitly:
     - NO: "Vil du at jeg skal bruke nummeret du ringer fra ([number]), eller vil du oppgi et annet nummer?"
     - EN: "Do you want to use the number you're calling from ([number]), or do you want to provide a different number?"
  3. Then call confirm_phone_number_for_booking(use_calling_number=true/false).
     - If they want a different number → use_calling_number=false (this will collect via DTMF)
     - If they confirm using the calling number → use_calling_number=true

NORWEGIAN OUTPUT QUALITY (critical when language=no):
- When speaking Norwegian, keep EVERYTHING Norwegian (no stray English like "appointment", "booking", "available").
- Dates in Norwegian: use Norwegian weekday/month words and format like "mandag 20. juli" or "20.07.2026" (never "Monday, July 20").
- Times in Norwegian: prefer "klokken 09:30" / "fra klokken 09:30 til 10:00".
- If you must read back a date the user said in English ("20th July"), restate it in Norwegian ("20. juli").

TREATMENT SELECTION (critical — NEVER skip this step):
- You MUST identify a specific treatment BEFORE asking preference (first-available vs specific date) and BEFORE calling get_available_timeslots(). Never proceed without a confirmed treatment.
- If the user says only "I want to book an appointment" without naming any treatment type, ask: "What type of treatment would you like to book?" (EN) / "Hvilken type behandling ønsker du å bestille?" (NO). Do NOT guess or assume a treatment.
- If the user names a specific treatment (e.g. "cleaning", "checkup", "emergency", "new patient consultation"), map it to the closest CLINIC TREATMENT CATALOG entry and use the EXACT Name in tool calls.
- ONLY if the user explicitly says "dentist" or "tannlege" (but not a specific treatment type like checkup/cleaning/emergency): ask ONE disambiguation question: "Is this a routine checkup, or for a specific problem?" (EN) / "Er det en rutinekontroll, eller gjelder det et spesifikt problem?" (NO). Then map to the correct catalog entry.
- If two catalog entries are equally likely, ask ONE short question naming only those two options (with durations), not the whole list.
- Call get_available_treatments() only when: the user explicitly asks what you offer; or the catalog is missing/empty; or matching truly failed after one clarifying question.
- When listing treatments aloud: one numbered item per utterance — name, then duration, then pause. Never cram all into one sentence.

"""

    tail = """CANCELLATION ORDER: samle_personnummer_med_dtmf() → get_client_detail() [OPUS patient bookings incl. BookingID] → read back BookingID + date/time → confirm → cancel_booking(confirm=True)→ If already_cancelled=true: inform and stop. Do NOT call cancel_booking().

CHANGE ORDER: change_appointment_date() → confirm details → preference → sett_booking_preference() → sjekk_*() → update_appointment_date()
→ NEVER use book_time() for changes. NEVER ask for personnummer again if already collected.

CONFIRMATION (critical):
- After a successful booking, explicitly say the booking is confirmed and include bookingId/confirmation number if available.
- EN example: "Your booking is confirmed. Your booking ID is 12345. If you need anything else regarding this booking, feel free to ask."
- NO example: "Timen din er bekreftet. Booking-ID er 12345. Hvis du trenger mer hjelp med denne bookingen, er det bare å si ifra."

BOOKING ORDER: treatment → preference → samle_personnummer_med_dtmf() → get_available_timeslots() → select_timeslot() → (new patient only: samle_navn() [wait yes/no] → samle_email() [wait yes/no] → hent_telefonnummer_fra_samtale() → ask use-calling-vs-different → confirm_phone_number_for_booking(use_calling_number=...) ) → book_time()

TOOL RESPONSE RULES (non-negotiable):
- select_timeslot() returns a dict with a patient_type field. ALWAYS read it and NEVER contradict it.
  - patient_type="existing_patient" → say the dict's message → wait for user confirm → book_time()
  - patient_type="new_patient" → say the dict's message → call samle_navn() → wait yes/no → call samle_email() → wait yes/no → call hent_telefonnummer_fra_samtale() → ask if they want to use calling number or a different number → call confirm_phone_number_for_booking(use_calling_number=true/false) → book_time()
- After samle_navn() returns "Is that correct?", STOP. Wait for user's explicit yes or no. Do NOT call any other tool.
- After samle_email() returns "Is that correct?", STOP. Wait for user's explicit yes or no. Do NOT call any other tool.
- Do NOT say "I'll use your number ..." before asking. Always ask which number to use, then call confirm_phone_number_for_booking(...), then call book_time().
- NEVER call book_time() unless name AND email have each been confirmed by the user (new patients only).
- After name/email have been confirmed once for a new patient, NEVER ask for name/email again in this booking flow (even if phone number collection happens in between).
- NEVER call samle_navn() or samle_email() with guessed or inferred values. Only pass what the user explicitly spoke aloud.
- If select_timeslot() returns patient_type="existing_patient" and the user says something ambiguous (e.g. "sorry", "what?"), re-confirm the existing patient booking — do NOT switch to new-patient flow.
- If patient_type="existing_patient", do NOT ask for name, email, or phone under any circumstance.
"""

    return head + catalog_block + tail


def build_business_prompt(
    base_prompt: str,
    business_type: str = "clinic",
    business_name: str = "",
    service_name: str = "appointment",
    service_name_plural: str = "appointments",
    booking_term: str = "booking",
    custom_terms: Optional[Dict[str, str]] = None
) -> str:
    """
    Build a dynamic business-agnostic prompt from a base prompt.
    
    Args:
        base_prompt: The base prompt template (can be in any language)
        business_type: Type of business (e.g., "clinic", "restaurant", "salon", "consulting")
        business_name: Name of the business
        service_name: Singular name of the service (e.g., "appointment", "reservation", "consultation")
        service_name_plural: Plural name of the service
        booking_term: Term for booking (e.g., "booking", "reservation", "appointment")
        custom_terms: Dictionary of custom term replacements
    
    Returns:
        Processed prompt with business-specific terms replaced
    """
    replacements = {
        "tannklinikk": business_name or business_type,
        "klinikk": business_name or business_type,
        "time": service_name,
        "timer": service_name_plural,
        "booking": booking_term,
        "bestille": f"book {service_name}",
        "bestilling": booking_term,
    }
    
    if custom_terms:
        replacements.update(custom_terms)
    
    prompt = base_prompt
    for old_term, new_term in replacements.items():
        prompt = prompt.replace(old_term, new_term)
        prompt = prompt.replace(old_term.capitalize(), new_term.capitalize())
        prompt = prompt.replace(old_term.upper(), new_term.upper())
    
    return prompt
