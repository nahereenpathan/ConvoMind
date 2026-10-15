"""Storage service abstraction and local disk storage backend."""

import hashlib
import os
import shutil
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from fastapi import UploadFile

from app.core.config import settings


class FileSizeExceededError(Exception):
    """Raised when an uploaded file exceeds the allowed size limit."""

    def __init__(self, message: str, max_size_bytes: int):
        super().__init__(message)
        self.max_size_bytes = max_size_bytes


class StorageBackend(ABC):
    """Abstract interface for file storage backends (Local, S3, MinIO, etc.)."""

    @abstractmethod
    async def save_file(
        self,
        file: UploadFile,
        storage_key: str,
        max_size_bytes: int,
    ) -> Tuple[int, str]:
        """Stream an uploaded file to storage.

        Args:
            file: FastAPI UploadFile stream.
            storage_key: Normalized storage path/key.
            max_size_bytes: Maximum allowed bytes.

        Returns:
            Tuple of (file_size_bytes, sha256_checksum).

        Raises:
            FileSizeExceededError: If the file exceeds max_size_bytes.
            ValueError: If path traversal or invalid key detected.
        """
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """Delete a file from storage by its storage key."""
        pass

    @abstractmethod
    def file_exists(self, storage_key: str) -> bool:
        """Check whether a file exists at the given storage key."""
        pass

    @abstractmethod
    def get_file_path(self, storage_key: str) -> str:
        """Resolve the local filesystem path for a storage key.

        Raises ValueError if the backend is non-local or the path is invalid.
        """
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend with chunked streaming and traversal protection."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.realpath(base_dir or settings.STORAGE_PATH)
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve_path(self, storage_key: str) -> str:
        """Sanitize and safely resolve absolute filesystem path inside base_dir."""
        if not storage_key or not storage_key.strip():
            raise ValueError("Storage key cannot be empty")

        # Normalize slashes and clean up relative path components
        clean_key = storage_key.replace("\\", "/").strip("/")
        parts = clean_key.split("/")
        if any(part in ("..", ".", "") for part in parts):
            raise ValueError("Path traversal attempt detected in storage key")

        full_path = os.path.realpath(os.path.join(self.base_dir, *parts))
        common = os.path.commonpath([self.base_dir, full_path])

        if common != self.base_dir:
            raise ValueError(f"Path traversal detected: {storage_key} escapes base directory")

        return full_path

    async def save_file(
        self,
        file: UploadFile,
        storage_key: str,
        max_size_bytes: int,
    ) -> Tuple[int, str]:
        """Stream uploaded file to local disk in 64KB chunks and compute SHA-256."""
        full_path = self._resolve_path(storage_key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        hasher = hashlib.sha256()
        total_bytes = 0
        chunk_size = 65536  # 64 KB

        try:
            with open(full_path, "wb") as destination:
                while chunk := await file.read(chunk_size):
                    total_bytes += len(chunk)
                    if total_bytes > max_size_bytes:
                        # Abort immediately, close file, delete incomplete artifact
                        destination.close()
                        if os.path.exists(full_path):
                            os.remove(full_path)
                        raise FileSizeExceededError(
                            f"Uploaded file exceeds maximum permitted size of {max_size_bytes} bytes",
                            max_size_bytes=max_size_bytes,
                        )
                    hasher.update(chunk)
                    destination.write(chunk)
        except Exception:
            # Clean up partial file on any exception
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except OSError:
                    pass
            raise

        checksum = hasher.hexdigest()
        return total_bytes, checksum

    async def delete_file(self, storage_key: str) -> bool:
        """Safely delete file from local disk."""
        try:
            full_path = self._resolve_path(storage_key)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                os.remove(full_path)
                # Attempt to clean up empty parent directories up to base_dir
                parent = os.path.dirname(full_path)
                while parent != self.base_dir and os.path.commonpath([self.base_dir, parent]) == self.base_dir:
                    try:
                        if not os.listdir(parent):
                            os.rmdir(parent)
                            parent = os.path.dirname(parent)
                        else:
                            break
                    except OSError:
                        break
                return True
            return False
        except (ValueError, OSError):
            return False

    def file_exists(self, storage_key: str) -> bool:
        """Check if file exists at local path."""
        try:
            full_path = self._resolve_path(storage_key)
            return os.path.exists(full_path) and os.path.isfile(full_path)
        except ValueError:
            return False

    def get_file_path(self, storage_key: str) -> str:
        """Return safe absolute path to file on disk."""
        return self._resolve_path(storage_key)


_storage_backend: Optional[StorageBackend] = None


def get_storage_service() -> StorageBackend:
    """Singleton getter for configured storage backend."""
    global _storage_backend
    if _storage_backend is None:
        if settings.STORAGE_BACKEND == "local":
            _storage_backend = LocalStorageBackend(base_dir=settings.STORAGE_PATH)
        else:
            # Future extension point for S3/MinIO
            _storage_backend = LocalStorageBackend(base_dir=settings.STORAGE_PATH)
    return _storage_backend
