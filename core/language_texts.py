LANGUAGE_TEXTS = {
    "first_slot_intro": {
        "no": "la meg finne den første ledige timen vi har tilgjengelig for deg...",
        "en": "Let me find the earliest available appointment we have for you..."
    },
    "first_slot_updates": {
        "no": [
            "Et lite øyeblikk, jeg søker etter første ledige time...",
            "Vi søker fortsatt...",
            "Takk for din tålmodighet...",
            "Jeg sjekker flere alternativer for deg...",
            "Bare et øyeblikk til...",
            "Fortsetter å lete etter beste tidspunkt...",
            "Snart ferdig med søket...",
        ],
        "en": [
            "One moment, I'm searching for the earliest available slot...",
            "Still looking...",
            "Thank you for your patience...",
            "I'm reviewing a few options for you...",
            "Just a moment more...",
            "Continuing to look for the best time...",
            "Almost finished with the search...",
        ]
    },
    "desired_slot_intro": {
        "no": "la meg sjekke tilgjengeligheten vår...",
        "en": "Let me check our availability..."
    },
    "desired_slot_updates": {
        "no": [
            "Et øyeblikk, jeg søker etter ledig time for deg...",
            "Vi søker fortsatt...",
            "Takk for at du venter...",
            "Ser etter ledige tidspunkter...",
            "Bare litt til, snart ferdig...",
            "Går gjennom mulighetene...",
            "Nesten fremme med resultatet...",
        ],
        "en": [
            "One moment, I'm checking for available times on that date...",
            "Still searching...",
            "Thank you for waiting...",
            "Looking through the available options...",
            "Just a little longer...",
            "Reviewing the possibilities...",
            "Almost ready with the result...",
        ]
    },
    "booking_intro": {
        "no": "Flott, la meg booke den timen for deg med en gang...",
        "en": "Great, let me book that appointment for you right away..."
    },
    "booking_updates": {
        "no": [
            "Bare et øyeblikk, jeg registrerer timen din...",
            "Jobber med bookingen...",
            "Takk for tålmodigheten...",
            "Snart ferdig med registreringen...",
            "Fullfører bookingen nå...",
            "Siste detaljer...",
            "Nesten klar...",
        ],
        "en": [
            "One moment, I'm recording your appointment...",
            "Working on the booking...",
            "Thanks for your patience...",
            "Almost done with the registration...",
            "Finishing the booking now...",
            "Final details...",
            "Almost ready...",
        ]
    },
    "leave_message_intro": {
        "no": "La meg legge igjen en beskjed til våre ansatte så de kan kontakte deg.",
        "en": "Let me leave a message so our staff can contact you."
    },
    "leave_message_updates": {
        "no": [
            "Sender beskjeden til teamet ditt nå...",
            "Sørger for at alle detaljene blir med...",
            "Bekrefter at beskjeden kommer frem...",
            "Takk for tålmodigheten, fullfører utsendingen...",
            "Snart ferdig – beskjeden er på vei..."
        ],
        "en": [
            "Sending your message to the team now...",
            "Making sure every detail is included...",
            "Confirming that the message is delivered...",
            "Thanks for waiting, wrapping up the send...",
            "Almost done – your message is on its way..."
        ]
    },
    "leave_message_capture_prompt": {
        "no": "Hva vil du at jeg skal videreformidle? Si beskjeden din etter tonen, så noterer jeg alt.",
        "en": "What would you like me to pass along? Please tell me the message and I'll write everything down."
    },
    "leave_message_capture_confirm": {
        "no": "Takk, jeg har notert beskjeden.",
        "en": "Thanks, I've written down your message."
    },
    "leave_message_capture_timeout": {
        "no": "Jeg fikk ikke med meg noen beskjed. Jeg sender likevel en forespørsel om at du blir kontaktet.",
        "en": "I didn't catch a message, but I'll still ask the team to reach out to you."
    },
    "leave_message_name_prompt": {
        "no": "Kan jeg få navnet ditt?",
        "en": "May I have your name?"
    },
    "leave_message_name_retry": {
        "no": "Jeg fikk ikke helt med meg navnet. Kan du si det én gang til?",
        "en": "I didn't quite catch that name. Could you repeat it for me?"
    },
    "leave_message_name_confirm": {
        "no": "Takk, {name}.",
        "en": "Thank you, {name}."
    },
    "first_slot_success": {
        "no": "Første ledige time ble funnet.",
        "en": "The earliest available appointment was found."
    },
    "first_slot_prompt": {
        "no": " Presenter denne tiden for kunden og spør om den passer før du fortsetter.",
        "en": " Please share this time with the customer and ask if it works before moving forward."
    },
    "desired_slot_success": {
        "no": "Ledige timer ble funnet for ønsket tidsrom.",
        "en": "Available times were found for the requested period."
    },
    "desired_slot_prompt": {
        "no": " Presenter disse tidene for kunden og spør hvilken som passer best.",
        "en": " Please list these times for the customer and ask which one works best."
    },
    "personnummer_failed": {
        "no": "Kunde klarte ikke taste inn personnummer korrekt. Instruer kunden i hvordan korrekt bruke taster og prøv igjen, eller videresend til menneskelig behandler.",
        "en": "The customer could not enter their personal identification number correctly. Please guide them through the keypad process and try again, or transfer to a human agent."
    },
    "booking_success": {
        "no": "Time er nå booket for {name}.",
        "en": "The appointment is now booked for {name}."
    },
    "booking_failure": {
        "no": "Klarte ikke å booke timen i systemet.",
        "en": "Couldn't book the appointment in the system."
    },
    "leave_message_success": {
        "no": "Beskjeden er sendt til våre ansatte, og de følger den opp. Er det noe mer jeg kan hjelpe deg med?",
        "en": "Your message has been sent to our staff, and they will follow up. Is there anything else I can assist you with?"
    },
    "transfer_unavailable": {
        "no": "Beklager, kan ikke videresende akkurat nå. La meg ta en beskjed.",
        "en": "Sorry, I can't transfer you right now. Let me take a message instead."
    },
    "transfer_in_progress": {
        "no": "Setter deg over nå.",
        "en": "Transferring you now."
    },
    "transfer_failed": {
        "no": "Videresending feilet. La meg heller ta en beskjed.",
        "en": "Transfer failed. Let me take a message instead."
    },
    "booking_preference_missing_first": {
        "no": "Før du kan finne første ledige time må du avklare med kunden om de ønsker første ledige eller en spesifikk dato. Still spørsmålet og bruk sett_booking_preference før du kaller funksjonen igjen.",
        "en": "Before you can search for the earliest slot, confirm with the customer whether they want the first available or a specific date. Ask the question and use sett_booking_preference before calling this function again."
    },
    "booking_preference_missing_date": {
        "no": "Før du kan søke etter en ønsket dato må du avklare om kunden faktisk ønsker en spesifikk dato. Still spørsmålet og bruk sett_booking_preference før du kaller funksjonen igjen.",
        "en": "Before searching for a requested date, confirm that the customer truly wants a specific date. Ask the question and use sett_booking_preference before calling this function again."
    },
    "booking_preference_set_first": {
        "no": "Forstår. Jeg noterer at kunden ønsker første ledige time.",
        "en": "Understood. I'll note that the customer wants the first available appointment."
    },
    "booking_preference_set_date": {
        "no": "Forstår. Jeg noterer at kunden ønsker en spesifikk dato.",
        "en": "Understood. I'll note that the customer wants a specific date."
    },
    "booking_preference_set_unknown": {
        "no": "Notert. Jeg skal dobbeltsjekke preferansen med kunden.",
        "en": "Noted. I'll double-check the preference with the customer."
    },
    "booking_preference_invalid": {
        "no": "Ukjent preferanse. Bruk 'first_available', 'specific_date' eller 'unknown'.",
        "en": "Unknown preference. Use 'first_available', 'specific_date', or 'unknown'."
    },
    "no_availability_first": {
        "no": "Beklager, jeg fant ingen ledige timer akkurat nå. Spør kunden om de vil legge igjen en beskjed eller sjekke tilgjengelighet for en annen behandling.",
        "en": "I'm sorry, I couldn't find any available appointments right now. Please ask if the customer would like to leave a message or check availability for another treatment."
    },
    "no_availability_date": {
        "no": "Beklager, vi har ingen ledige timer {date}. Spør om kunden vil velge en annen dato eller første ledige tid.",
        "en": "I'm sorry, there are no appointments available on {date}. Please ask if the customer would like a different date or the next available slot."
    },
    "status_error": {
        "no": "Fikk ikke kontakt med bookingsystemet. Statuskode: {status}",
        "en": "Could not contact the booking system. Status code: {status}"
    },
    "technical_error_availability": {
        "no": "En teknisk feil oppstod ved sjekking av ledige timer.",
        "en": "A technical error occurred while checking available times."
    },
    "technical_error_booking": {
        "no": "En teknisk feil oppstod under booking.",
        "en": "A technical error occurred while booking the appointment."
    },
    "technical_error_message": {
        "no": "En teknisk feil oppstod ved sending av beskjed.",
        "en": "A technical error occurred while sending the message."
    },
    "technical_error_generic": {
        "no": "En teknisk feil oppstod.",
        "en": "A technical error occurred."
    },
    "default_message_summary": {
        "no": "Kunden ønsket å bli kontaktet. Ingen ytterligere detaljer ble gitt.",
        "en": "Customer asked for a callback. No additional details were provided."
    },
    "default_customer_name": {
        "no": "Kunde",
        "en": "Customer"
    },
    "requested_date_placeholder": {
        "no": "den ønskede datoen",
        "en": "the requested date"
    },
    "phone_number_unavailable": {
        "no": "Telefonnummer ikke tilgjengelig",
        "en": "Phone number not available"
    },
    "language_switching_unavailable": {
        "no": "Språkbytte ikke tilgjengelig",
        "en": "Language switching not available"
    },
    "unknown_language": {
        "no": "Ukjent språk: {language}. Bruk 'en' for engelsk eller 'no' for norsk.",
        "en": "Unknown language: {language}. Use 'en' for English or 'no' for Norwegian."
    },
    "cancel_booking_intro": {
        "no": "Jeg forstår at du ønsker å avlyse bookingen din. La meg hjelpe deg med det. For å finne bookingen din, trenger jeg personnummeret ditt. Kan du vennligst taste inn personnummeret ditt på telefonen din?",
        "en": "I understand you want to cancel your booking. Let me help you with that. To find your booking, I need your personal number. Can you please enter your personal number using your phone keypad?"
    },
    "get_client_detail_intro": {
        "no": "La meg søke etter bookingen din for deg.",
        "en": "Let me look up your booking for you."
    },
    "get_client_detail_updates": {
        "no": [
            "Jeg søker etter bookingen din nå...",
            "Et øyeblikk, jeg sjekker systemet...",
            "Takk for tålmodigheten, jeg er nesten ferdig..."
        ],
        "en": [
            "I'm looking up your booking now...",
            "Just a moment, I'm checking the system...",
            "Thank you for waiting, I'm almost done..."
        ]
    },
    "client_detail_found": {
        "no": "Perfekt! Jeg fant bookingen din. Du har en time for {treatment} den {date} klokken {time}.",
        "en": "Perfect! I found your booking. You have an appointment for {treatment} on {date} at {time}."
    },
    "client_detail_not_found": {
        "no": "Jeg fant ingen booking for dette personnummeret. Kan du bekrefte at personnummeret er korrekt?",
        "en": "I couldn't find any booking for this personal number. Can you confirm the personal number is correct?"
    },
    "cancel_booking_confirm": {
        "no": "Vil du bekrefte at du ønsker å avlyse bookingen din for {treatment} den {date} klokken {time}?",
        "en": "Do you confirm that you want to cancel your booking for {treatment} on {date} at {time}?"
    },
    "cancel_booking_success": {
        "no": "Ferdig! Bookingen din er nå avlyst. Er det noe annet jeg kan hjelpe deg med?",
        "en": "Done! Your booking has been cancelled. Is there anything else I can help you with?"
    },
    "cancel_booking_failure": {
        "no": "Beklager, jeg klarte ikke å avlyse bookingen. Prøv igjen senere eller kontakt oss direkte.",
        "en": "Sorry, I couldn't cancel the booking. Please try again later or contact us directly."
    },
    "cancel_booking_cancelled": {
        "no": "Avlysningen ble avbrutt. Bookingen din er fortsatt aktiv.",
        "en": "Cancellation was cancelled. Your booking is still active."
    },
    "booking_already_cancelled": {
        "no": "Du har allerede avlyst timen for {treatment} den {date} klokken {time}.",
        "en": "You have already cancelled the appointment for {treatment} on {date} at {time}."
    },
    "change_appointment_intro": {
        "no": "Jeg forstår at du vil endre time. For å finne din nåværende time, trenger jeg personnummeret ditt. Kan du vennligst taste inn personnummeret ditt på telefonen?",
        "en": "I understand you want to change your appointment. To find your current appointment, I need your personal number. Can you please enter your personal number using your phone keypad?"
    },
    "change_appointment_confirm_details": {
        "no": "Jeg fant bookingen din. Du har en time for {treatment} den {date} klokken {time}. Stemmer dette?",
        "en": "I found your booking. You have an appointment for {treatment} on {date} at {time}. Is this correct?"
    },
    "change_appointment_preference_question": {
        "no": "Vil du ha første ledige time, eller ønsker du en spesifikk dato?",
        "en": "Do you want the next available appointment or a specific date?"
    },
    "change_appointment_no_booking": {
        "no": "Jeg fant ingen aktiv booking for dette personnummeret. Kan du bekrefte at personnummeret er korrekt?",
        "en": "I couldn't find any active booking for this personal number. Can you confirm the personal number is correct?"
    },
    "update_appointment_intro": {
        "no": "La meg oppdatere timen din...",
        "en": "Let me update your appointment..."
    },
    "update_appointment_updates": {
        "no": [
            "Oppdaterer bookingen din nå...",
            "Et øyeblikk, jeg endrer tidspunktet...",
            "Takk for tålmodigheten..."
        ],
        "en": [
            "Updating your booking now...",
            "Just a moment, changing the appointment time...",
            "Thank you for waiting..."
        ]
    },
    "update_appointment_success": {
        "no": "Perfekt! Timen din er nå oppdatert til {date} klokken {time}. Er det noe annet jeg kan hjelpe deg med?",
        "en": "Perfect! Your appointment has been updated to {date} at {time}. Is there anything else I can help you with?"
    },
    "update_appointment_failure": {
        "no": "Beklager, jeg klarte ikke å oppdatere timen. Prøv igjen senere eller kontakt oss direkte.",
        "en": "Sorry, I couldn't update the appointment. Please try again later or contact us directly."
    }
}
