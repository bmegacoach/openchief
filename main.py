"""
OpenChief V2 — Entry Point
Usage: python main.py
Requires: .env with DISCORD_TOKEN set
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def check_env():
    """Validate required environment variables before boot."""
    required = ["DISCORD_TOKEN"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"[ERROR] Missing required env vars: {', '.join(missing)}")
        print("        Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    # Warn about optional but important keys
    optional = {
        "ANTHROPIC_API_KEY": "Claude LLM (agents will use stub responses)",
        "DISCORD_GUILD_ID":  "Server ID (some features limited)",
    }
    for key, purpose in optional.items():
        if not os.getenv(key):
            print(f"[WARN]  {key} not set — {purpose}")


def main():
    check_env()

    from bot.client import create_bot  # noqa: import after env check

    bot = create_bot()

    print("[OpenChief] Starting bot...")
    try:
        bot.run(os.getenv("DISCORD_TOKEN"), log_handler=None)
    except KeyboardInterrupt:
        print("\n[OpenChief] Shutting down gracefully.")
    except Exception as exc:
        print(f"[OpenChief] Fatal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
