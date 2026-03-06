import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_job_heartbeat_calls_post_heartbeat():
    mock_bot = MagicMock()
    with patch("cron.jobs.heartbeat.post_heartbeat", new_callable=AsyncMock) as mock_hb:
        from cron.jobs.heartbeat import job_heartbeat
        await job_heartbeat(mock_bot)
        mock_hb.assert_called_once_with(mock_bot)
