import re


class Layer3Data:
    """
    Layer 3 Security: Outbound Data Protection.
    Redacts secrets, API keys, tokens from content before LLM sees it.
    """

    PATTERNS = [
        (r"sk-[A-Za-z0-9]{20,}", "[REDACTED-SK-KEY]"),
        (r"[A-Za-z0-9]{24,28}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,38}", "[REDACTED-DISCORD-TOKEN]"),
        (r"\b[0-9a-fA-F]{32,64}\b", "[REDACTED-HEX-SECRET]"),
        (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer [REDACTED-BEARER-TOKEN]"),
        (r"Basic\s+[A-Za-z0-9+/]+=*", "Basic [REDACTED-BASIC-AUTH]"),
        (r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", "[REDACTED-PRIVATE-KEY]"),
        (r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "[REDACTED-JWT]"),
        (r"password\s*=\s*\S+", "password=[REDACTED]"),
        (r"passwd\s*=\s*\S+", "passwd=[REDACTED]"),
        (r"api[_-]?key\s*[=:]\s*\S+", "api_key=[REDACTED]"),
        (r"apikey\s*[=:]\s*\S+", "apikey=[REDACTED]"),
    ]

    def __init__(self):
        self.compiled = [(re.compile(p, re.IGNORECASE | re.DOTALL), r) for p, r in self.PATTERNS]

    def redact(self, text: str) -> str:
        """Redact all secret patterns from text."""
        for pattern, replacement in self.compiled:
            text = pattern.sub(replacement, text)
        return text

    def check_outbound(self, text: str) -> tuple:
        """Returns (redacted_text, was_redacted)."""
        redacted = self.redact(text)
        return redacted, redacted != text
