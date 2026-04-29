"""
main.py — Entry point for the multi-project voice agent

Usage:
  python main.py --project cravehub
  python main.py --project ecommerce
  python main.py --project hospital
  python main.py --project hotel
    python main.py --project justbill

Commands during runtime:
  /voice   -> mic input
  /reload  -> reload items from DB + retrain classifier
  /cart    -> show cart / context summary
  /quit    -> exit
"""
import argparse
import importlib
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

sys.path.insert(0, os.path.dirname(__file__))

from core.database   import ItemDB
from core.matcher    import ItemMatcher
from core.classifier import IntentClassifier
from core.context    import ConversationContext
from core.actions    import ActionBuilder
from core.voice      import build_voice_guidance, listen
from core.tts        import speak

AVAILABLE_PROJECTS = ["cravehub", "ecommerce", "hospital", "hotel", "justbill"]

def load_project(name):
    if name not in AVAILABLE_PROJECTS:
        print(f"  [ERROR] Unknown project '{name}'.")
        print(f"  Available: {', '.join(AVAILABLE_PROJECTS)}")
        sys.exit(1)
    config  = importlib.import_module(f"projects.{name}.config")
    intents = importlib.import_module(f"projects.{name}.intents")
    return config, intents

def main():
    parser = argparse.ArgumentParser(description="Multi-project Voice Agent")
    parser.add_argument("--project", required=False, default=None,
                        help="Project name: cravehub | ecommerce | hospital | hotel | justbill")
    parser.add_argument("--speak", action=argparse.BooleanOptionalAction,
                        default=os.getenv("VOICE_AGENT_SPEAK", "true").strip().lower() in {"1", "true", "yes", "on"},
                        help="Speak responses aloud using local TTS")
    args = parser.parse_args()

    if not args.project:
        print("\n  Available projects:")
        for i, p in enumerate(AVAILABLE_PROJECTS, 1):
            print(f"    {i}. {p}")
        choice = input("\n  Select project (name or number): ").strip().lower()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(AVAILABLE_PROJECTS):
                args.project = AVAILABLE_PROJECTS[idx]
            else:
                print("  Invalid selection."); sys.exit(1)
        else:
            args.project = choice

    config, intents_module = load_project(args.project)

    print("\n" + "="*55)
    print(f"  Voice Agent   : {config.PROJECT_NAME}")
    print(f"  Project       : {args.project}")
    print(f"  API           : {config.API_BASE_URL}")
    print("  /voice=mic  /reload=refresh  /quit=exit")
    print("="*55 + "\n")

    db      = ItemDB(config)
    matcher = ItemMatcher(db)
    db.load()
    voice_hotwords, voice_prompt = build_voice_guidance(config, db.items)

    clf     = IntentClassifier(intents_module.TRAINING_DATA)
    ctx     = ConversationContext()
    builder = ActionBuilder(config, intents_module)

    print(f"\n  Ready! {intents_module.WELCOME_HINT}\n")

    while True:
        try:
            mode = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not mode: continue
        if mode == "/quit":
            print("Goodbye!"); break

        if mode == "/reload":
            db.last_loaded = 0
            db.load()
            voice_hotwords, voice_prompt = build_voice_guidance(config, db.items)
            clf = IntentClassifier(intents_module.TRAINING_DATA)
            ctx = ConversationContext()
            print("  Reloaded.\n")
            continue

        if mode == "/cart":
            print(f"\n  {ctx.get_context_summary()}\n")
            continue

        text = listen(
            config.LANGUAGE,
            initial_prompt=voice_prompt,
            hotwords=voice_hotwords,
        ) if mode == "/voice" else mode
        if not text: continue

        intent, confidence = clf.predict(text)
        if confidence < config.CONFIDENCE_WARN:
            print(f"  [Low confidence: {confidence}]")

        result = builder.build(intent, text, matcher, ctx)

        print(f"\n  Intent  : {result['intent']} ({confidence})")
        print(f"  Message : {result['message']}")
        print(f"  JSON    : {result['json']}")
        print()

        if args.speak and result.get("message"):
            try:
                speak(result["message"], voice_hint=getattr(config, "VOICE_TTS_HINT", ""), wait=True)
            except Exception as exc:
                print(f"  [TTS] {exc}")

        if result["intent"] == "BYE":
            break

if __name__ == "__main__":
    main()
