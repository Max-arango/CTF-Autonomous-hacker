"""Artifact Manager"""
import asyncio
import aiofiles
import hashlib
import uuid
import mimetypes
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, BinaryIO
from datetime import datetime

from .models import Artifact, ArtifactMetadata
from ..config.settings import get_settings
from ..observability import get_logger, log_artifact_event


class ArtifactManager:
    """Manages artifact storage and retrieval."""

    def __init__(self):
        self.settings = get_settings()
        self.storage_path = Path(self.settings.paths.artifacts_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory index
        self._index: Dict[str, ArtifactMetadata] = {}
        self._lock = asyncio.Lock()

        # Load existing index
        self._load_index()

    def _load_index(self):
        """Load artifact index from disk."""
        index_file = self.storage_path / "index.json"
        if index_file.exists():
            try:
                import json
                with open(index_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        metadata = ArtifactMetadata.from_dict(item)
                        self._index[metadata.id] = metadata
            except Exception:
                pass

    async def _save_index(self):
        """Save artifact index to disk."""
        index_file = self.storage_path / "index.json"
        try:
            import json
            data = [meta.to_dict() for meta in self._index.values()]
            async with aiofiles.open(index_file, "w") as f:
                await f.write(json.dumps(data, indent=2))
        except Exception:
            pass

    async def store(
        self,
        content: bytes,
        filename: str,
        creator: str = "",
        source: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store an artifact."""
        # Compute hash
        sha256 = hashlib.sha256(content).hexdigest()

        # Check for duplicate
        async with self._lock:
            for existing in self._index.values():
                if existing.sha256 == sha256:
                    # Return existing artifact ID
                    return existing.id

        # Create metadata
        artifact_id = str(uuid.uuid4())
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        artifact_metadata = ArtifactMetadata(
            id=artifact_id,
            filename=filename,
            sha256=sha256,
            mime_type=mime_type,
            size=len(content),
            creator=creator,
            source=source,
            tags=tags or [],
            custom=metadata or {},
        )

        # Store content
        artifact_path = self.storage_path / f"{artifact_id}_{filename}"
        try:
            async with aiofiles.open(artifact_path, "wb") as f:
                await f.write(content)
        except Exception as e:
            raise RuntimeError(f"Failed to store artifact: {e}")

        # Add to index
        async with self._lock:
            self._index[artifact_id] = artifact_metadata
            await self._save_index()

        # Log event
        await log_artifact_event(
            artifact_id=artifact_id,
            event="artifact_stored",
            data={
                "filename": filename,
                "size": len(content),
                "sha256": sha256,
                "creator": creator,
            },
        )

        return artifact_id

    async def store_file(
        self,
        file_path: Path,
        creator: str = "",
        source: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store a file as artifact."""
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        return await self.store(
            content=content,
            filename=file_path.name,
            creator=creator,
            source=source,
            tags=tags,
            metadata=metadata,
        )

    async def get(self, artifact_id: str) -> Optional[Artifact]:
        """Get an artifact by ID."""
        async with self._lock:
            metadata = self._index.get(artifact_id)
            if not metadata:
                return None

        # Find file
        artifact_path = None
        for path in self.storage_path.glob(f"{artifact_id}_*"):
            artifact_path = path
            break

        if not artifact_path or not artifact_path.exists():
            return None

        async with aiofiles.open(artifact_path, "rb") as f:
            content = await f.read()

        # Verify hash
        if hashlib.sha256(content).hexdigest() != metadata.sha256:
            # Hash mismatch - artifact corrupted
            return None

        return Artifact(metadata=metadata, content=content)

    async def get_metadata(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        """Get artifact metadata without content."""
        async with self._lock:
            return self._index.get(artifact_id)

    async def get_content(self, artifact_id: str) -> Optional[bytes]:
        """Get artifact content only."""
        artifact = await self.get(artifact_id)
        return artifact.content if artifact else None

    async def delete(self, artifact_id: str) -> bool:
        """Delete an artifact."""
        async with self._lock:
            metadata = self._index.get(artifact_id)
            if not metadata:
                return False

            # Delete file
            for path in self.storage_path.glob(f"{artifact_id}_*"):
                try:
                    path.unlink()
                except Exception:
                    pass

            # Remove from index
            del self._index[artifact_id]
            await self._save_index()

            await log_artifact_event(
                artifact_id=artifact_id,
                event="artifact_deleted",
                data={"filename": metadata.filename},
            )

            return True

    async def list(
        self,
        creator: Optional[str] = None,
        tags: Optional[List[str]] = None,
        mime_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[ArtifactMetadata]:
        """List artifacts with filters."""
        async with self._lock:
            results = []
            for metadata in self._index.values():
                if creator and metadata.creator != creator:
                    continue
                if tags and not any(tag in metadata.tags for tag in tags):
                    continue
                if mime_type and metadata.mime_type != mime_type:
                    continue
                results.append(metadata)

            # Sort by timestamp descending
            results.sort(key=lambda m: m.timestamp, reverse=True)
            return results[:limit]

    async def search(self, query: str, limit: int = 100) -> List[ArtifactMetadata]:
        """Search artifacts by filename or tags."""
        async with self._lock:
            results = []
            query_lower = query.lower()
            for metadata in self._index.values():
                if query_lower in metadata.filename.lower():
                    results.append(metadata)
                elif any(query_lower in tag.lower() for tag in metadata.tags):
                    results.append(metadata)

            results.sort(key=lambda m: m.timestamp, reverse=True)
            return results[:limit]

    async def add_relationship(
        self,
        artifact_id: str,
        relationship_type: str,
        related_artifact_id: str,
    ) -> bool:
        """Add a relationship between artifacts."""
        async with self._lock:
            metadata = self._index.get(artifact_id)
            if not metadata:
                return False

            if relationship_type not in metadata.relationships:
                metadata.relationships[relationship_type] = []
            if related_artifact_id not in metadata.relationships[relationship_type]:
                metadata.relationships[relationship_type].append(related_artifact_id)

            # Add reverse relationship
            reverse_type = f"reverse_{relationship_type}"
            related_metadata = self._index.get(related_artifact_id)
            if related_metadata:
                if reverse_type not in related_metadata.relationships:
                    related_metadata.relationships[reverse_type] = []
                if artifact_id not in related_metadata.relationships[reverse_type]:
                    related_metadata.relationships[reverse_type].append(artifact_id)

            await self._save_index()
            return True

    async def get_related(
        self,
        artifact_id: str,
        relationship_type: Optional[str] = None,
    ) -> List[ArtifactMetadata]:
        """Get related artifacts."""
        async with self._lock:
            metadata = self._index.get(artifact_id)
            if not metadata:
                return []

            related_ids = []
            if relationship_type:
                related_ids = metadata.relationships.get(relationship_type, [])
            else:
                for rel_list in metadata.relationships.values():
                    related_ids.extend(rel_list)

            results = []
            for rid in related_ids:
                related = self._index.get(rid)
                if related:
                    results.append(related)

            return results

    async def get_stats(self) -> Dict[str, Any]:
        """Get artifact storage statistics."""
        async with self._lock:
            total_size = sum(m.size for m in self._index.values())
            mime_types = {}
            for m in self._index.values():
                mime_types[m.mime_type] = mime_types.get(m.mime_type, 0) + 1

            return {
                "total_artifacts": len(self._index),
                "total_size_bytes": total_size,
                "mime_types": mime_types,
                "storage_path": str(self.storage_path),
            }


# Global artifact manager
_artifact_manager: Optional[ArtifactManager] = None


async def get_artifact_manager() -> ArtifactManager:
    """Get global artifact manager."""
    global _artifact_manager
    if _artifact_manager is None:
        _artifact_manager = ArtifactManager()
    return _artifact_manager