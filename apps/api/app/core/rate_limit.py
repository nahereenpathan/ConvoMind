"""Rate limiting module using slowapi with Redis storage and automatic test-mode bypass."""

import os
import sys
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

# Determine if the process is running under pytest or testing environment
is_testing = (
    "pytest" in sys.modules
    or (len(sys.argv) > 0 and "pytest" in sys.argv[0])
    or bool(os.environ.get("PYTEST_CURRENT_TEST"))
    or settings.ENVIRONMENT in ("testing", "test")
)

def _get_storage_uri() -> str:
    """Safely obtain storage URI for rate limiter, falling back to memory if Redis host is unreachable."""
    redis_url = settings.REDIS_URL
    if "redis://" in redis_url or "rediss://" in redis_url:
        try:
            import socket
            parts = redis_url.split("://")[1].split("/")[0].split("@")[-1].split(":")
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 6379
            if host == "redis":
                try:
                    host = socket.gethostbyname("redis")
                except socket.gaierror:
                    return "memory://"
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            s.connect((host, port))
            s.close()
            return redis_url
        except Exception:
            return "memory://"
    return redis_url


# Initialize slowapi limiter using client IP address with memory fallback for Redis resilience
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri=_get_storage_uri(),
    in_memory_fallback_enabled=True,
    enabled=not is_testing,
)


