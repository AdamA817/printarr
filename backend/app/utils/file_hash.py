"""File hashing utilities for deduplication (DEC-041).

Provides stream-based SHA-256 hash computation to avoid loading entire files into memory.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

# Default chunk size for streaming hash computation
DEFAULT_CHUNK_SIZE = 8192  # 8KB - good balance of speed and memory


def compute_file_hash_sync(
    file_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Compute SHA-256 hash of a file synchronously (stream-based).

    This function streams the file in chunks to avoid loading the entire
    file into memory, making it suitable for large 3D model files.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Size of chunks to read at a time (default 8KB).

    Returns:
        64-character lowercase hex string of the SHA-256 hash.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        PermissionError: If the file can't be read.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


async def compute_file_hash(
    file_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Compute SHA-256 hash of a file asynchronously (stream-based).

    Runs the hash computation in a thread pool executor to avoid blocking
    the async event loop during I/O.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Size of chunks to read at a time (default 8KB).

    Returns:
        64-character lowercase hex string of the SHA-256 hash.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        PermissionError: If the file can't be read.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        compute_file_hash_sync,
        file_path,
        chunk_size,
    )


async def compute_file_hashes_batch(
    file_paths: list[Path],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict[Path, str]:
    """Compute SHA-256 hashes for multiple files in parallel.

    Useful for bulk import operations where many files need to be hashed.

    Args:
        file_paths: List of paths to files to hash.
        chunk_size: Size of chunks to read at a time (default 8KB).

    Returns:
        Dict mapping file paths to their SHA-256 hashes.
        Files that couldn't be hashed are not included in the result.
    """
    results: dict[Path, str] = {}

    async def hash_one(path: Path) -> tuple[Path, str | None]:
        try:
            hash_value = await compute_file_hash(path, chunk_size)
            return (path, hash_value)
        except (FileNotFoundError, PermissionError, OSError):
            return (path, None)

    tasks = [hash_one(path) for path in file_paths]
    completed = await asyncio.gather(*tasks, return_exceptions=True)

    for item in completed:
        if isinstance(item, tuple) and item[1] is not None:
            results[item[0]] = item[1]

    return results
