"""Unit tests for artifact management"""
import pytest
import asyncio
import hashlib
from pathlib import Path
from src.artifacts.manager import ArtifactManager
from src.artifacts.models import ArtifactMetadata
import tempfile


@pytest.fixture
async def artifact_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ArtifactManager()
        manager.storage_path = Path(tmpdir)
        yield manager


@pytest.mark.asyncio
async def test_store_and_get(artifact_manager):
    """Test storing and retrieving artifacts."""
    content = b"test artifact content"
    artifact_id = await artifact_manager.store(
        content=content,
        filename="test.txt",
        creator="test-agent",
        tags=["test"],
    )
    
    artifact = await artifact_manager.get(artifact_id)
    
    assert artifact is not None
    assert artifact.content == content
    assert artifact.metadata.filename == "test.txt"
    assert artifact.metadata.creator == "test-agent"
    assert "test" in artifact.metadata.tags
    assert artifact.metadata.sha256 == hashlib.sha256(content).hexdigest()


@pytest.mark.asyncio
async def test_deduplication(artifact_manager):
    """Test content-based deduplication."""
    content = b"duplicate content"
    
    id1 = await artifact_manager.store(content=content, filename="file1.txt")
    id2 = await artifact_manager.store(content=content, filename="file2.txt")
    
    # Should return same ID for identical content
    assert id1 == id2


@pytest.mark.asyncio
async def test_delete(artifact_manager):
    """Test artifact deletion."""
    artifact_id = await artifact_manager.store(
        content=b"to delete",
        filename="delete.txt",
    )
    
    # Verify exists
    artifact = await artifact_manager.get(artifact_id)
    assert artifact is not None
    
    # Delete
    result = await artifact_manager.delete(artifact_id)
    assert result is True
    
    # Verify gone
    artifact = await artifact_manager.get(artifact_id)
    assert artifact is None


@pytest.mark.asyncio
async def test_search(artifact_manager):
    """Test artifact search."""
    await artifact_manager.store(
        content=b"secret flag content",
        filename="flag.txt",
        tags=["flag", "secret"],
    )
    
    await artifact_manager.store(
        content=b"normal file",
        filename="normal.txt",
        tags=["normal"],
    )
    
    # Search by filename
    results = await artifact_manager.search("flag")
    assert len(results) == 1
    assert results[0].filename == "flag.txt"
    
    # Search by tag
    results = await artifact_manager.search("secret")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_relationships(artifact_manager):
    """Test artifact relationships."""
    id1 = await artifact_manager.store(b"parent", filename="parent.txt")
    id2 = await artifact_manager.store(b"child", filename="child.txt")
    
    result = await artifact_manager.add_relationship(id1, "derived_from", id2)
    assert result is True
    
    related = await artifact_manager.get_related(id1, "derived_from")
    assert len(related) == 1
    assert related[0].id == id2
    
    # Check reverse relationship
    reverse = await artifact_manager.get_related(id2, "reverse_derived_from")
    assert len(reverse) == 1
    assert reverse[0].id == id1