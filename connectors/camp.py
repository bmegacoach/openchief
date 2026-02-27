"""
CAMP IDL Marketplace Connector
Handles inscription listings, bids, and batch distributions.
"""
import os

PROGRAM_ID = os.getenv("CAMP_IDL_PROGRAM_ID", "")


class CampConnector:
    """Interface to CAMP IDL Solana program."""

    def __init__(self):
        self.program_id = PROGRAM_ID

    def is_configured(self) -> bool:
        return bool(self.program_id)

    def get_listings(self, limit: int = 20) -> list:
        if not self.is_configured():
            return []
        return []

    def get_floor_price(self) -> dict:
        if not self.is_configured():
            return {"status": "unconfigured", "floor": None}
        return {"status": "stub", "floor": None}

    def submit_bid(self, inscription_id: str, amount: float, bidder: str) -> dict:
        """Requires approval before calling."""
        if not self.is_configured():
            return {"status": "unconfigured"}
        return {"status": "stub", "bid_id": None}

    def batch_distribute(self, recipients: list, amounts: list) -> dict:
        """Requires approval before calling."""
        if not self.is_configured():
            return {"status": "unconfigured"}
        return {"status": "stub", "batch_id": None}
