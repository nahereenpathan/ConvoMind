"""Abstract interface for native real-time media providers (LiveKit, etc.)."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class MediaProviderError(Exception):
    """Base exception for real-time media provider errors."""
    pass


class BaseMediaProvider(ABC):
    """Abstract interface for SFU media room token generation and lifecycle control."""

    @abstractmethod
    async def generate_room_token(
        self,
        room_name: str,
        participant_identity: str,
        participant_name: str,
        is_host: bool = False,
        ttl_seconds: int = 7200,
    ) -> str:
        """Generate a secure, short-lived JWT media token for client room join."""
        pass

    @abstractmethod
    async def create_room(
        self,
        room_name: str,
        empty_timeout: int = 300,
        max_participants: int = 50,
    ) -> Dict[str, Any]:
        """Initialize or verify a room on the media infrastructure."""
        pass

    @abstractmethod
    async def end_room(self, room_name: str) -> bool:
        """Close room and disconnect all participants on the media server."""
        pass
