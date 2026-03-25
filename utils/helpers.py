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
    """Extract phone number from room name format like _+4747788636_FccScBRpKxpE"""
    if room_name.startswith('_+'):
        parts = room_name.split('_')
        if len(parts) >= 2:
            return parts[1]  # Returns '+4747788636'
    return None


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
