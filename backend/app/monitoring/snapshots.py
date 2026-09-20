from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Manages immutable raw content and metadata snapshots for baselines and detected changes."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.monitoring_dir

    def _get_source_dir(self, source_url_id: uuid.UUID) -> Path:
        path = self.base_dir / str(source_url_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_baseline_snapshot(
        self,
        source_url_id: uuid.UUID,
        raw_content: bytes,
        metadata: Dict[str, Any],
    ) -> Dict[str, str]:
        """Save initial baseline snapshot.
        
        Returns:
            Dict with paths to saved files and raw sha256.
        """
        source_dir = self._get_source_dir(source_url_id)
        baseline_dir = source_dir / "baseline"
        baseline_dir.mkdir(parents=True, exist_ok=True)

        content_path = baseline_dir / "response.html"
        meta_path = baseline_dir / "metadata.json"

        content_hash = hashlib.sha256(raw_content).hexdigest()

        # Update metadata with storage info
        meta_record = {
            **metadata,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "content_sha256": content_hash,
            "content_size_bytes": len(raw_content),
            "snapshot_type": "BASELINE",
        }

        with open(content_path, "wb") as f:
            f.write(raw_content)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_record, f, indent=2, ensure_ascii=False)

        return {
            "content_path": str(content_path),
            "metadata_path": str(meta_path),
            "content_sha256": content_hash,
        }

    def save_change_snapshot(
        self,
        source_url_id: uuid.UUID,
        event_id: uuid.UUID,
        raw_content: bytes,
        metadata: Dict[str, Any],
    ) -> Dict[str, str]:
        """Save immutable change snapshot tagged with the change event ID."""
        source_dir = self._get_source_dir(source_url_id)
        changes_dir = source_dir / "changes" / str(event_id)
        changes_dir.mkdir(parents=True, exist_ok=True)

        content_path = changes_dir / "response.html"
        meta_path = changes_dir / "metadata.json"

        content_hash = hashlib.sha256(raw_content).hexdigest()

        meta_record = {
            **metadata,
            "event_id": str(event_id),
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "content_sha256": content_hash,
            "content_size_bytes": len(raw_content),
            "snapshot_type": "CHANGE",
        }

        with open(content_path, "wb") as f:
            f.write(raw_content)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_record, f, indent=2, ensure_ascii=False)

        return {
            "content_path": str(content_path),
            "metadata_path": str(meta_path),
            "content_sha256": content_hash,
        }

    def get_baseline_snapshot(self, source_url_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Retrieve baseline content and metadata if present."""
        baseline_dir = self.base_dir / str(source_url_id) / "baseline"
        content_path = baseline_dir / "response.html"
        meta_path = baseline_dir / "metadata.json"

        if not content_path.exists() or not meta_path.exists():
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            with open(content_path, "rb") as f:
                content = f.read()
            return {"content": content, "metadata": meta}
        except Exception as e:
            logger.error(f"Failed to read baseline snapshot for {source_url_id}: {e}")
            return None
