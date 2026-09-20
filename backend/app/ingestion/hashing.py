import hashlib
from pathlib import Path


def calculate_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """
    Calculate the SHA-256 hex digest of a file by streaming in chunks.

    Does not load the entire file into memory to safely support large government PDFs.
    Default chunk size is 64 KB (65,536 bytes).
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()
