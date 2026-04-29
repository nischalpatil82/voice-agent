# Voice Agent Project - Beginner Detailed Guide

## 1) What This Project Is

This repository is a reusable voice-command engine that can power multiple business domains.

It currently supports five project flavors:

1. CraveHub (food ordering)
2. Ecommerce Store (shopping)
3. Hospital Management (doctor and appointment flows)
4. Hotel Booking (room booking flows)
5. JustBill Jewellery (jewellery shopping + live product catalog API)

In simple terms, this project listens to what the user says (or types), understands intent, finds relevant items, and returns structured actions for a frontend/backend to execute.

Examples:

1. "add diamond ring to cart" -> returns `ADD_TO_CART` and action payload.
2. "show my cart" -> returns cart summary and action to open cart.
3. "book deluxe room" -> goes through hotel-specific intent handling.

## 2) Core Concepts (No Prior Knowledge Needed)

### 2.1 Intent

An intent is the meaning of a user command.

Examples:

1. `ADD_TO_CART`
2. `SHOW_CART`
3. `CHECKOUT`
4. `SEARCH`
5. `NAVIGATE`

The classifier predicts one intent from user text.

### 2.2 Entity / Item Matching

After intent is known, the system tries to identify the product/doctor/room the user mentioned.

This is done by matcher logic that uses:

1. Exact matching
2. Keyword matching
3. Fuzzy matching
4. Voice/spelling normalization

### 2.3 Context (Memory During Conversation)

The system keeps session context:

1. Last intent
2. Last referenced item
3. Cart contents
4. Booking details
5. Recent history

This helps with commands like "add one more" or "book that one".

### 2.4 Action Payload

The response includes:

1. Human message
2. Action list with type + params

Frontend can use action payload to actually navigate, add item, update cart, etc.

## 3) Project Structure Explained

## 3.1 Top-Level Files

1. `main.py`
   - CLI mode entry point.
   - Supports typed commands and `/voice` microphone mode.

2. `server.py`
   - Flask API server mode.
   - Exposes endpoints like `/command`, `/voice-command`, `/transcribe`, `/health`, `/ready`.

3. `README.txt`
   - Operations/setup guide (installation, env vars, production notes).

4. `requirements.txt` and `requirements-dev.txt`
   - Runtime and test dependencies.

5. `Dockerfile` and `.dockerignore`
   - Containerization setup.

## 3.2 `core/` Folder (Shared Engine)

1. `core/classifier.py`
   - ML intent classifier based on scikit-learn.
   - Pipeline: TF-IDF + LogisticRegression.
   - Returns intent + confidence.

2. `core/preprocessor.py`
   - Cleans and normalizes text.
   - Handles spelling mistakes, phonetic variants, shortcuts.
   - Protects domain words from wrong corrections.

3. `core/matcher.py`
   - Finds best item mentioned by user.
   - Uses exact, keyword, indexed, and fuzzy matching.
   - Includes synonyms and voice-error normalization.

4. `core/context.py`
   - In-memory context per user session.
   - Keeps cart and booking state.
   - `SessionManager` handles multiple users with TTL cleanup.

5. `core/actions.py`
   - Builds response payload (message + actions JSON).
   - Performs sanitization and optional async callback to external API.

6. `core/database.py`
   - Generic MySQL item loader for projects using relational tables.
   - Supports fallback items when DB is unavailable.

7. `core/voice.py`
   - Microphone-based speech capture path (CLI).
   - Whisper-first transcription with fallback behavior.

8. `core/tts.py`
   - Text-to-speech output support.

## 3.3 `projects/` Folder (Domain Customization)

Each project folder contains domain-specific rules:

1. `config.py`
   - Project name, API URL, confidence thresholds, DB/table config, fallback items.

2. `intents.py`
   - Training examples (`TRAINING_DATA`).
   - Intent handling logic (`handle_intent`).
   - Help/welcome/fallback text.

3. Optional `database.py` (project-specific)
   - JustBill uses custom live API loader (`projects/justbill/database.py`) instead of generic MySQL-only loader.

## 4) How a Request Flows Through the System

This is the full flow for API mode (`server.py`).

1. Client sends text or audio.
2. API creates or retrieves session context.
3. Text is normalized (audio transcripts get extra cleanup).
4. Classifier predicts intent + confidence.
5. Low confidence may trigger clarification or fallback behavior.
6. Action builder delegates to project-specific `handle_intent`.
7. Matcher tries to resolve item mentioned in user text.
8. Database layer supplies catalog items (live, cache, or fallback).
9. Context is updated (cart, last item, history).
10. Response returns message + actions.

## 5) CLI Mode vs API Mode

## 5.1 CLI Mode (`main.py`)

Good for local/manual testing.

Command examples:

1. `python main.py --project justbill`
2. Type commands directly, or use `/voice`.

Special CLI commands:

1. `/voice` - microphone input
2. `/reload` - reload items and retrain classifier
3. `/cart` - print current context/cart
4. `/quit` - exit

## 5.2 API Mode (`server.py`)

Used by frontend apps and integration.

Common endpoints:

1. `GET /health` - service and catalog status
2. `GET /ready` - readiness for deployment probes
3. `POST /command` - text command processing
4. `POST /voice-command` - audio transcription + command execution
5. `POST /transcribe` - audio-to-text only
6. `POST /speak` - text-to-speech as WAV
7. `GET /items` - available catalog items
8. `POST /reload` - admin reload
9. `GET /analytics` - admin analytics (if enabled)

## 6) JustBill-Specific Behavior (Important)

JustBill is special compared to other projects:

1. Product catalog is fetched from live external API (`/api/Product/get_ProductList`).
2. It has resilience features:
   - retry
   - timeout handling
   - circuit breaker
   - fallback catalog
3. It supports strict production controls and readiness checks.
4. It supports live refresh mode:
   - `JUSTBILL_FETCH_LIVE_EVERY_REQUEST=true`
   - or `JUSTBILL_RELOAD_EVERY=0`

If live API fails (for example SSL certificate issue), it can serve fallback items.

## 7) Environment Variables You Should Understand First

Minimal important ones:

1. `VOICE_AGENT_PRODUCTION`
   - `false` for local development.
   - `true` enables stricter checks.

2. `VOICE_AGENT_CORS_ORIGINS`
   - allowed frontend origins for API.

3. `JUSTBILL_VERIFY_TLS`
   - should be `true` in production.
   - local debugging may temporarily set `false`.

4. `JUSTBILL_FETCH_LIVE_EVERY_REQUEST`
   - if `true`, fetches catalog from source every request.

5. `JUSTBILL_RELOAD_EVERY`
   - cache duration in seconds.
   - `0` disables cache.

6. `VOICE_AGENT_ADMIN_TOKEN`
   - required to access admin endpoints when enforced.

## 8) What Happens When Things Go Wrong

### 8.1 Could not understand audio

Likely speech recognition/transcription issue.

Check:

1. microphone quality
2. FFmpeg installed and in PATH
3. Whisper model load status in logs

### 8.2 Wrong item matched

Could be because:

1. catalog not loaded as expected
2. fallback catalog differs from real catalog
3. transcript wording differs from product terms

Check:

1. `GET /health` catalog block
2. `GET /items` to inspect current loaded items
3. matcher tests in `tests/test_matcher_behavior.py`

### 8.3 Always getting fallback responses

Possible causes:

1. low intent confidence
2. missing training examples in project `intents.py`
3. catalog unavailable

## 9) How to Add or Modify Behavior

## 9.1 Add New Intent

1. Add training examples in `projects/<name>/intents.py`.
2. Add handling branch in `handle_intent`.
3. Return message + action JSON.
4. Add tests.

## 9.2 Add New Project

1. Create `projects/newproject/config.py`.
2. Create `projects/newproject/intents.py`.
3. Add project name to `AVAILABLE_PROJECTS` in `main.py` and `server.py`.
4. Add fallback items and DB/API settings.
5. Add tests for project behavior.

## 9.3 Improve Matching

1. Update `core/matcher.py` normalization/synonyms safely.
2. Keep precision safeguards to avoid wrong item selections.
3. Add regression tests before changing thresholds.

## 10) Testing Strategy (How to Trust Changes)

Run focused tests first:

1. `pytest tests/test_matcher_behavior.py`
2. `pytest tests/test_justbill_intents.py`
3. `pytest tests/test_justbill_database.py`

Run full suite:

1. `pytest -q`

Testing goals:

1. avoid wrong intent predictions for common phrases
2. avoid wrong item mapping
3. verify fallback and security behavior

## 11) Security and Production Notes

1. Use `--production` when running server in production.
2. Keep `JUSTBILL_VERIFY_TLS=true` in production.
3. Restrict `VOICE_AGENT_CORS_ORIGINS` to real domains only.
4. Enforce tokens for admin/public endpoints where needed.
5. Avoid exposing internal errors in public responses.

## 12) Quick Start for a New Developer (30-Minute Path)

1. Create virtual env and install dependencies.
2. Run `python server.py --project justbill`.
3. Open `http://127.0.0.1:5004/health`.
4. Send a text command to `/command`.
5. Check `/items` to confirm catalog source.
6. Read these files in order:
   - `main.py`
   - `server.py`
   - `core/classifier.py`
   - `core/matcher.py`
   - `core/actions.py`
   - `projects/justbill/intents.py`
   - `projects/justbill/database.py`

## 13) One-Screen Mental Model

Use this model while debugging:

1. Input quality issue?
   - check transcription
2. Intent issue?
   - check classifier confidence and training examples
3. Item issue?
   - check catalog source and matcher logic
4. State issue?
   - check session context
5. Action issue?
   - check action payload and frontend handling

If you remember only one thing: this project is a layered pipeline, and each layer has clear responsibilities. Debug one layer at a time.
