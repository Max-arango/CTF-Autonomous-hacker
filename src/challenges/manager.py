"""Challenge Manager"""
import asyncio
import ipaddress
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..orchestrator.models import Challenge, ChallengeScope
from ..artifacts import ArtifactManager, get_artifact_manager
from ..config.settings import get_settings
from ..observability import get_logger


class ChallengeManager:
    """Manages challenge storage and retrieval."""

    def __init__(self):
        self.settings = get_settings()
        self.storage_path = Path(self.settings.paths.workspace_path) / "challenges"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._index: Dict[str, Challenge] = {}
        self._lock = asyncio.Lock()

        self._load_index()

    def _load_index(self):
        """Load challenge index."""
        index_file = self.storage_path / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        # Load scope if present
                        scope_data = item.get("scope", {})
                        scope = ChallengeScope.from_dict(scope_data) if scope_data else ChallengeScope(
                            challenge_id=item.get("id", "")
                        )
                        item["scope"] = scope
                        
                        challenge = Challenge(**item)
                        self._index[challenge.id] = challenge
            except Exception:
                pass

    async def _save_index(self):
        """Save challenge index."""
        index_file = self.storage_path / "index.json"
        try:
            data = []
            for challenge in self._index.values():
                scope_dict = challenge.scope.to_dict()
                challenge_dict = {
                    "id": challenge.id,
                    "name": challenge.name,
                    "description": challenge.description,
                    "category": [c.value for c in challenge.category],
                    "challenge_type": challenge.challenge_type.value,
                    "files": challenge.files,
                    "target_info": challenge.target_info,
                    "credentials": challenge.credentials,
                    "constraints": challenge.constraints,
                    "flag_format": challenge.flag_format,
                    "metadata": challenge.metadata,
                    "created_at": challenge.created_at.isoformat(),
                    "updated_at": challenge.updated_at.isoformat(),
                    "scope": scope_dict,
                }
                data.append(challenge_dict)
            
            async with asyncio.Lock():
                import aiofiles
                async with aiofiles.open(index_file, "w") as f:
                    await f.write(json.dumps(data, indent=2))
        except Exception:
            pass

    async def store(self, challenge: Challenge) -> str:
        """Store a challenge."""
        async with self._lock:
            self._index[challenge.id] = challenge
            await self._save_index()
        return challenge.id

    async def get(self, challenge_id: str) -> Optional[Challenge]:
        """Get a challenge."""
        return self._index.get(challenge_id)

    async def list(self) -> List[Challenge]:
        """List all challenges."""
        return list(self._index.values())

    async def delete(self, challenge_id: str) -> bool:
        """Delete a challenge."""
        async with self._lock:
            if challenge_id in self._index:
                del self._index[challenge_id]
                await self._save_index()
                return True
            return False

    async def add_file(self, challenge_id: str, artifact_id: str):
        """Add a file to challenge."""
        challenge = self._index.get(challenge_id)
        if challenge and artifact_id not in challenge.files:
            challenge.files.append(artifact_id)
            challenge.updated_at = datetime.utcnow()
            await self._save_index()

    async def import_challenge(self, path: Path) -> Challenge:
        """Import challenge from file/directory."""
        artifact_manager = await get_artifact_manager()

        if path.is_file():
            # Archive file - extract
            artifact_id = await artifact_manager.store_file(path)
            challenge = Challenge(
                name=path.stem,
                description=f"Imported from {path.name}",
                files=[artifact_id],
            )
        else:
            # Directory - store each file
            artifact_ids = []
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    artifact_id = await artifact_manager.store_file(file_path)
                    artifact_ids.append(artifact_id)

            challenge = Challenge(
                name=path.name,
                description=f"Imported from directory {path}",
                files=artifact_ids,
            )

        await self.store(challenge)
        return challenge

    def get_scope(self, challenge_id: str) -> Optional[ChallengeScope]:
        """Get challenge scope."""
        challenge = self._index.get(challenge_id)
        if challenge:
            return challenge.scope
        return None