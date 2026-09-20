"""
JanSetu - Day 28: Gold Dataset Hashing & Staleness Utilities.

Computes SHA-256 checksums over source artifacts, audio recordings,
scheme versions, and dataset manifests to guarantee immutability
and detect staleness.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Union


def compute_file_sha256(file_path: Union[str, Path]) -> str:
    """Computes streaming SHA-256 hex digest for a file."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Cannot compute SHA-256: file not found at '{path}'")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# Backward-compatible alias
compute_sha256 = compute_file_sha256


def compute_bytes_sha256(data: bytes) -> str:
    """Computes SHA-256 hex digest for bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_canonical_json_sha256(obj: Any) -> str:
    """
    Computes deterministic SHA-256 hex digest for any JSON-serializable structure
    using canonical UTF-8 JSON encoding with sorted keys and compact separators.
    """
    canonical_bytes = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def compute_manifest_hash(manifest_dict: Dict[str, Any]) -> str:
    """
    Computes deterministic manifest SHA-256 across all registered cases
    and metadata, ignoring any existing 'dataset_sha256' field.
    """
    filtered = {k: v for k, v in manifest_dict.items() if k != "dataset_sha256"}
    return compute_canonical_json_sha256(filtered)


def check_artifact_staleness(file_path: Union[str, Path], recorded_sha256: str) -> bool:
    """
    Returns True if the physical file on disk has changed from its recorded SHA-256 hash.
    Returns True (stale/missing) if the file does not exist.
    """
    path = Path(file_path)
    if not path.is_file():
        return True
    current_hash = compute_file_sha256(path)
    return current_hash.lower() != recorded_sha256.lower()
