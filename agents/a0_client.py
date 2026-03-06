"""
Single HTTP bridge to Agent Zero (localhost:5000).
All OpenChief -> A0 communication flows through here.
"""
import logging
import os
import aiohttp

_DEFAULT_BASE = "http://localhost:5000"
_log = logging.getLogger(__name__)


def _headers() -> dict:
    key = os.getenv("A0_API_KEY", "")
    if key:
        return {"X-API-KEY": key}
    return {}


async def ask_a0(prompt: str, context_id: str, system_role: str = "") -> str:
    """Send a prompt to Agent Zero and return the response text."""
    base = os.getenv("A0_BASE_URL", _DEFAULT_BASE)
    payload: dict = {"message": prompt, "context_id": context_id}
    if system_role:
        payload["system"] = system_role
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base}/api_message",
            json=payload,
            headers=_headers(),
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            resp.raise_for_status()
            try:
                data = await resp.json(content_type=None)
            except Exception as exc:
                raise ValueError(f"A0 returned non-JSON response: {exc}") from exc
            return data.get("response", "")


async def send_directive(text: str, context_ids: list[str]) -> None:
    """Inject a Master Chief directive into every supplied A0 context."""
    wrapped = f"[MASTER CHIEF DIRECTIVE]\n{text}"
    for cid in context_ids:
        try:
            await ask_a0(wrapped, cid)
        except Exception as exc:
            _log.warning("send_directive failed for context %s: %s", cid, exc)


async def ping() -> bool:
    """Return True if Agent Zero responds on /health."""
    try:
        base = os.getenv("A0_BASE_URL", _DEFAULT_BASE)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base}/health",
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return resp.status == 200
    except Exception:
        return False
