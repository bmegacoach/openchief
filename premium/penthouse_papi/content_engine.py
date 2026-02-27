"""
Penthouse Papi Content Engine — Premium Module
Feature flag: ENABLE_PENTHOUSE_PAPI=true
AI-powered content generation for social media and marketing.
"""
import os
from event_logging.event_logger import EventLogger

ENABLED = os.getenv("ENABLE_PENTHOUSE_PAPI", "false").lower() == "true"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

logger = EventLogger()

CONTENT_SYSTEM_PROMPT = """You are Penthouse Papi, a premium content strategist for a Web3/RWA brand.
You write punchy, engaging social media copy that converts.
Keep posts under 280 chars for X/Twitter unless specified.
Tone: confident, knowledgeable, slightly edgy — never cringe."""


class ContentEngine:
    """Generate social content using Claude."""

    def __init__(self):
        self.enabled = ENABLED

    def is_configured(self) -> bool:
        return self.enabled and bool(ANTHROPIC_API_KEY)

    def generate_post(self, brief: str, platform: str = "twitter") -> dict:
        if not self.is_configured():
            return {"status": "unconfigured", "content": None}
        try:
            import anthropic  # type: ignore
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=300,
                system=CONTENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"Platform: {platform}\nBrief: {brief}"}],
            )
            content = msg.content[0].text
            logger.log_event("content_generated", {"platform": platform, "chars": len(content)})
            return {"status": "ok", "content": content, "platform": platform}
        except Exception as exc:
            logger.log_event("content_error", {"error": str(exc)})
            return {"status": "error", "error": str(exc)}

    def generate_thread(self, topic: str, num_tweets: int = 5) -> dict:
        if not self.is_configured():
            return {"status": "unconfigured", "thread": []}
        brief = (
            f"Write a {num_tweets}-tweet thread about: {topic}. "
            f"Number each tweet 1/{num_tweets} through {num_tweets}/{num_tweets}. "
            "Each tweet under 280 chars."
        )
        result = self.generate_post(brief, platform="twitter-thread")
        if result["status"] != "ok":
            return result
        tweets = [t.strip() for t in result["content"].split("\n") if t.strip()]
        return {"status": "ok", "thread": tweets}
