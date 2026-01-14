"""Heartbeat manager for agent registration."""

import asyncio
import logging
from contextlib import suppress
from typing import Optional

from agentcore.registry.client import RegistryClient

logger = logging.getLogger(__name__)


class HeartbeatManager:
    """Background task to keep agent alive in registry."""

    def __init__(
        self,
        registry: RegistryClient,
        agent_id: str,
        interval: int = 10,
    ):
        self._registry = registry
        self._agent_id = agent_id
        self._interval = interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the heartbeat background task."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Started heartbeat for agent {self._agent_id}")

    async def stop(self) -> None:
        """Stop the heartbeat."""
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        logger.info(f"Stopped heartbeat for agent {self._agent_id}")

    async def _loop(self) -> None:
        """Continuous heartbeat loop."""
        while self._running:
            try:
                await self._registry.heartbeat(self._agent_id)
                logger.debug(f"Heartbeat sent for agent {self._agent_id}")
            except Exception as e:
                logger.error(f"Heartbeat failed for {self._agent_id}: {e}")
                # Continue trying - Redis might recover

            await asyncio.sleep(self._interval)
