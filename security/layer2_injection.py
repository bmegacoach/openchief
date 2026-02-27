import re


class Layer2Injection:
    """
    Layer 2 Security: Prompt Injection Defense.
    Scans incoming messages for injection patterns and assigns risk scores.
    HIGH risk = block + require human approval.
    MEDIUM risk = log + proceed with caution.
    LOW risk = proceed normally.
    """

    HIGH_RISK_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"you\s+are\s+now\s+(dan|gpt|jailbreak|unrestricted|free)",
        r"(forget|override|bypass)\s+(your\s+)?(instructions|rules|guidelines|restrictions|constraints)",
        r"(act|behave|respond)\s+as\s+(if\s+you\s+(are|have)\s+)?no\s+restrictions",
        r"pretend\s+you\s+(are|have|don.t\s+have)\s+(no\s+restrictions|different\s+rules)",
        r"system\s+prompt\s*:",
        r"<\s*system\s*>",
        r"\[SYSTEM\]",
        r"new\s+instructions?\s*:",
        r"admin\s+override",
        r"developer\s+mode",
        r"send\s+(all\s+)?(funds|money|crypto|sol|eth|btc)",
        r"transfer\s+(all\s+)?funds",
        r"drain\s+(the\s+)?(wallet|treasury|vault)",
    ]

    MEDIUM_RISK_PATTERNS = [
        r"act\s+as\s+a\s+different",
        r"without\s+any\s+rules",
        r"no\s+ethical\s+guidelines",
        r"hypothetically\s+speaking.*no\s+rules",
        r"roleplay\s+as.*no\s+restrictions",
        r"jailbreak",
        r"token\s+manipulation",
        r"prompt\s+injection",
        r"reveal\s+(your\s+)?(system\s+prompt|instructions|api\s+key)",
        r"what\s+are\s+your\s+(exact\s+)?(instructions|system\s+prompt)",
    ]

    def __init__(self):
        self.high_compiled = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in self.HIGH_RISK_PATTERNS]
        self.medium_compiled = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in self.MEDIUM_RISK_PATTERNS]

    def scan(self, text: str) -> str:
        """Scan text and return risk level: HIGH, MEDIUM, or LOW."""
        for pattern in self.high_compiled:
            if pattern.search(text):
                return "HIGH"
        for pattern in self.medium_compiled:
            if pattern.search(text):
                return "MEDIUM"
        return "LOW"

    def scan_detail(self, text: str) -> dict:
        """Return full scan result with matched patterns."""
        matched_high = [p.pattern for p in self.high_compiled if p.search(text)]
        matched_medium = [p.pattern for p in self.medium_compiled if p.search(text)]
        if matched_high:
            level = "HIGH"
        elif matched_medium:
            level = "MEDIUM"
        else:
            level = "LOW"
        return {
            "risk_level": level,
            "matched_high": matched_high,
            "matched_medium": matched_medium,
        }
