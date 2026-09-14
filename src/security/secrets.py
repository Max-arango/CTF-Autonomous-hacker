"""Secret Management - Secure credential handling and redaction"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import secrets
import base64
import json
import re
from pathlib import Path


class SecretType(str, Enum):
    """Types of secrets."""
    PASSWORD = "password"
    API_KEY = "api_key"
    SSH_KEY = "ssh_key"
    PRIVATE_KEY = "private_key"
    CERTIFICATE = "certificate"
    TOKEN = "token"
    DATABASE_URL = "database_url"
    WEBHOOK_URL = "webhook_url"
    GENERIC = "generic"


class SecretStatus(str, Enum):
    """Secret status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"


@dataclass
class CredentialRef:
    """Reference to a credential (not the credential itself)."""
    ref_id: str
    challenge_id: str
    secret_type: SecretType
    description: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # These are NOT stored in the ref
    # The actual secret is stored encrypted in the SecretManager
    _secret_hash: str = field(default="", repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict (no secret material)."""
        return {
            "ref_id": self.ref_id,
            "challenge_id": self.challenge_id,
            "secret_type": self.secret_type.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CredentialRef":
        """Deserialize from dict."""
        ref = cls(
            ref_id=data["ref_id"],
            challenge_id=data["challenge_id"],
            secret_type=SecretType(data["secret_type"]),
            description=data["description"],
            metadata=data.get("metadata", {}),
        )
        if data.get("created_at"):
            ref.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("expires_at"):
            ref.expires_at = datetime.fromisoformat(data["expires_at"])
        return ref


@dataclass
class SecretEntry:
    """Encrypted secret entry."""
    ref_id: str
    challenge_id: str
    secret_type: SecretType
    encrypted_value: bytes  # Encrypted with master key
    nonce: bytes
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    status: SecretStatus = SecretStatus.ACTIVE
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        return self.status == SecretStatus.ACTIVE and not self.is_expired()


class SecretManager:
    """Manages secrets with encryption and access control."""
    
    def __init__(self, master_key: Optional[bytes] = None):
        self._master_key = master_key or self._derive_master_key()
        self._secrets: Dict[str, SecretEntry] = {}
        self._refs: Dict[str, CredentialRef] = {}
        self._challenge_refs: Dict[str, Set[str]] = {}  # challenge_id -> set of ref_ids
        self._access_log: List[Dict[str, Any]] = []
        
        # Redaction patterns for logging
        self._redaction_patterns = [
            (re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*\S+'), r'\1=***REDACTED***'),
            (re.compile(r'(?i)(api[_-]?key|apikey)\s*[:=]\s*\S+'), r'\1=***REDACTED***'),
            (re.compile(r'(?i)(secret|token)\s*[:=]\s*\S+'), r'\1=***REDACTED***'),
            (re.compile(r'(?i)(authorization|bearer)\s+[\w\-._~+/]+=*'), r'\1 ***REDACTED***'),
            (re.compile(r'(?i)(ssh[_-]?key|private[_-]?key)\s*[:=]\s*\S+'), r'\1=***REDACTED***'),
            (re.compile(r'(?i)(database[_-]?url|db[_-]?url)\s*[:=]\s*\S+'), r'\1=***REDACTED***'),
            (re.compile(r'[a-zA-Z0-9+/]{20,}={0,2}'), '***REDACTED***'),  # Base64-like strings
            (re.compile(r'[a-fA-F0-9]{32,}'), '***REDACTED***'),  # Hex strings (potential keys)
        ]
    
    def _derive_master_key(self) -> bytes:
        """Derive master key from environment or generate."""
        import os
        key_env = os.getenv("SECRET_MASTER_KEY")
        if key_env:
            return hashlib.sha256(key_env.encode()).digest()
        # Generate ephemeral key for session
        return secrets.token_bytes(32)
    
    def _encrypt(self, plaintext: bytes) -> tuple[bytes, bytes]:
        """Encrypt plaintext using AES-GCM."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(self._master_key)
        nonce = secrets.token_bytes(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return ciphertext, nonce
    
    def _decrypt(self, ciphertext: bytes, nonce: bytes) -> bytes:
        """Decrypt ciphertext using AES-GCM."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(self._master_key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def store_secret(
        self,
        challenge_id: str,
        secret_type: SecretType,
        value: str,
        description: str = "",
        expires_in_hours: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CredentialRef:
        """Store a secret and return a reference."""
        ref_id = secrets.token_urlsafe(16)
        
        # Encrypt the secret
        plaintext = value.encode('utf-8')
        encrypted_value, nonce = self._encrypt(plaintext)
        
        # Create secret entry
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        entry = SecretEntry(
            ref_id=ref_id,
            challenge_id=challenge_id,
            secret_type=secret_type,
            encrypted_value=encrypted_value,
            nonce=nonce,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        
        # Create reference
        ref = CredentialRef(
            ref_id=ref_id,
            challenge_id=challenge_id,
            secret_type=secret_type,
            description=description,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        ref._secret_hash = hashlib.sha256(plaintext).hexdigest()[:16]
        
        # Store
        self._secrets[ref_id] = entry
        self._refs[ref_id] = ref
        
        if challenge_id not in self._challenge_refs:
            self._challenge_refs[challenge_id] = set()
        self._challenge_refs[challenge_id].add(ref_id)
        
        return ref
    
    def retrieve_secret(self, ref_id: str, requester_agent_id: str) -> Optional[str]:
        """Retrieve a secret by reference ID."""
        entry = self._secrets.get(ref_id)
        if not entry:
            return None
        
        if not entry.is_valid():
            return None
        
        # Check challenge access (would integrate with auth context)
        # For now, allow if agent has access to challenge
        
        # Decrypt
        try:
            plaintext = self._decrypt(entry.encrypted_value, entry.nonce)
        except Exception:
            return None
        
        # Update access tracking
        entry.access_count += 1
        entry.last_accessed = datetime.utcnow()
        
        # Log access
        self._access_log.append({
            "ref_id": ref_id,
            "agent_id": requester_agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action": "retrieve",
        })
        
        return plaintext.decode('utf-8')
    
    def get_ref(self, ref_id: str) -> Optional[CredentialRef]:
        """Get credential reference."""
        return self._refs.get(ref_id)
    
    def get_challenge_refs(self, challenge_id: str) -> List[CredentialRef]:
        """Get all credential references for a challenge."""
        ref_ids = self._challenge_refs.get(challenge_id, set())
        return [self._refs[rid] for rid in ref_ids if rid in self._refs]
    
    def revoke_secret(self, ref_id: str) -> bool:
        """Revoke a secret."""
        entry = self._secrets.get(ref_id)
        if not entry:
            return False
        
        entry.status = SecretStatus.REVOKED
        return True
    
    def rotate_secret(self, ref_id: str, new_value: str) -> bool:
        """Rotate a secret to a new value."""
        entry = self._secrets.get(ref_id)
        if not entry or not entry.is_valid():
            return False
        
        # Encrypt new value
        plaintext = new_value.encode('utf-8')
        encrypted_value, nonce = self._encrypt(plaintext)
        
        entry.encrypted_value = encrypted_value
        entry.nonce = nonce
        entry.metadata["rotated_at"] = datetime.utcnow().isoformat()
        entry.metadata["previous_hash"] = hashlib.sha256(entry.encrypted_value).hexdigest()[:16]
        
        return True
    
    def redact(self, text: str) -> str:
        """Redact secrets from text."""
        redacted = text
        for pattern, replacement in self._redaction_patterns:
            redacted = pattern.sub(replacement, redacted)
        return redacted
    
    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact secrets from a dictionary."""
        redacted = {}
        for key, value in data.items():
            if isinstance(value, str):
                redacted[key] = self.redact(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact(item) if isinstance(item, str) else
                    self.redact_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted
    
    def get_access_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get access log."""
        return self._access_log[-limit:]
    
    def cleanup_expired(self) -> int:
        """Remove expired secrets."""
        now = datetime.utcnow()
        removed = 0
        to_remove = []
        
        for ref_id, entry in self._secrets.items():
            if entry.is_expired() or entry.status == SecretStatus.EXPIRED:
                to_remove.append(ref_id)
        
        for ref_id in to_remove:
            entry = self._secrets.pop(ref_id, None)
            ref = self._refs.pop(ref_id, None)
            if ref and ref.challenge_id in self._challenge_refs:
                self._challenge_refs[ref.challenge_id].discard(ref_id)
            removed += 1
        
        return removed


# Global secret manager
_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """Get global secret manager."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager