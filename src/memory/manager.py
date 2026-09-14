"""Memory Manager"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

from .models import MemoryEntry, MemoryType, MemoryLayer, Finding, Experiment
from ..config.settings import get_settings
from ..observability import get_logger


class MemoryManager:
    """Manages multi-layer memory for agents."""

    def __init__(self):
        self.settings = get_settings()

        # In-memory stores (in production, these would be backed by Redis/DB)
        self._short_term: Dict[str, MemoryEntry] = {}      # Current task
        self._task_memory: Dict[str, MemoryEntry] = {}     # Current challenge
        self._long_term: Dict[str, MemoryEntry] = {}       # Cross-challenge patterns

        # Indexes for fast lookup
        self._by_agent: Dict[str, Set[str]] = defaultdict(set)
        self._by_challenge: Dict[str, Set[str]] = defaultdict(set)
        self._by_type: Dict[MemoryType, Set[str]] = defaultdict(set)
        self._by_layer: Dict[MemoryLayer, Set[str]] = defaultdict(set)
        self._by_tag: Dict[str, Set[str]] = defaultdict(set)

        # Experiments
        self._experiments: Dict[str, Experiment] = {}
        self._experiments_by_hypothesis: Dict[str, List[str]] = defaultdict(list)

        # Locks
        self._lock = asyncio.Lock()

        # TTL settings
        self._short_term_ttl = timedelta(hours=1)
        self._task_ttl = timedelta(days=7)
        self._long_term_ttl = timedelta(days=90)

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry."""
        async with self._lock:
            # Determine storage layer
            store = self._get_store(entry.layer)
            store[entry.id] = entry

            # Update indexes
            self._by_agent[entry.agent_id].add(entry.id)
            if entry.challenge_id:
                self._by_challenge[entry.challenge_id].add(entry.id)
            self._by_type[entry.type].add(entry.id)
            self._by_layer[entry.layer].add(entry.id)
            for tag in entry.tags:
                self._by_tag[tag].add(entry.id)

            return entry.id

    async def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by ID."""
        async with self._lock:
            for store in [self._short_term, self._task_memory, self._long_term]:
                if entry_id in store:
                    entry = store[entry_id]
                    entry.accessed_at = datetime.utcnow()
                    entry.access_count += 1
                    return entry
            return None

    async def query(
        self,
        agent_id: Optional[str] = None,
        challenge_id: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        layer: Optional[MemoryLayer] = None,
        tags: Optional[List[str]] = None,
        content_search: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> List[MemoryEntry]:
        """Query memory entries."""
        async with self._lock:
            # Start with all entries
            candidate_ids = set()
            first = True

            # Filter by agent
            if agent_id:
                ids = self._by_agent.get(agent_id, set())
                candidate_ids = ids if first else candidate_ids & ids
                first = False

            # Filter by challenge
            if challenge_id:
                ids = self._by_challenge.get(challenge_id, set())
                candidate_ids = ids if first else candidate_ids & ids
                first = False

            # Filter by type
            if memory_type:
                ids = self._by_type.get(memory_type, set())
                candidate_ids = ids if first else candidate_ids & ids
                first = False

            # Filter by layer
            if layer:
                ids = self._by_layer.get(layer, set())
                candidate_ids = ids if first else candidate_ids & ids
                first = False

            # Filter by tags
            if tags:
                for tag in tags:
                    ids = self._by_tag.get(tag, set())
                    candidate_ids = ids if first else candidate_ids & ids
                    first = False

            # If no filters, get all
            if first:
                candidate_ids = set(self._short_term.keys()) | set(self._task_memory.keys()) | set(self._long_term.keys())

            # Retrieve entries
            entries = []
            for entry_id in candidate_ids:
                entry = await self.retrieve(entry_id)
                if entry:
                    # Filter by confidence
                    if entry.confidence < min_confidence:
                        continue
                    # Filter by content search
                    if content_search and content_search.lower() not in entry.content.lower():
                        continue
                    entries.append(entry)

            # Sort by confidence and recency
            entries.sort(key=lambda e: (e.confidence, e.created_at), reverse=True)

            return entries[:limit]

    async def store_finding(self, finding: Finding) -> str:
        """Store a finding."""
        entry = finding.to_memory_entry()
        return await self.store(entry)

    async def get_findings(
        self,
        challenge_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        finding_type: Optional[str] = None,
    ) -> List[Finding]:
        """Get findings."""
        entries = await self.query(
            challenge_id=challenge_id,
            agent_id=agent_id,
            memory_type=MemoryType(finding_type) if finding_type else None,
            layer=MemoryLayer.TASK,
        )

        findings = []
        for entry in entries:
            findings.append(Finding(
                id=entry.id,
                agent_id=entry.agent_id,
                challenge_id=entry.challenge_id,
                type=entry.type.value,
                title=entry.title,
                content=entry.content,
                confidence=entry.confidence,
                related_findings=entry.related_entries,
                artifacts=entry.artifacts,
                commands=entry.commands,
                timestamp=entry.created_at,
                metadata=entry.metadata,
            ))
        return findings

    async def store_experiment(self, experiment: Experiment) -> str:
        """Store an experiment."""
        async with self._lock:
            self._experiments[experiment.id] = experiment
            self._experiments_by_hypothesis[experiment.hypothesis].append(experiment.id)
            return experiment.id

    async def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get an experiment."""
        return self._experiments.get(experiment_id)

    async def get_experiments_for_hypothesis(self, hypothesis: str) -> List[Experiment]:
        """Get all experiments for a hypothesis."""
        ids = self._experiments_by_hypothesis.get(hypothesis, [])
        return [self._experiments[id] for id in ids if id in self._experiments]

    async def has_failed_experiment(self, hypothesis: str, conditions: Dict[str, Any]) -> bool:
        """Check if an experiment with same hypothesis and conditions already failed."""
        experiments = await self.get_experiments_for_hypothesis(hypothesis)
        for exp in experiments:
            if exp.status == "failed" and exp.metadata.get("conditions") == conditions:
                return True
        return False

    async def promote_to_task_memory(self, entry_id: str):
        """Promote short-term memory to task memory."""
        async with self._lock:
            if entry_id in self._short_term:
                entry = self._short_term.pop(entry_id)
                entry.layer = MemoryLayer.TASK
                entry.updated_at = datetime.utcnow()
                self._task_memory[entry_id] = entry
                self._by_layer[MemoryLayer.SHORT_TERM].discard(entry_id)
                self._by_layer[MemoryLayer.TASK].add(entry_id)

    async def promote_to_long_term(self, entry_id: str):
        """Promote task memory to long-term memory."""
        async with self._lock:
            if entry_id in self._task_memory:
                entry = self._task_memory.pop(entry_id)
                entry.layer = MemoryLayer.LONG_TERM
                entry.updated_at = datetime.utcnow()
                self._long_term[entry_id] = entry
                self._by_layer[MemoryLayer.TASK].discard(entry_id)
                self._by_layer[MemoryLayer.LONG_TERM].add(entry_id)

    async def cleanup_expired(self):
        """Clean up expired entries."""
        async with self._lock:
            now = datetime.utcnow()

            # Clean short-term
            expired = [
                eid for eid, entry in self._short_term.items()
                if now - entry.created_at > self._short_term_ttl
            ]
            for eid in expired:
                self._remove_entry(eid, self._short_term)

            # Clean task memory
            expired = [
                eid for eid, entry in self._task_memory.items()
                if now - entry.created_at > self._task_ttl
            ]
            for eid in expired:
                self._remove_entry(eid, self._task_memory)

            # Clean long-term (keep high-confidence lessons)
            expired = [
                eid for eid, entry in self._long_term.items()
                if now - entry.created_at > self._long_term_ttl and entry.confidence < 0.8
            ]
            for eid in expired:
                self._remove_entry(eid, self._long_term)

    def _remove_entry(self, entry_id: str, store: Dict[str, MemoryEntry]):
        """Remove entry from store and indexes."""
        if entry_id in store:
            entry = store.pop(entry_id)
            self._by_agent[entry.agent_id].discard(entry_id)
            if entry.challenge_id:
                self._by_challenge[entry.challenge_id].discard(entry_id)
            self._by_type[entry.type].discard(entry_id)
            self._by_layer[entry.layer].discard(entry_id)
            for tag in entry.tags:
                self._by_tag[tag].discard(entry_id)

    def _get_store(self, layer: MemoryLayer) -> Dict[str, MemoryEntry]:
        if layer == MemoryLayer.SHORT_TERM:
            return self._short_term
        elif layer == MemoryLayer.TASK:
            return self._task_memory
        else:
            return self._long_term

    async def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        async with self._lock:
            return {
                "short_term_count": len(self._short_term),
                "task_memory_count": len(self._task_memory),
                "long_term_count": len(self._long_term),
                "total_entries": len(self._short_term) + len(self._task_memory) + len(self._long_term),
                "experiments_count": len(self._experiments),
                "agents_with_memory": len(self._by_agent),
                "challenges_with_memory": len(self._by_challenge),
            }


# Global memory manager
_memory_manager: Optional[MemoryManager] = None


async def get_memory_manager() -> MemoryManager:
    """Get global memory manager."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager