import aiohttp
import json
from typing import List, Dict, Optional
from datetime import datetime

import config.constants as cfg

OPUS_API_URL = cfg.OPUS_API_URL
OPUS_BEARER_TOKEN = cfg.OPUS_BEARER_TOKEN

async def get_clinic_treatments(business_id: str) -> List[Dict]:
    """
    Fetch all available treatments for a clinic from Opus API.
    
    Args:
        business_id: The GUID business ID of the clinic
        
    Returns:
        List of treatment dictionaries, or empty list if error
    """
    if not OPUS_BEARER_TOKEN:
        print("[OPUS] Warning: OPUS_BEARER_TOKEN not set in environment variables.")
        return []

    url = f"{OPUS_API_URL}/api/Opus/treatments"
    
    params = {
        "businessId": business_id,
        "useTestEnvironment": "true" if cfg.OPUS_USE_TEST_ENV else "false",
    }
    
    headers = {
        "Authorization": f"Bearer {OPUS_BEARER_TOKEN}",
        "Content-Type": "application/json"
    }

    print(f"[OPUS] Fetching treatments for business: {business_id} from {url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"[OPUS] Successfully fetched {len(data)} treatments.")
                    return data
                else:
                    text_response = await response.text()
                    print(f"[OPUS] Error fetching treatments. Status: {response.status}, Response: {text_response}")
                    return []
    except Exception as e:
        print(f"[OPUS] Exception fetching treatments: {e}")
        return []


OPUS_PREFERRED_CLINICIAN_ID = cfg.OPUS_PREFERRED_CLINICIAN_ID
OPUS_CLINIC_ID = cfg.OPUS_CLINIC_ID


async def get_clinicians(
    business_id: str,
    clinic_id: str,
    treatment_id: int,
    use_test_environment: Optional[bool] = None
) -> List[Dict]:
    """
    Fetch clinicians for a clinic+treatment from Opus API.
    GET /api/Opus/clinicians
    """
    if not OPUS_BEARER_TOKEN:
        print("[OPUS] Warning: OPUS_BEARER_TOKEN not set.")
        return []

    use_test = use_test_environment if use_test_environment is not None else cfg.OPUS_USE_TEST_ENV
    url = f"{OPUS_API_URL}/api/Opus/clinicians"
    params = {
        "businessId": business_id,
        "clinicId": clinic_id,
        "treatmentId": str(treatment_id),
        "useTestEnvironment": "true" if use_test else "false",
    }
    headers = {
        "Authorization": f"Bearer {OPUS_BEARER_TOKEN}",
        "Accept": "application/json",
    }

    full_url = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    print("[OPUS API] ========== CLINICIANS REQUEST ==========")
    print(f"[OPUS API] GET {full_url}")
    print(f"[OPUS API] Headers: Accept=application/json, Authorization=Bearer ***")
    print("[OPUS API] ========================================")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                text_response = await response.text()
                print(f"[OPUS API] CLINICIANS Response Status: {response.status}")
                try:
                    data = json.loads(text_response) if text_response else []
                except json.JSONDecodeError:
                    data = []
                if response.status == 200:
                    all_clinicians = data if isinstance(data, list) else []
                    print(f"[OPUS API] CLINICIANS Response Body: {len(all_clinicians)} clinicians, ids={[c.get('id') for c in all_clinicians] if all_clinicians else []}")
                    matched = [c for c in all_clinicians if c.get('id') == OPUS_PREFERRED_CLINICIAN_ID]
                    if matched:
                        print(f"[OPUS] Preferred clinician {OPUS_PREFERRED_CLINICIAN_ID} found: {matched[0].get('name')}")
                        return matched
                    print(f"[OPUS] Preferred clinician {OPUS_PREFERRED_CLINICIAN_ID} NOT found. Returning empty.")
                    return []
                print(f"[OPUS API] CLINICIANS Response Body (error): {text_response[:500]}")
                return []
    except Exception as e:
        print(f"[OPUS] Exception fetching clinicians: {e}")
        return []


async def get_clinic_timeslots(
    business_id: str, 
    treatment_id: int, 
    starting_from: Optional[str] = None,
    clinic_id: Optional[str] = None,
    clinician_id: Optional[int] = None
) -> List[Dict]:
    """
    Fetch available timeslots for a specific treatment from Opus API.
    
    Args:
        business_id: The GUID business ID of the clinic
        treatment_id: The ID of the treatment to find slots for
        starting_from: ISO 8601 datetime string (e.g., "2025-01-09T08:00:00"). Defaults to current time.
        clinic_id: Optional clinic ID to filter by specific clinic
        clinician_id: Optional clinician ID to filter by specific dentist
        
    Returns:
        List of timeslot dictionaries sorted by start time, or empty list if error
        Each slot contains: id, start, end, clinicId, clinicianId, treatmentId
    """
    if not OPUS_BEARER_TOKEN:
        print("[OPUS] Warning: OPUS_BEARER_TOKEN not set in environment variables.")
        return []

    url = f"{OPUS_API_URL}/api/Opus/timeslots"
    
    # Default to current datetime if not provided
    if not starting_from:
        starting_from = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

    params = {
        "businessId": business_id,
        "treatmentId": str(treatment_id),
        "startingFromDateTime": starting_from,
        "useTestEnvironment": "true" if cfg.OPUS_USE_TEST_ENV else "false",
    }
    
    # Add optional filters
    if clinic_id:
        params["clinicId"] = clinic_id
    if clinician_id:
        params["clinicianId"] = str(clinician_id)
    
    headers = {
        "Authorization": f"Bearer {OPUS_BEARER_TOKEN}",
        "Content-Type": "application/json"
    }

    full_url = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    print("[OPUS API] ========== TIMESLOTS REQUEST ==========")
    print(f"[OPUS API] GET {full_url}")
    print(f"[OPUS API] Headers: Content-Type=application/json, Authorization=Bearer ***")
    print("[OPUS API] ========================================")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                text_response = await response.text()
                print(f"[OPUS API] TIMESLOTS Response Status: {response.status}")
                try:
                    data = json.loads(text_response) if text_response else []
                except json.JSONDecodeError:
                    data = []
                if response.status == 200:
                    slots = data if isinstance(data, list) else []
                    print(f"[OPUS API] TIMESLOTS Response Body: {len(slots)} slots")
                    if slots:
                        first = slots[0]
                        print(f"[OPUS API] First slot: start={first.get('start') or first.get('Start')}, clinicId={first.get('clinicId')}, clinicianId={first.get('clinicianId')}")
                    return slots
                print(f"[OPUS API] TIMESLOTS Response Body (error): {text_response[:500]}")
                return []
    except Exception as e:
        print(f"[OPUS] Exception fetching timeslots: {e}")
        return []


async def book_opus_appointment(
    business_id: str,
    clinic_id: str,
    treatment_id: str,
    clinician_id: str,
    start_time: str,
    end_time: str,
    personal_id_number: str,
    first_name: str,
    last_name: str,
    phone_number: str,
    email: Optional[str] = "",
    notes: Optional[str] = "Called via AI receptionist"
) -> Dict:
    """
    Book an appointment via Opus API (POST /api/opus/book).
    
    Args:
        business_id: The GUID business ID of the clinic
        clinic_id: Clinic ID from the selected timeslot
        treatment_id: Treatment ID (string)
        clinician_id: Clinician/dentist ID (string)
        start_time: ISO 8601 datetime (e.g., "2025-01-15T09:00:00")
        end_time: ISO 8601 datetime (e.g., "2025-01-15T10:00:00")
        personal_id_number: Customer's personal ID (personnummer)
        first_name: Customer's first name
        last_name: Customer's last name
        phone_number: Customer's phone number
        email: Optional email address
        notes: Optional booking notes
        
    Returns:
        Dict with success (bool), bookingId (if success), message (str)
        On error: {"success": False, "message": "..."}
    """
    if not OPUS_BEARER_TOKEN:
        print("[OPUS] Warning: OPUS_BEARER_TOKEN not set in environment variables.")
        return {"success": False, "message": "OPUS API token not configured"}

    url = f"{OPUS_API_URL}/api/Opus/book"

    params = {
        "useTestEnvironment": "true" if cfg.OPUS_USE_TEST_ENV else "false",
    }
    
    payload = {
        "businessId": business_id,
        "clinicId": clinic_id,
        "treatmentId": int(treatment_id),
        "clinicianId": int(clinician_id),
        "startTime": start_time,
        "endTime": end_time,
        "personalIdNumber": personal_id_number,
        "firstName": first_name,
        "lastName": last_name,
        "phoneNumber": phone_number,
        "email": email or "",
        "notes": notes or "Called via AI receptionist"
    }
    
    headers = {
        "Authorization": f"Bearer {OPUS_BEARER_TOKEN}",
        "Content-Type": "application/json"
    }

    print(f"[OPUS] Booking appointment for {first_name} {last_name} at {start_time}")

    # Print booking data for verification (API call commented out)
    print("[OPUS] ========== BOOKING DATA (API call disabled) ==========")
    print(f"[OPUS] URL: {url}")
    print(f"[OPUS] Params: {params}")
    print(f"[OPUS] Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print("[OPUS] ======================================================")

    # try:
    #     async with aiohttp.ClientSession() as session:
    #         async with session.post(url, params=params, json=payload, headers=headers) as response:
    #             response_text = await response.text()
    #             try:
    #                 response_json = json.loads(response_text) if response_text else {}
    #             except json.JSONDecodeError:
    #                 response_json = {}
    #
    #             if response.status == 200:
    #                 success = response_json.get("success", True)
    #                 booking_id = response_json.get("bookingId", "")
    #                 msg = response_json.get("message", "Appointment booked successfully")
    #                 print(f"[OPUS] Booking successful. bookingId: {booking_id}")
    #                 return {
    #                     "success": success,
    #                     "bookingId": booking_id,
    #                     "message": msg
    #                 }
    #             else:
    #                 error_msg = response_json.get("message", response_text) or f"HTTP {response.status}"
    #                 print(f"[OPUS] Booking failed. Status: {response.status}, Response: {response_text}")
    #                 return {
    #                     "success": False,
    #                     "message": error_msg
    #                 }
    # except Exception as e:
    #     print(f"[OPUS] Exception booking appointment: {e}")
    #     return {
    #         "success": False,
    #         "message": str(e)
    #     }

    # API disabled - return so caller knows data was printed for verification
    return {
        "success": False,
        "message": "API call disabled - booking data printed for verification (check console)"
    }
