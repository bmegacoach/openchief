"""
GoldBackBond RWA Connector
Wraps the Rust binary (Phase 2) or calls Solana RPC directly.
"""
import os

PROGRAM_ID = os.getenv("GOLDBACKBOND_PROGRAM_ID", "")
RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")


class GoldBackBondConnector:
    """Interface to GoldBackBond Solana program."""

    def __init__(self):
        self.program_id = PROGRAM_ID
        self.rpc_url = RPC_URL

    def is_configured(self) -> bool:
        return bool(self.program_id)

    def get_supply(self) -> dict:
        if not self.is_configured():
            return {"status": "unconfigured", "supply": None}
        return {"status": "stub", "supply": 0, "backing_value": 0}

    def get_rewards_pending(self) -> dict:
        if not self.is_configured():
            return {"status": "unconfigured", "pending": []}
        return {"status": "stub", "pending": []}

    def calculate_distribution(self, holders: list) -> dict:
        if not self.is_configured():
            return {"status": "unconfigured"}
        return {"status": "stub", "distributions": []}

    def mint_usdgb(self, amount: float, recipient: str) -> dict:
        """Requires human approval before calling."""
        if not self.is_configured():
            return {"status": "unconfigured"}
        return {"status": "stub", "tx_id": None}
