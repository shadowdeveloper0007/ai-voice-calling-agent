import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class CallData:
    """Data structure to track call information"""
    phone_number: str = ""  # Agent/business phone (from room name)
    caller_phone: str = ""  # Customer's calling number (from room name user_number or SIP identity)
    business_id: str = ""  # Store business_id for API calls (timeslots, booking, etc.)
    call_start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    appointment_booked: bool = False
    conversation_messages: List[Dict[str, str]] = field(default_factory=list)  # Store conversation for summary
    # DTMF collection fields
    dtmf_digits: List[str] = field(default_factory=list)
    collected_personnummer: str = ""  # Store collected personnummer for reuse
    alternative_phone_number: str = ""  # Store DTMF-collected phone number
    phone_choice_confirmed: bool = False  # Caller confirmed calling number vs different number for booking
    language: str = "no"  # Current conversation language: "no" for Norwegian, "en" for English (can be changed anytime on explicit user request)
    is_console_mode: bool = False  # Flag to indicate console mode for auto-fill
    booking_preference: Optional[str] = None  # "first_available", "specific_date", or None
    treatment_type_for_change: Optional[str] = None  # Store treatment_type when changing appointment, so it can be reused
    old_appointment_details: Optional[Dict[str, Any]] = None  # Store old appointment details when changing appointment
    dtmf_event: Optional[asyncio.Event] = field(init=False, default=None)
    pending_message_future: Optional[asyncio.Future] = field(init=False, default=None)
    recorded_message: Optional[str] = None  # Store captured customer message for reuse
    customer_first_name: str = ""
    customer_last_name: str = ""
    message_sent: bool = False
    last_assistant_message: Optional[str] = None  # Store last assistant message for language switch repetition
    selected_treatment_id: Optional[int] = None  # Store selected treatment ID for timeslot/booking
    selected_timeslot: Optional[Dict[str, Any]] = None  # Store selected timeslot for booking confirmation
    selected_clinician: Optional[Dict[str, Any]] = None  # Store preferred clinician info (id, name, title) from clinicians API
    available_timeslots: Optional[List[Dict[str, Any]]] = None  # Store all available timeslots for user selection
    collected_email: str = ""

    def __post_init__(self):
        # Event must be created inside running loop
        try:
            asyncio.get_running_loop()
            self.dtmf_event = asyncio.Event()
        except RuntimeError:
            self.dtmf_event = None
