"""Mock real-time media provider for development and testing."""

import hashlib
import time
from typing import Any, Dict, Optional
from app.services.media.base import BaseMediaProvider


class MockMediaProvider(BaseMediaProvider):
    """Development mock provider generating deterministic test media tokens."""

    def __init__(self, ws_url: str = "wss://mock.livekit.cloud"):
        self.ws_url = ws_url

    async def generate_room_token(
        self,
        room_name: str,
        participant_identity: str,
        participant_name: str,
        is_host: bool = False,
        ttl_seconds: int = 7200,
    ) -> str:
        """Generate mock signed token."""
        digest = hashlib.sha256(
            f"{room_name}:{participant_identity}:{is_host}:{time.time()}".encode("utf-8")
        ).hexdigest()[:32]
        return f"mock_lk_token_{digest}"

    async def create_room(
        self,
        room_name: str,
        empty_timeout: int = 300,
        max_participants: int = 50,
    ) -> Dict[str, Any]:
        """Mock room creation."""
        return {
            "room_name": room_name,
            "status": "created",
            "provider": "mock",
            "max_participants": max_participants,
        }

    async def end_room(self, room_name: str) -> bool:
        """Mock room termination."""
        return True
