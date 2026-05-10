"""Helper functions for workflow routes."""

import hashlib


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content.

    Args:
        content: File content as bytes.

    Returns:
        Hex string of SHA-256 hash.
    """
    return hashlib.sha256(content).hexdigest()
