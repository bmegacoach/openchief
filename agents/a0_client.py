"""
Single HTTP bridge to Agent Zero (localhost:50001).
All OpenChief -> A0 communication flows through here.
"""
import os
import aiohttp

_DEFAULT_BASE = "http://localhost:50001"


def _headers() -> dict:
    key = os.getenv("A0_API_KEY", "")
    if key:
        return {"Authorization": f"Bearer {key}"}
    return {}


async def ask_a0(prompt: str, context_id: str, system_role: str = "") -> str:
    """Send a prompt to Agent Zero and return the response text."""
    base = os.getenv("A0_BASE_URL", _DEFAULT_BASE)
    payload: dict = {"message": prompt, "context_id": context_id}
    if system_role:
        payload["system"] = system_role
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base}/agent/dispatch",
            json=payload,
            headers=_headers(),
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("response", "")


async def send_directive(text: str, context_ids: list) -> None:
    """Inject a Master Chief directive into every supplied A0 context."""
    wrapped = f"[MASTER CHIEF DIRECTIVE]\n{text}"
    for cid in context_ids:
        try:
            await ask_a0(wrapped, cid)
        except Exception:
            pass  # best-effort


async def ping() -> bool:
    """Return True if Agent Zero responds on /health."""
    try:
        base = os.getenv("A0_BASE_URL", _DEFAULT_BASE)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base}/health",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return resp.status == 200
    except Exception:
        return False
