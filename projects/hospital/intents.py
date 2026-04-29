"""
projects/hospital/intents.py — Hospital management training data + intent handler.
Intents: BOOK_APPOINTMENT, CANCEL_APPOINTMENT, CHECK_APPOINTMENT,
         SHOW_DOCTORS, DOCTOR_INFO, EMERGENCY, SHOW_REPORTS,
         GREET, HELP, THANKS, BYE, NAVIGATE
"""

WELCOME_HINT  = "Say 'book appointment', 'show doctors', or 'emergency'."
GREET_HINT    = "Your health is our priority. How can we help you today?"
FALLBACK_HINT = "Try: book appointment with cardiologist, show doctors, check my appointment."
HELP_TEXT = ("I can: book/cancel appointments, show available doctors, "
             "check appointment status, find doctors by specialty, "
             "show reports, and handle emergencies.")

TRAINING_DATA = [
    # BOOK_APPOINTMENT
    ("book appointment","BOOK_APPOINTMENT"),
    ("i need to see a doctor","BOOK_APPOINTMENT"),
    ("schedule appointment with cardiologist","BOOK_APPOINTMENT"),
    ("book appointment with dr sharma","BOOK_APPOINTMENT"),
    ("i want to see a dermatologist","BOOK_APPOINTMENT"),
    ("appointment for tomorrow","BOOK_APPOINTMENT"),
    ("book checkup","BOOK_APPOINTMENT"),
    ("schedule a visit","BOOK_APPOINTMENT"),
    ("i need an appointment","BOOK_APPOINTMENT"),
    ("see a doctor tomorrow","BOOK_APPOINTMENT"),
    ("book with general physician","BOOK_APPOINTMENT"),
    ("need to consult a doctor","BOOK_APPOINTMENT"),
    # CANCEL_APPOINTMENT
    ("cancel appointment","CANCEL_APPOINTMENT"),
    ("cancel my booking","CANCEL_APPOINTMENT"),
    ("i can't make it","CANCEL_APPOINTMENT"),
    ("cancel tomorrow's appointment","CANCEL_APPOINTMENT"),
    ("remove my appointment","CANCEL_APPOINTMENT"),
    ("i want to cancel","CANCEL_APPOINTMENT"),
    # CHECK_APPOINTMENT
    ("check my appointment","CHECK_APPOINTMENT"),
    ("my appointment status","CHECK_APPOINTMENT"),
    ("when is my appointment","CHECK_APPOINTMENT"),
    ("appointment details","CHECK_APPOINTMENT"),
    ("show my bookings","CHECK_APPOINTMENT"),
    ("upcoming appointments","CHECK_APPOINTMENT"),
    # SHOW_DOCTORS
    ("show doctors","SHOW_DOCTORS"),
    ("available doctors","SHOW_DOCTORS"),
    ("list doctors","SHOW_DOCTORS"),
    ("who are the doctors","SHOW_DOCTORS"),
    ("show specialists","SHOW_DOCTORS"),
    ("which doctors are available","SHOW_DOCTORS"),
    # DOCTOR_INFO
    ("doctor fee","DOCTOR_INFO"),
    ("consultation fee","DOCTOR_INFO"),
    ("how much does dr sharma charge","DOCTOR_INFO"),
    ("info about neurologist","DOCTOR_INFO"),
    ("tell me about the cardiologist","DOCTOR_INFO"),
    # EMERGENCY
    ("emergency","EMERGENCY"),
    ("it's urgent","EMERGENCY"),
    ("i need help now","EMERGENCY"),
    ("ambulance","EMERGENCY"),
    ("severe chest pain","EMERGENCY"),
    ("someone collapsed","EMERGENCY"),
    ("call doctor immediately","EMERGENCY"),
    # SHOW_REPORTS
    ("show my reports","SHOW_REPORTS"),
    ("medical reports","SHOW_REPORTS"),
    ("lab results","SHOW_REPORTS"),
    ("test results","SHOW_REPORTS"),
    ("prescription history","SHOW_REPORTS"),
    # UNIVERSAL
    ("hello","GREET"), ("hi","GREET"), ("good morning","GREET"),
    ("help","HELP"), ("what can you do","HELP"),
    ("thanks","THANKS"), ("thank you","THANKS"),
    ("bye","BYE"), ("goodbye","BYE"),
    ("go to home","NAVIGATE"), ("go to login","NAVIGATE"),
    ("my profile","NAVIGATE"), ("appointments page","NAVIGATE"),
]

def handle_intent(intent, text, matcher, ctx, make_json, extract_quantity):
    t = text.lower()

    if intent == "BOOK_APPOINTMENT":
        doctor = matcher.find(text)
        if doctor:
            ctx.update(intent, doctor)
            ctx.set_booking("doctor", doctor["name"])
            ctx.set_booking("fee", f"Rs.{doctor['price']:.0f}")
            msg = (f"Appointment request for {doctor['name']}. "
                   f"Consultation fee: Rs.{doctor['price']:.0f}. "
                   f"Please confirm date and time.")
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "book_appointment",
                                      {"doctorId": doctor["id"], "doctorName": doctor["name"]})}
        msg = "Which doctor or specialty? Say: book appointment with cardiologist"
        return {"intent": intent, "message": msg, "json": "{}"}

    if intent == "CANCEL_APPOINTMENT":
        ctx.clear_booking(); ctx.update(intent)
        return {"intent": intent, "message": "Appointment cancelled. We hope to see you soon.",
                "json": make_json("Appointment cancelled", "cancel_appointment")}

    if intent == "CHECK_APPOINTMENT":
        ctx.update(intent)
        summary = ctx.get_booking_summary()
        return {"intent": intent, "message": f"Your booking: {summary}",
                "json": make_json("Showing appointments", "show_appointments")}

    if intent == "SHOW_DOCTORS":
        doctors = matcher.db.load()
        listing = "\n".join(f"  {d['name']} — Rs.{d['price']:.0f}" for d in doctors)
        ctx.update(intent)
        return {"intent": intent, "message": f"Available Doctors:\n{listing}",
                "json": make_json("Showing doctors", "show_doctors")}

    if intent == "DOCTOR_INFO":
        doctor = matcher.find(text)
        if doctor:
            ctx.update(intent, doctor)
            msg = f"{doctor['name']}: Consultation fee Rs.{doctor['price']:.0f}"
            return {"intent": intent, "message": msg, "json": make_json(msg)}
        return {"intent": intent, "message": "Which doctor or specialty?", "json": "{}"}

    if intent == "EMERGENCY":
        return {"intent": intent,
                "message": "EMERGENCY! Connecting to emergency services immediately. Please stay calm.",
                "json": make_json("EMERGENCY", "emergency_alert", {"priority": "HIGH"})}

    if intent == "SHOW_REPORTS":
        ctx.update(intent)
        return {"intent": intent, "message": "Showing your medical reports and test results.",
                "json": make_json("Showing reports", "show_reports")}

    return None
