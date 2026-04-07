import aiohttp
import json
from typing import List, Dict, Optional
from datetime import datetime

import config.constants as cfg

OPUS_API_URL = cfg.OPUS_API_URL
OPUS_BEARER_TOKEN = cfg.OPUS_BEARER_TOKEN

async def get_patient_bookings(
    *,
    business_id: str,
    pid: str,
    use_test_environment: Optional[bool] = None,
) -> List[Dict]:
    """
    Fetch bookings for a patient.
    GET /api/Opus/patients/{pid}/bookings?businessId=<guid>&useTestEnvironment=false
    """
    if not OPUS_BEARER_TOKEN:
        print("[OPUS] Warning: OPUS_BEARER_TOKEN not set.")
        return []
    if not business_id or not pid:
        return []

    use_test = use_test_environment if use_test_environment is not None else cfg.OPUS_USE_TEST_ENV
    url = f"{OPUS_API_URL}/api/Opus/patients/{pid}/bookings"
    params = {
        "businessId": business_id,
        "useTestEnvironment": "true" if use_test else "false",
    }
    headers = {
        "Authorization": f"Bearer {OPUS_BEARER_TOKEN}",
        "Accept": "application/json",
    }

    full_url = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    print("[OPUS API] ========== PATIENT BOOKINGS REQUEST ==========")
    print(f"[OPUS API] GET {full_url}")
    print(f"[OPUS API] Headers: Accept=application/json, Authorization=Bearer ***")
    print("[OPUS API] =============================================")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                text_response = await response.text()
                print(f"[OPUS API] PATIENT BOOKINGS Response Status: {response.status}")
                if response.status != 200:
                    print(f"[OPUS API] PATIENT BOOKINGS Error: {text_response[:500]}")
                    return []
                try:
                    data = json.loads(text_response) if text_response else []
                except json.JSONDecodeError:
                    return []

                # Response may be list or wrapped object.
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    maybe = data.get("bookings") or data.get("data") or data.get("items")
                    if isinstance(maybe, list):
                        return maybe
                return []
    except Exception as e:
        print(f"[OPUS] Exception in get_patient_bookings: {e}")
        return []


async def cancel_booking_opus(
    *,
    business_id: str,
    booking_id: str,
    pid: str,
    use_test_environment: Optional[bool] = None,
) -> Dict:
    """
    Cancel a booking via OPUS.
    Endpoint: /api/Opus/bookings/cancel?businessId=...&bookingId=...&pid=...&useTestEnvironment=false
    """
    if not OPUS_BEARER_TOKEN:
        print("[OPUS] Warning: OPUS_BEARER_TOKEN not set.")
        return {"success": False, "message": "OPUS API token not configured"}
    if not business_id or not booking_id or not pid:
        return {"success": False, "message": "Missing required cancel parameters"}

    use_test = use_test_environment if use_test_environment is not None else cfg.OPUS_USE_TEST_ENV
    url = f"{OPUS_API_URL}/api/Opus/bookings/cancel"
    params = {
        "businessId": business_id,
        "bookingId": booking_id,
        "pid": pid,
        "useTestEnvironment": "true" if use_test else "false",
    }
    headers = {
        "Authorization": f"Bearer {OPUS_BEARER_TOKEN}",
        "Accept": "application/json",
    }

    full_url = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    print("[OPUS API] ========== CANCEL BOOKING REQUEST ==========")
    print(f"[OPUS API] POST {full_url}")
    print(f"[OPUS API] Headers: Accept=application/json, Authorization=Bearer ***")
    print("[OPUS API] ===========================================")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params, headers=headers) as response:
                text_response = await response.text()
                print(f"[OPUS API] CANCEL BOOKING Response Status: {response.status}")
                try:
                    data = json.loads(text_response) if text_response else {}
                except json.JSONDecodeError:
                    data = {}

                if response.status == 200:
                    return {"success": True, "message": data.get("message") or "Booking cancelled", "data": data}

                err = data.get("message", text_response) or f"HTTP {response.status}"
                print(f"[OPUS] Cancel booking failed. Status: {response.status}, Response: {text_response[:500]}")
                return {"success": False, "message": err, "data": data}
    except Exception as e:
        print(f"[OPUS] Exception in cancel_booking_opus: {e}")
        return {"success": False, "message": str(e)}

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


async def find_patient_slot(
    business_id: str,
    pid: str,
    treatment_name: str,
    preferred_date: Optional[str] = None
) -> List[Dict]:
    """
    Find available slot(s) for a patient via POST /api/Opus/patient/find-slot.

    Response may be a single object or an array. Each item has a 'found' bool.
    Found slots get backward-compatible aliases (start/end/Start/End) added.

    Returns:
        List of slot dicts (including not-found items so callers can read 'reason').
    """
    if not OPUS_BEARER_TOKEN:
        print("[OPUS] Warning: OPUS_BEARER_TOKEN not set.")
        return []

    url = f"{OPUS_API_URL}/api/Opus/patient/find-slot"
    params = {
        "useTestEnvironment": "true" if cfg.OPUS_USE_TEST_ENV else "false",
    }

    if not preferred_date:
        preferred_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    elif not preferred_date.endswith("Z"):
        preferred_date = preferred_date + ".000Z"

    payload = {
        "businessId": business_id,
        "pid": pid,
        "treatmentName": treatment_name,
        "preferredDate": preferred_date,
    }

    headers = {
        "Authorization": f"Bearer {OPUS_BEARER_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    print("[OPUS API] ========== FIND-SLOT REQUEST ==========")
    print(f"[OPUS API] POST {url}?useTestEnvironment={params['useTestEnvironment']}")
    print(f"[OPUS API] Payload: {json.dumps(payload, ensure_ascii=False)}")
    print("[OPUS API] =========================================")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params, json=payload, headers=headers) as response:
                text_response = await response.text()
                print(f"[OPUS API] FIND-SLOT Response Status: {response.status}")

                if response.status != 200:
                    print(f"[OPUS API] FIND-SLOT Error: {text_response[:500]}")
                    return []

                try:
                    data = json.loads(text_response) if text_response else {}
                except json.JSONDecodeError:
                    print("[OPUS API] FIND-SLOT JSON decode error")
                    return []

                slots_raw = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])

                result = []
                for slot in slots_raw:
                    if slot.get("found", False):
                        slot["start"] = slot.get("slotStart", "")
                        slot["end"] = slot.get("slotEnd", "")
                        slot["Start"] = slot.get("slotStart", "")
                        slot["End"] = slot.get("slotEnd", "")
                    result.append(slot)

                found_count = sum(1 for s in result if s.get("found"))
                print(f"[OPUS API] FIND-SLOT: {found_count} available slot(s) out of {len(result)} returned")
                if found_count:
                    first = next(s for s in result if s.get("found"))
                    print(f"[OPUS API] First slot: {first.get('slotStart')} - {first.get('slotEnd')}, clinician={first.get('clinicianName')}")

                return result
    except Exception as e:
        print(f"[OPUS] Exception in find_patient_slot: {e}")
        return []


async def book_existing_patient(
    business_id: str,
    pid: str,
    treatment_id: int,
    clinician_id: int,
    slot_start: str,
    slot_end: str,
) -> Dict:
    """
    Book for an existing patient: POST /api/Opus/existing-patient/book
    """
    if not OPUS_BEARER_TOKEN:
        print("[OPUS] Warning: OPUS_BEARER_TOKEN not set.")
        return {"success": False, "message": "OPUS API token not configured"}

    url = f"{OPUS_API_URL}/api/Opus/existing-patient/book"
    params = {"useTestEnvironment": "true" if cfg.OPUS_USE_TEST_ENV else "false"}

    payload = {
        "businessId": business_id,
        "pid": pid,
        "treatmentId": int(treatment_id),
        "clinicianId": int(clinician_id),
        "slotStart": slot_start,
        "slotEnd": slot_end,
    }

    headers = {
        "Authorization": f"Bearer {OPUS_BEARER_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    print("[OPUS API] ========== EXISTING-PATIENT BOOK ==========")
    print(f"[OPUS API] POST {url}")
    print(f"[OPUS API] Payload: {json.dumps(payload, ensure_ascii=False)}")
    print("[OPUS API] ==========================================")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params, json=payload, headers=headers) as response:
                text_response = await response.text()
                print(f"[OPUS API] EXISTING-PATIENT BOOK Response Status: {response.status}")
                try:
                    response_json = json.loads(text_response) if text_response else {}
                except json.JSONDecodeError:
                    response_json = {}

                if response.status == 200:
                    print(f"[OPUS] Existing-patient booking successful: {text_response[:300]}")
                    return {
                        "success": True,
                        "bookingId": response_json.get("bookingId", ""),
                        "message": response_json.get("message", "Appointment booked successfully"),
                        "data": response_json,
                    }
                else:
                    error_msg = response_json.get("message", text_response) or f"HTTP {response.status}"
                    print(f"[OPUS] Existing-patient booking failed. Status: {response.status}, Response: {text_response[:500]}")
                    return {"success": False, "message": error_msg}
    except Exception as e:
        print(f"[OPUS] Exception in book_existing_patient: {e}")
        return {"success": False, "message": str(e)}


async def book_new_patient(
    business_id: str,
    pid: str,
    first_name: str,
    last_name: str,
    phone: str,
    email: str,
    treatment_id: int,
    clinician_id: int,
    slot_start: str,
    slot_end: str,
) -> Dict:
    """
    Book for a new patient: POST /api/Opus/new-patient/book
    """
    if not OPUS_BEARER_TOKEN:
        print("[OPUS] Warning: OPUS_BEARER_TOKEN not set.")
        return {"success": False, "message": "OPUS API token not configured"}

    url = f"{OPUS_API_URL}/api/Opus/new-patient/book"
    params = {"useTestEnvironment": "true" if cfg.OPUS_USE_TEST_ENV else "false"}

    payload = {
        "businessId": business_id,
        "pid": pid,
        "firstName": first_name,
        "lastName": last_name,
        "mobilePhoneNumber": phone,
        "email": email or "",
        "treatmentId": int(treatment_id),
        "clinicianId": int(clinician_id),
        "slotStart": slot_start,
        "slotEnd": slot_end,
    }

    headers = {
        "Authorization": f"Bearer {OPUS_BEARER_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    print("[OPUS API] ========== NEW-PATIENT BOOK ==========")
    print(f"[OPUS API] POST {url}")
    print(f"[OPUS API] Payload: {json.dumps(payload, ensure_ascii=False)}")
    print("[OPUS API] =======================================")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params, json=payload, headers=headers) as response:
                text_response = await response.text()
                print(f"[OPUS API] NEW-PATIENT BOOK Response Status: {response.status}")
                try:
                    response_json = json.loads(text_response) if text_response else {}
                except json.JSONDecodeError:
                    response_json = {}

                if response.status == 200:
                    print(f"[OPUS] New-patient booking successful: {text_response[:300]}")
                    return {
                        "success": True,
                        "bookingId": response_json.get("bookingId", ""),
                        "message": response_json.get("message", "Appointment booked successfully"),
                        "data": response_json,
                    }
                else:
                    error_msg = response_json.get("message", text_response) or f"HTTP {response.status}"
                    print(f"[OPUS] New-patient booking failed. Status: {response.status}, Response: {text_response[:500]}")
                    return {"success": False, "message": error_msg}
    except Exception as e:
        print(f"[OPUS] Exception in book_new_patient: {e}")
        return {"success": False, "message": str(e)}
