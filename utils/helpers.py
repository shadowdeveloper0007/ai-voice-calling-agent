import re
from typing import Optional


async def generate_conversation_summary(call_data) -> str:
    """Genererer et sammendrag av samtalen ved hjelp av LLM"""
    try:
        if not call_data.conversation_messages:
            return "Ingen samtale registrert."
        
        # Build conversation text from stored messages
        conversation_text = "\n".join([
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in call_data.conversation_messages[-20:]
        ])
        
        # Import what we need
        from livekit.plugins import openai
        from livekit.agents.llm import ChatContext, ChatMessage
        
        # Create a simple LLM instance to generate the summary
        llm = openai.LLM(model="gpt-4o-mini", temperature=0.6)
        
        # Create chat context
        chat_ctx = ChatContext([
            ChatMessage(
                role="system",
                content=["Du er en AI som lager korte sammendrag av tannklinikk-samtaler. VIKTIG: Aldri inkluder personnummer, navn eller telefonnummer."]
            ),
            ChatMessage(
                role="user", 
                content=[f"Lag et kort sammendrag (1-2 setninger) av denne samtalen. Fokuser på hva kunden spurte om:\n\n{conversation_text}"]
            )
        ])
        
        # Generate summary using chat
        response = ""
        async with llm.chat(chat_ctx=chat_ctx) as stream:
            async for chunk in stream:
                if not chunk:
                    continue
                content = getattr(chunk.delta, 'content', None) if hasattr(chunk, 'delta') else str(chunk)
                if content:
                    response += content
        
        summary = response.strip()
        return summary
        
    except Exception as e:
        return "Kunne ikke generere sammendrag av samtalen."


def extract_phone_from_room_name(room_name: str) -> Optional[str]:
    """Legacy wrapper — returns agent_number for backward compat."""
    parsed = parse_room_name(room_name)
    return parsed.get("agent_number")


def parse_room_name(room_name: str) -> dict:
    """
    Parse a LiveKit room name into business_id, agent_number, and user_number.

    Supported format (new):
      ``bid=<uuid>-an=<digits>_<user_phone>_<suffix>``
      e.g. ``bid=9ebf79ad-ff71-4205-8988-08ddfe66e5a9-an=4723507256_+37066187886_FccScBRpKxpE``

    Legacy format:
      ``_+4747788636_FccScBRpKxpE``  (only agent number)

    Returns dict with keys: business_id, agent_number, user_number (all Optional[str]).
    """
    result: dict = {"business_id": None, "agent_number": None, "user_number": None}
    if not room_name:
        return result

    try:
        parts = room_name.split("_")
        prefix = parts[0] if parts else ""

        # user_number is always the second underscore-separated segment
        user_number = parts[1] if len(parts) > 1 else None
        if user_number:
            user_number = user_number.strip()
            if user_number and not user_number.startswith("+"):
                user_number = f"+{user_number}"
            result["user_number"] = user_number

        # business_id: bid=<uuid>
        bid_match = re.search(
            r"bid=([a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})",
            prefix,
        )
        if bid_match:
            result["business_id"] = bid_match.group(1)

        # agent_number: an=<digits>
        an_match = re.search(r"an=(\+?[\d]+)", prefix)
        if an_match:
            n = an_match.group(1)
            result["agent_number"] = n if n.startswith("+") else f"+{n}"

        # Legacy fallback: `_+47..._...`
        if not result["agent_number"] and room_name.startswith("_+") and len(parts) >= 2:
            result["agent_number"] = parts[1]
            result["user_number"] = None  # legacy has no separate user number

        # Legacy fallback: `biz-...-num-<digits>_...`
        if not result["agent_number"]:
            m = re.search(r"(?:^|-)num-(\+?\d{8,15})", prefix)
            if m:
                n = m.group(1)
                result["agent_number"] = n if n.startswith("+") else f"+{n}"

        print(f"[ROOM PARSE] room_name={room_name!r} -> {result}")
    except Exception as e:
        print(f"[ROOM PARSE] Could not parse room name: {e}")

    return result


# --- Commented-out Qdrant conversation logging functions ---
# async def load_conversation_history(phone_number: str, clinic_name: str) -> Optional[Dict[str, Any]]:
#     """Load previous conversations for a phone number"""
#     if not phone_number or not qdrant_client:
#         return None
        
#     try:
#         collection_name = f"{clinic_name.replace(' ', '_')}_samtalelogg"
#         phone_id = int(''.join(filter(str.isdigit, phone_number)))
        
#         results = await qdrant_client.retrieve(
#             collection_name=collection_name,
#             ids=[phone_id],
#             with_payload=True
#         )
        
#         if results:
#             payload = results[0].payload.get(phone_number, {})
            
#             return payload
            
#     except Exception as e:
#         print("[ENTRYPOINT] Exception loading conversation history" + str(e))
#         return None
    
#     return None


# def format_conversation_history(history: Dict[str, Any]) -> str:
#     """Format conversation history into natural language context"""
#     if not history:
#         return ""
    
#     sorted_calls = sorted(history.items(), key=lambda x: x[0], reverse=True)
    
#     context_parts = []
#     context_parts.append("VIKTIG INFORMASJON: Du har følgende historikk fra tidligere samtaler med denne kunden som ringer inn nå.")
#     context_parts.append("Dette er sammendrag av tidligere samtaler, IKKE den pågående samtalen:")
#     context_parts.append("")
    
#     for timestamp_key, call_data in sorted_calls:
#         date_str = timestamp_key[:10]
#         time_str = timestamp_key[11:].replace('-', ':')
        
#         summary = call_data.get('Kort sammendrag', 'Ingen sammendrag')
#         booked = "Ja" if call_data.get('Time booket?') else "Nei"
        
#         context_parts.append(
#             f"- {date_str} kl {time_str}: {summary} (Time booket: {booked})"
#         )
    
#     context_parts.append("\nBruk denne informasjonen til å gi personlig og tilpasset service til kunden.")
#     return "\n".join(context_parts)


# async def save_call_log(call_data, clinic_name: str):
#     """Save call log to Qdrant using ID-based storage without requiring embeddings"""
#     try:
#         if not call_data.phone_number or not qdrant_client:
#             return
            
#         summary = await generate_conversation_summary(call_data)
        
#         call_end_time = datetime.now(timezone.utc)
#         timestamp_key = call_data.call_start_time.strftime("%Y-%m-%d-%H-%M-%S")
        
#         call_log_entry = {
#             "Kort sammendrag": summary,
#             "Samtale start": call_data.call_start_time.isoformat(),
#             "Samtale slutt": call_end_time.isoformat(),
#             "Time booket?": call_data.appointment_booked
#         }
        
#         collection_name = f"{clinic_name.replace(' ', '_')}_samtalelogg"
#         print(f"[ENTRYPOINT] save_call_log: Collection name: {collection_name}")
#         vector_size = 4
#         try:
#             collection_info = await qdrant_client.get_collection(collection_name)
#             vector_size = collection_info.config.params.vectors.size
#         except:
#             await qdrant_client.create_collection(
#                 collection_name=collection_name,
#                 vectors_config=models.VectorParams(
#                     size=vector_size,
#                     distance=models.Distance.COSINE
#                 )
#             )
        
#         phone_id = int(''.join(filter(str.isdigit, call_data.phone_number)))
        
#         existing_logs = {}
#         try:
#             result = await qdrant_client.retrieve(
#                 collection_name=collection_name,
#                 ids=[phone_id]
#             )
#             if result:
#                 existing_logs = result[0].payload.get(call_data.phone_number, {})
#         except:
#             pass
        
#         existing_logs[timestamp_key] = call_log_entry
#         payload = {call_data.phone_number: existing_logs}
        
#         if vector_size == 1024:
#             dummy_vector = [0.0] * 1024
#         else:
#             dummy_vector = [0.0] * (vector_size - 1) + [1.0]
        
#         await qdrant_client.upsert(
#             collection_name=collection_name,
#             points=[
#                 models.PointStruct(
#                     id=phone_id,
#                     vector=dummy_vector,
#                     payload=payload
#                 )
#             ]
#         )
        
#     except Exception as e:
#         pass
