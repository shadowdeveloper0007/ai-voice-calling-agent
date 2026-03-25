import json
from typing import Dict, Any, Optional, List
from qdrant_client import AsyncQdrantClient, models

import config.constants as cfg

QDRANT_URL = cfg.QDRANT_URL
QDRANT_API_KEY = cfg.QDRANT_API_KEY
COLLECTION_NAME = cfg.QDRANT_COLLECTION_NAME

# Static FunctionToolsJson and WebhookConfigJson (not from Qdrant)
# STATIC_FUNCTION_TOOLS_JSON = [
#     {"name": "samle_personnummer_med_dtmf", "purpose": "Samle personnummer via DTMF", "parameters": []},
#     {"name": "samle_telefonnummer_med_dtmf", "purpose": "Samle telefonnummer via DTMF", "parameters": []},
#     {"name": "sett_booking_preference", "purpose": "Sett bookingpreferanse (første ledige vs spesifikk dato)", "parameters": ["preference"]},
#     {"name": "sjekk_forste_ledige_time", "purpose": "Hent første ledige time", "parameters": ["personnr", "kundeMelding"]},
#     {"name": "sjekk_onsket_time", "purpose": "Sjekk ledighet på ønsket dato", "parameters": ["personnr", "kundeMelding", "OnsketDato"]},
#     {"name": "book_time", "purpose": "Book tid", "parameters": ["personnr", "Fornavn", "Etternavn", "mobilnr", "BusinessIDForValgtTime", "TreatmentIDForValgtTime", "ClinicianIDForValgtTime", "StartTid", "SluttTid", "Dato"]},
#     {"name": "get_client_detail", "purpose": "Hent kundens bookingdetaljer", "parameters": ["personnr"]},
#     {"name": "cancel_booking", "purpose": "Avlys booking", "parameters": ["ssn", "start_time", "end_time", "business_id", "treatment_id", "clinician_id", "confirm"]},
#     {"name": "update_appointment_date", "purpose": "Oppdater bookingdato", "parameters": ["ssn", "old_start_time", "old_end_time", "old_date", "old_business_id", "old_treatment_id", "old_clinician_id", "new_start_time", "new_end_time", "new_date", "new_business_id", "new_treatment_id", "new_clinician_id", "confirm"]},
#     {"name": "legg_igjen_beskjed", "purpose": "Registrer beskjed", "parameters": ["sammendrag", "telefonnummer", "Fornavn", "Etternavn"]}
# ]

# STATIC_WEBHOOK_CONFIG_JSON = {
#     "check_first_availability": "https://n8n.csdevhub.com/webhook/stage/check_first_availability",
#     "check_desired_date": "https://n8n.csdevhub.com/webhook/stage/check_desired_date",
#     "book_time": "https://n8n.csdevhub.com/webhook/stage/book_time",
#     "leave_message": "https://n8n.csdevhub.com/webhook/stage/leave_message",
#     "get_client_detail": "https://n8n.csdevhub.com/webhook/stage/get_client_detail",
#     "cancel_booking": "https://n8n.csdevhub.com/webhook/stage/cancel_booking",
#     "update_appointment_date": "https://n8n.csdevhub.com/webhook/stage/update_appointment_date"
# }


async def initialize_qdrant_client() -> Optional[AsyncQdrantClient]:
    """Initialize Qdrant client if credentials are available."""
    if not QDRANT_URL or not QDRANT_API_KEY:
        return None
        
    try:
        client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        await client.get_collections()
        return client
    except Exception as e:
        print(f"Warning: Failed to initialize Qdrant client: {e}")
        return None


async def ensure_indexes(client: AsyncQdrantClient, collection_name: str):
    """Ensure required indexes exist for filtering."""
    required_indexes = {
        "kind": models.PayloadSchemaType.KEYWORD,
        "phone_number": models.PayloadSchemaType.KEYWORD,
        "PhoneNumber": models.PayloadSchemaType.KEYWORD,
        "BusinessId": models.PayloadSchemaType.KEYWORD,
        "BusinessCategoryId": models.PayloadSchemaType.INTEGER,
    }

    try:
        collection_info = await client.get_collection(collection_name)
        existing_indexes = collection_info.payload_schema or {}

        for field_name, schema in required_indexes.items():
            if field_name in existing_indexes:
                continue

            await client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema,
                wait=True,
            )
    except Exception:
        pass


async def _query_business_records(
    client: AsyncQdrantClient,
    kind: str,
    identifier_key: str,
    identifier_value: str
) -> List:
    """
    Generic query helper for business records.
    
    Args:
        client: Qdrant client
        kind: Record kind (e.g., 'business_details', 'business_prompt_chunk', 'website_knowledge_chunk')
        identifier_key: Field name to filter by (e.g., 'PhoneNumber', 'BusinessId')
        identifier_value: Value to match
    
    Returns:
        List of matching records
    """
    if not identifier_value:
        return []
    
    search_filter = models.Filter(
        must=[
            models.FieldCondition(key="kind", match=models.MatchValue(value=kind)),
            models.FieldCondition(key=identifier_key, match=models.MatchValue(value=identifier_value)),
        ]
    )

    all_points = []
    offset = None

    while True:
        points, next_offset = await client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=search_filter,
            limit=1000,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        all_points.extend(points)

        if next_offset is None or len(points) == 0:
            break

        offset = next_offset

    return all_points


async def _query_agent_data_chunk(
    client: AsyncQdrantClient, 
    phone_number: str
) -> List:
    """Query agent_data_chunk records by phone_number (legacy approach)."""
    normalized_phone = phone_number.strip().lstrip('+')
    
    search_filter = models.Filter(
        must=[
            models.FieldCondition(key="kind", match=models.MatchValue(value="agent_data_chunk")),
            models.Filter(
                should=[
                    models.FieldCondition(
                        key="phone_number", 
                        match=models.MatchValue(value=phone_number)
                    ),
                    models.FieldCondition(
                        key="phone_number", 
                        match=models.MatchValue(value=normalized_phone)
                    ),
                    models.FieldCondition(
                        key="PhoneNumber", 
                        match=models.MatchValue(value=phone_number)
                    ),
                    models.FieldCondition(
                        key="PhoneNumber", 
                        match=models.MatchValue(value=normalized_phone)
                    ),
                ]
            ),
        ]
    )

    all_points = []
    offset = None

    while True:
        points, next_offset = await client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=search_filter,
            limit=1000,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        all_points.extend(points)

        if next_offset is None or len(points) == 0:
            break

        offset = next_offset

    return all_points


async def _query_website_knowledge_chunk(
    client: AsyncQdrantClient, 
    business_id: str
) -> List:
    """Query website_knowledge_chunk records by BusinessId."""
    records = await _query_business_records(
        client=client,
        kind="website_knowledge_chunk",
        identifier_key="BusinessId",
        identifier_value=business_id
    )
    
    if records:
        print("\n[INNSTILLINGER] ========== website_knowledge_chunk (kind: website_knowledge_chunk) ==========")
        print(f"[INNSTILLINGER] Total records found: {len(records)}")
        for idx, record in enumerate(records, 1):
            print(f"[INNSTILLINGER] --- Record {idx} ---")
            print(f"[INNSTILLINGER] {json.dumps(record.payload.get("content"), indent=2, ensure_ascii=False)}")
        print("[INNSTILLINGER] =============================================================================\n")
    
    return records


async def fetch_website_knowledge_by_business_id(business_id: str) -> str:
    """Fetch all website_knowledge_chunk records by BusinessId and combine their content."""
    if not business_id:
        return ""
    
    client = await initialize_qdrant_client()
    if not client:
        return ""
    
    try:
        await ensure_indexes(client, COLLECTION_NAME)
        records = await _query_website_knowledge_chunk(client, business_id)
        
        if not records:
            return ""
        
        # Combine all content fields
        content_parts = []
        for record in records:
            payload = record.payload
            content = payload.get('content', '').strip()
            
            if content:
                # Optional: Add metadata for better context
                page_title = payload.get('PageTitle', '')
                section_title = payload.get('SectionTitle', '')
                
                if page_title or section_title:
                    content_with_context = f"{page_title} - {section_title}: {content}" if page_title and section_title else \
                                         f"{page_title}: {content}" if page_title else \
                                         f"{section_title}: {content}" if section_title else content
                    content_parts.append(content_with_context)
                else:
                    content_parts.append(content)
        
        return "\n\n".join(content_parts)
        
    except Exception:
        return ""
    finally:
        if client:
            await client.close()


async def fetch_business_settings_by_phone(phone_number: str) -> Dict[str, Any]:
    """
    Fetch clinic settings by phone number from Qdrant.
    Uses agent_data_chunk for settings and website_knowledge_chunk for business info.
    """
    if not phone_number:
        raise ValueError("Phone number is required to fetch business settings.")
    
    client = await initialize_qdrant_client()
    if not client:
        raise RuntimeError("Failed to initialize Qdrant client. Check QDRANT_URL and QDRANT_API_KEY environment variables.")
    
    try:
        await ensure_indexes(client, COLLECTION_NAME)
        
        # Fetch agent_data_chunk by phone number
        records = await _query_agent_data_chunk(client, phone_number)
        
        if not records:
            raise ValueError(f"No business data found with phone number: {phone_number}")
        
        record = records[0]
        payload = record.payload if record else {}
        
        print("\n[INNSTILLINGER] ========== agent_data_chunk (kind: agent_data_chunk) ==========")
        print(f"[INNSTILLINGER] Full data: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        print("[INNSTILLINGER] ================================================================\n")
        
        business_id = payload.get("BusinessId") or payload.get("business_id") or ""
        business_name = payload.get("business_name") or payload.get("Name") or ""
        agent_name = payload.get("agent_navn") or ""
        active_persona = payload.get("active_persona") or payload.get("PersonaName") or ""
        prompt = payload.get("prompt") or ""
        
        # Use static FunctionToolsJson instead of parsing from Qdrant
        # function_tools = STATIC_FUNCTION_TOOLS_JSON.copy()
        
        # Use static WebhookConfigJson instead of parsing from Qdrant
        # webhook_urls = STATIC_WEBHOOK_CONFIG_JSON.copy()
        
        param_mapping: Dict[str, str] = {}
        
        param_mapping_json_str = payload.get('ParameterMappingJson')
        if param_mapping_json_str:
            try:
                if isinstance(param_mapping_json_str, str):
                    param_mapping = json.loads(param_mapping_json_str) if param_mapping_json_str.strip() else {}
                else:
                    param_mapping = param_mapping_json_str if isinstance(param_mapping_json_str, dict) else {}
            except (json.JSONDecodeError, TypeError):
                param_mapping = {}
        
        voice_data = payload.get('voice', {})
        if isinstance(voice_data, str):
            try:
                voice_data = json.loads(voice_data) if voice_data.strip() else {}
            except (json.JSONDecodeError, TypeError):
                voice_data = {}
        elif not isinstance(voice_data, dict):
            voice_data = {}
        
        # Fetch website knowledge chunks
        website_knowledge = ""
        if business_id:
            website_knowledge = await fetch_website_knowledge_by_business_id(business_id)
        
        result = {
            "business_id": business_id or "",
            "business_name": business_name or "",
            "business_category_id": payload.get("BusinessCategoryId"),
            "business_type": payload.get("business_type") or "business",
            "phone_number": phone_number,
            "agent_navn": agent_name or "",
            "active_persona": active_persona or "",
            "ekstern_behandler": payload.get("ekstern_behandler") or "+4791534220",
            "enable_conversation_history": payload.get("EnableConversationHistory") if payload.get("EnableConversationHistory") is not None else True,
            "booking_term": payload.get("BookingTerm") or "booking",
            "prompt": prompt or "",
            # "function_tools": function_tools or [],
            "business_info": website_knowledge or "",
            # "webhook_urls": webhook_urls or {},
        }
        
        result["llm_model"] = payload.get("llm_model") or ""
        result["llm_provider"] = payload.get("llm_provider") or "openai"
        result["llm_temperature"] = payload.get("llm_temperature") if payload.get("llm_temperature") is not None else 0.4
        
        result["stt_model"] = payload.get("stt_model") or ""
        result["stt_provider"] = payload.get("stt_provider") or ""
        result["stt_prompt"] = payload.get("stt_prompt") or ""
        
        result["tts_provider"] = payload.get("tts_provider") or ""
        result["tts_model"] = payload.get("tts_model") or ""
        
        voice_id_value = ""
        if isinstance(voice_data, dict):
            voice_id_value = voice_data.get("id") or ""
        else:
            voice_id_value = payload.get("voice_id") or ""
        
        result["voice"] = {
            "id": voice_id_value,
            "stability": voice_data.get("stability") if isinstance(voice_data, dict) and voice_data.get("stability") is not None else 0.5,
            "similarity_boost": voice_data.get("similarity_boost") if isinstance(voice_data, dict) and voice_data.get("similarity_boost") is not None else 0.75,
            "speed": voice_data.get("speed") if isinstance(voice_data, dict) and voice_data.get("speed") is not None else 1.0
        }
        
        result["vad_model"] = payload.get("vad_model") or ""
        result["turn_detection_model"] = payload.get("turn_detection_model") or ""
        
        return result
        
    except Exception as e:
        raise RuntimeError(f"Error fetching business settings: {e}")
    finally:
        if client:
            await client.close()