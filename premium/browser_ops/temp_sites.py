"""
Temp Site Provisioner — Premium Module
Feature flag: ENABLE_BROWSER_OPS=true
Spins up temporary landing pages for campaigns.
Phase 2: Integrate with Vercel/Netlify API for real provisioning.
"""
import os
import uuid
from datetime import datetime, timezone
from event_logging.event_logger import EventLogger

ENABLED = os.getenv("ENABLE_BROWSER_OPS", "false").lower() == "true"
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN", "")

logger = EventLogger()

# In-memory registry (Phase 2: persist to Supabase)
_sites: dict = {}


class TempSiteProvisioner:
    """Provision and manage temporary campaign landing pages."""

    def __init__(self):
        self.enabled = ENABLED

    def is_configured(self) -> bool:
        return self.enabled

    def provision(self, name: str, template: str = "default") -> dict:
        """Provision a new temp site. Returns site metadata."""
        if not self.enabled:
            return {"status": "unconfigured"}
        site_id = str(uuid.uuid4())[:8]
        site = {
            "id": site_id,
            "name": name,
            "template": template,
            "url": f"https://temp-{site_id}.openchief.app",  # stub
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "stub",
        }
        _sites[site_id] = site
        logger.log_event("temp_site_provisioned", {"site_id": site_id, "name": name})
        return {"status": "ok", "site": site}

    def list_sites(self) -> list:
        return list(_sites.values())

    def deprovision(self, site_id: str) -> dict:
        if site_id not in _sites:
            return {"status": "not_found"}
        del _sites[site_id]
        logger.log_event("temp_site_deprovisioned", {"site_id": site_id})
        return {"status": "ok"}
