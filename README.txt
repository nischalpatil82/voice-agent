Multi-Project Voice Agent
=========================

Reusable voice agent engine for:
- CraveHub
- Ecommerce
- Hospital
- Hotel
- JustBill

This document is written as a handoff guide for a new developer or operator.


1) What Must Be Installed
=========================

Required for all environments:
1. Python 3.11 (recommended)
2. pip (comes with Python)
3. Git (if cloning from a repo)
4. FFmpeg (required for voice transcription endpoints)

Usually required when installing audio dependencies from source:
1. C/C++ build tools
2. PortAudio development libraries

Optional but recommended:
1. Docker Desktop (for container build/run)


2) OS-Specific Prerequisites
============================

Windows
-------
1. Install Python 3.11 from python.org (check Add Python to PATH).
2. Install FFmpeg using one of these:
   winget install Gyan.FFmpeg
   OR manually install and add ffmpeg/bin to PATH.
3. If PyAudio installation fails, install Visual C++ Build Tools.

macOS
-----
1. Install Python 3.11 (python.org installer or pyenv).
2. Install FFmpeg:
   brew install ffmpeg
3. If PyAudio installation fails:
   brew install portaudio

Ubuntu/Debian Linux
-------------------
1. Install system packages:
   sudo apt-get update
   sudo apt-get install -y python3 python3-venv python3-pip ffmpeg portaudio19-dev build-essential


3) Project Setup (First Time)
=============================

From the project root folder:

Windows PowerShell
------------------
1. python -m venv .venv
2. Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
3. . .venv\Scripts\Activate.ps1
4. python -m pip install --upgrade pip
5. pip install -r requirements.txt

macOS/Linux
-----------
1. python3 -m venv .venv
2. source .venv/bin/activate
3. python -m pip install --upgrade pip
4. pip install -r requirements.txt

Developer/test tools (optional but recommended):
1. pip install -r requirements-dev.txt


4) Environment Variables (.env)
===============================

Create a file named .env in the project root.

Local development baseline:

VOICE_AGENT_PRODUCTION=false
VOICE_AGENT_ADMIN_TOKEN=change-me-admin
VOICE_AGENT_REQUIRE_PUBLIC_TOKEN=false
VOICE_AGENT_PUBLIC_TOKEN=change-me-public
VOICE_AGENT_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
VOICE_AGENT_ALLOW_LOCALHOST_ORIGINS=true
VOICE_AGENT_TRUST_PROXY_HEADERS=false
VOICE_AGENT_REQUIRE_ADMIN_TOKEN=false
JUSTBILL_VERIFY_TLS=true
JUSTBILL_VOICE_PROFILE=balanced

Notes:
1. For local testing, public token auth can be disabled.
2. For production, set VOICE_AGENT_REQUIRE_PUBLIC_TOKEN=true.
3. Keep JUSTBILL_VERIFY_TLS=true outside controlled local debugging.
4. JUSTBILL_ACTION_API_URL is optional and should be set only when action callbacks are required.
5. To auto-pick new JustBill products immediately, set JUSTBILL_FETCH_LIVE_EVERY_REQUEST=true.
6. Use JUSTBILL_RELOAD_EVERY to control cache seconds (set 0 to disable cache).


5) Run the Application
======================

CLI mode:
1. python main.py --project cravehub
2. python main.py --project ecommerce
3. python main.py --project hospital
4. python main.py --project hotel
5. python main.py --project justbill

Interactive CLI selector:
1. python main.py

Web API (single project):
1. python server.py --project justbill

Web API production path (Waitress):
1. python server.py --project justbill --production

Run all projects:
1. python server.py --all
2. python server.py --all --production


6) API Endpoints
================

Public endpoints:
1. GET /health
2. GET /ready
3. POST /command
4. POST /voice-command
5. POST /transcribe
6. POST /speak
7. GET /items

Admin endpoints (header X-Admin-Token required):
1. POST /reload
2. GET /analytics (when VOICE_AGENT_ENABLE_ANALYTICS=true)

Optional public endpoint auth:
1. Set VOICE_AGENT_REQUIRE_PUBLIC_TOKEN=true
2. Send token in X-Client-Token header
3. Authorization: Bearer <token> also works


7) Health Checks and Quick Validation
=====================================

1. Open:
   http://127.0.0.1:5004/health

2. Compile check:
   python -m compileall main.py server.py core projects

3. Run tests:
   pytest -q


8) Voice Configuration and Performance
======================================

JustBill voice profile:
1. JUSTBILL_VOICE_PROFILE=fast
   - Lowest latency
   - Lower accuracy
2. JUSTBILL_VOICE_PROFILE=balanced
   - Recommended default
   - Better accuracy with good latency
3. JUSTBILL_VOICE_PROFILE=accurate
   - Better decoding quality
   - Higher latency

Common voice environment overrides:
1. VOICE_WHISPER_MODEL=tiny|small|medium
2. JUSTBILL_VOICE_BEAM_SIZE=1|2|3
3. JUSTBILL_VOICE_BEST_OF=1|2|3
4. JUSTBILL_VOICE_ENABLE_FALLBACK_PASS=true|false

Important:
1. First voice request can be slow because Whisper model downloads/caches.
2. Later requests are much faster after model warm-up.


9) Production Requirements Checklist
====================================

Before production deploy:
1. VOICE_AGENT_PRODUCTION=true
2. Restrict VOICE_AGENT_CORS_ORIGINS to real frontend domains
3. VOICE_AGENT_ALLOW_LOCALHOST_ORIGINS=false
4. VOICE_AGENT_TRUST_PROXY_HEADERS=false unless behind a trusted reverse proxy
5. JUSTBILL_VERIFY_TLS=true
6. Run with --production
7. Optional token auth hardening:
   - VOICE_AGENT_REQUIRE_ADMIN_TOKEN=true and set VOICE_AGENT_ADMIN_TOKEN
   - VOICE_AGENT_REQUIRE_PUBLIC_TOKEN=true and set VOICE_AGENT_PUBLIC_TOKEN
8. Optional strict catalog controls:
   - JUSTBILL_STRICT_CATALOG=true
   - JUSTBILL_ALLOW_FALLBACK_IN_PRODUCTION=false
   - VOICE_AGENT_FAIL_STARTUP_ON_CATALOG_DEGRADED=true


10) Docker Build and Run
========================

Build image:
1. docker build -t voice-agent-justbill:latest .

Run container (example):
1. docker run -d --name voice-agent-justbill -p 5004:5004 -e VOICE_AGENT_CORS_ORIGINS=https://your-frontend-domain.com -e JUSTBILL_VOICE_PROFILE=balanced voice-agent-justbill:latest

View logs:
1. docker logs -f voice-agent-justbill


11) Common Troubleshooting
==========================

Problem: SSL certificate verify failed when loading JustBill API
Fix:
1. Ensure host has updated root certificates.
2. Keep JUSTBILL_VERIFY_TLS=true in production.
3. As fallback, app can run with demo catalog data.

Problem: ffmpeg is not installed
Fix:
1. Install FFmpeg and verify with:
   ffmpeg -version

Problem: Slow first voice response
Fix:
1. Expected on first run due model download.
2. Keep server running so model stays warm.

Problem: CORS or Unauthorized errors
Fix:
1. Verify VOICE_AGENT_CORS_ORIGINS values.
2. Verify X-Client-Token for public endpoints.
3. Verify X-Admin-Token for admin endpoints.


12) Project Structure
=====================

main.py                    - CLI entry point
server.py                  - Flask/Waitress API server
core/
  database.py              - generic data loading
  matcher.py               - fuzzy item matching
  classifier.py            - ML intent classifier
  context.py               - conversation/session memory
  actions.py               - action payload construction
  voice.py                 - microphone path
projects/
  cravehub/
  ecommerce/
  hospital/
  hotel/
  justbill/

