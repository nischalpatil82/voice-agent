"""
projects/hotel/intents.py — Hotel booking training data + intent handler.
Intents: BOOK_ROOM, CANCEL_BOOKING, CHECK_BOOKING, SHOW_ROOMS,
         ROOM_INFO, CHECK_IN, CHECK_OUT, REQUEST_SERVICE,
         GREET, HELP, THANKS, BYE, NAVIGATE
"""

WELCOME_HINT  = "Say 'show rooms', 'book a suite', or 'check my booking'."
GREET_HINT    = "Experience luxury and comfort at every stay!"
FALLBACK_HINT = "Try: show rooms, book deluxe room, check my booking, checkout."
HELP_TEXT = ("I can: show available rooms, book/cancel rooms, check booking status, "
             "room pricing, check-in/out assistance, and request room services.")

TRAINING_DATA = [
    # BOOK_ROOM
    ("book a room","BOOK_ROOM"),
    ("i want to book a suite","BOOK_ROOM"),
    ("reserve deluxe room","BOOK_ROOM"),
    ("book standard room for 2 nights","BOOK_ROOM"),
    ("i need a room","BOOK_ROOM"),
    ("make a reservation","BOOK_ROOM"),
    ("book family room","BOOK_ROOM"),
    ("reserve a room","BOOK_ROOM"),
    ("book presidential suite","BOOK_ROOM"),
    ("i want executive room","BOOK_ROOM"),
    # CANCEL_BOOKING
    ("cancel booking","CANCEL_BOOKING"),
    ("cancel my reservation","CANCEL_BOOKING"),
    ("i want to cancel my room","CANCEL_BOOKING"),
    ("cancel room booking","CANCEL_BOOKING"),
    ("remove my reservation","CANCEL_BOOKING"),
    # CHECK_BOOKING
    ("check my booking","CHECK_BOOKING"),
    ("my reservation details","CHECK_BOOKING"),
    ("booking status","CHECK_BOOKING"),
    ("show my bookings","CHECK_BOOKING"),
    ("upcoming reservation","CHECK_BOOKING"),
    ("booking confirmation","CHECK_BOOKING"),
    # SHOW_ROOMS
    ("show rooms","SHOW_ROOMS"),
    ("available rooms","SHOW_ROOMS"),
    ("list rooms","SHOW_ROOMS"),
    ("what rooms do you have","SHOW_ROOMS"),
    ("room types","SHOW_ROOMS"),
    ("show all rooms","SHOW_ROOMS"),
    # ROOM_INFO
    ("room price","ROOM_INFO"),
    ("how much is the suite","ROOM_INFO"),
    ("cost of deluxe room","ROOM_INFO"),
    ("tell me about standard room","ROOM_INFO"),
    ("executive room details","ROOM_INFO"),
    # CHECK_IN
    ("check in","CHECK_IN"),
    ("i want to check in","CHECK_IN"),
    ("check in process","CHECK_IN"),
    ("how do i check in","CHECK_IN"),
    # CHECK_OUT
    ("check out","CHECK_OUT"),
    ("i want to check out","CHECK_OUT"),
    ("checkout time","CHECK_OUT"),
    ("how do i check out","CHECK_OUT"),
    # REQUEST_SERVICE
    ("room service","REQUEST_SERVICE"),
    ("i need towels","REQUEST_SERVICE"),
    ("send housekeeping","REQUEST_SERVICE"),
    ("request extra pillows","REQUEST_SERVICE"),
    ("order food to room","REQUEST_SERVICE"),
    ("wake up call","REQUEST_SERVICE"),
    # UNIVERSAL
    ("hello","GREET"), ("hi","GREET"), ("good evening","GREET"),
    ("help","HELP"), ("what can you do","HELP"),
    ("thanks","THANKS"), ("thank you","THANKS"),
    ("bye","BYE"), ("goodbye","BYE"),
    ("dark mode","THEME_DARK"), ("light mode","THEME_LIGHT"),
    ("go to home","NAVIGATE"), ("my bookings","NAVIGATE"),
]

def handle_intent(intent, text, matcher, ctx, make_json, extract_quantity):
    t = text.lower()

    if intent == "BOOK_ROOM":
        room = matcher.find(text)
        nights = extract_quantity(text)
        if room:
            ctx.update(intent, room, nights)
            ctx.set_booking("room", room["name"])
            ctx.set_booking("nights", nights)
            ctx.set_booking("total", f"Rs.{room['price']*nights:.0f}")
            msg = (f"Booking {room['name']} for {nights} night(s). "
                   f"Rs.{room['price']:.0f}/night — Total: Rs.{room['price']*nights:.0f}. "
                   f"Please confirm check-in date.")
            return {"intent": intent, "message": msg,
                    "json": make_json(msg, "book_room",
                                      {"roomId": room["id"], "nights": nights,
                                       "roomType": room["name"]})}
        return {"intent": intent,
                "message": "Which room type? Try: book deluxe room, book suite",
                "json": "{}"}

    if intent == "CANCEL_BOOKING":
        ctx.clear_booking(); ctx.update(intent)
        return {"intent": intent,
                "message": "Reservation cancelled. We hope to welcome you again!",
                "json": make_json("Reservation cancelled", "cancel_booking")}

    if intent == "CHECK_BOOKING":
        ctx.update(intent)
        summary = ctx.get_booking_summary()
        return {"intent": intent, "message": f"Your reservation: {summary}",
                "json": make_json("Showing booking", "show_booking")}

    if intent == "SHOW_ROOMS":
        rooms = matcher.db.load()
        listing = "\n".join(f"  {r['name']} — Rs.{r['price']:.0f}/night" for r in rooms)
        ctx.update(intent)
        return {"intent": intent, "message": f"Available Rooms:\n{listing}",
                "json": make_json("Showing rooms", "show_rooms")}

    if intent == "ROOM_INFO":
        room = matcher.find(text)
        if room:
            ctx.update(intent, room)
            msg = f"{room['name']}: Rs.{room['price']:.0f} per night"
            return {"intent": intent, "message": msg, "json": make_json(msg)}
        return {"intent": intent, "message": "Which room type?", "json": "{}"}

    if intent == "CHECK_IN":
        return {"intent": intent,
                "message": "Welcome! Proceeding with check-in. Please have your ID ready.",
                "json": make_json("Check-in", "initiate_checkin")}

    if intent == "CHECK_OUT":
        ctx.clear_booking(); ctx.update(intent)
        return {"intent": intent,
                "message": "Checking you out. Thank you for staying with us!",
                "json": make_json("Check-out", "initiate_checkout")}

    if intent == "REQUEST_SERVICE":
        service = "general"
        if "food" in t or "room service" in t: service = "food"
        elif "towel" in t or "housekeeping" in t: service = "housekeeping"
        elif "pillow" in t or "blanket" in t: service = "amenities"
        elif "wake" in t: service = "wake_up_call"
        return {"intent": intent,
                "message": f"Room service request ({service}) sent. We'll be with you shortly!",
                "json": make_json(f"Service: {service}", "room_service", {"service": service})}

    return None
