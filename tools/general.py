from livekit.agents import function_tool, RunContext


class GeneralToolsMixin:
    """Mixin containing general-purpose tools (business info, history, language)."""

    @function_tool()
    async def get_business_info(self, ctx: RunContext) -> str:
        """
        Get business information like location, opening hours, services, prices, etc.
        Call this function when customer asks about the business details, services offered,
        location, opening hours, prices, or any other business-related information.
        """
        lang = self._language_code()
        
        if self.cached_business_info:
            if lang == "en":
                return f"Business Information:\n{self.cached_business_info}"
            else:
                return f"Bedriftsinformasjon:\n{self.cached_business_info}"
        
        if lang == "en":
            return "Business information is not available at the moment."
        return "Bedriftsinformasjon er ikke tilgjengelig for øyeblikket."

    @function_tool()
    async def sjekk_samtalehistorikk(self, context: RunContext) -> str:
        """Sjekker tidligere samtaler med denne kunden – bruk KUN hvis kunden refererer til tidligere kontakt"""
        if hasattr(self, 'conversation_history') and self.conversation_history:
            sorted_calls = sorted(self.conversation_history.items(), key=lambda x: x[0], reverse=True)
            if sorted_calls:
                last_call = sorted_calls[0]
                summary = last_call[1].get('Kort sammendrag', 'Ingen detaljer') 
                return f"MERK: Dette er fra en TIDLIGERE SAMTALE, ikke relatert til denne pågående samtalen. Siste samtale: {summary}"
        return "Ingen tidligere samtaler registrert"

    @function_tool()
    async def switch_language(self, context: RunContext, language: str) -> str:
        """Switch conversation language. Use 'en' for English or 'no' for Norwegian. ONLY call this when the user EXPLICITLY requests a language change (e.g., 'speak English', 'can you speak English', 'snakk norsk', 'kan du snakke norsk'). NEVER auto-detect or change language based on what language the user is speaking. After switching, you MUST immediately repeat your last message to the customer in the new language."""
        if not self.call_data:
            return self._get_text("language_switching_unavailable") or ("Language switching not available" if self._language_code() == "en" else "Språkbytte ikke tilgjengelig")
        
        old_language = self.call_data.language
        language = language.lower().strip()
        
        if language in ["en", "english", "engelsk"]:
            self.call_data.language = "en"
            if old_language == "no":
                return "Language switched to English. IMPORTANT: You MUST now immediately repeat your last message to the customer in English. After repeating it, continue all future responses in English."
            return "Language switched to English. Continue all future responses in English."
        elif language in ["no", "norwegian", "norsk"]:
            self.call_data.language = "no"
            if old_language == "en":
                return "Språk byttet til norsk. VIKTIG: Du MÅ nå umiddelbart gjenta din siste melding til kunden på norsk. Etter at du har gjentatt den, fortsett alle fremtidige svar på norsk."
            return "Språk byttet til norsk. Fortsett alle fremtidige svar på norsk."
        else:
            template = self._get_text("unknown_language")
            if template:
                return template.replace("{language}", language)
            return f"Unknown language: {language}. Use 'en' for English or 'no' for Norwegian."
