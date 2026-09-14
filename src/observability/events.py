"""Event logging"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from .logger import get_logger

_logger = get_logger("events")
_audit_logger = get_logger("audit")


async def log_agent_event(
    agent_id: str,
    event: str,
    data: Dict[str, Any],
    level: str = "info",
):
    """Log an agent event."""
    log_data = {
        "agent_id": agent_id,
        "event": event,
        "timestamp": datetime.utcnow().isoformat(),
        **data,
    }
    getattr(_logger, level)(log_data)


async def log_command_execution(
    agent_id: str,
    tool: str,
    arguments: Dict[str, Any],
    result: Any,
    level: str = "info",
):
    """Log a command execution."""
    log_data = {
        "agent_id": agent_id,
        "tool": tool,
        "arguments": arguments,
        "success": getattr(result, "success", False),
        "exit_code": getattr(result, "exit_code", None),
        "execution_time": getattr(result, "execution_time", None),
        "timestamp": datetime.utcnow().isoformat(),
    }
    getattr(_logger, level)(log_data)


async def log_evidence_verification(
    claim_id: str,
    agent_id: str,
    status: str,
    confidence: float,
    level: str = "info",
):
    """Log evidence verification."""
    log_data = {
        "claim_id": claim_id,
        "agent_id": agent_id,
        "status": status,
        "confidence": confidence,
        "timestamp": datetime.utcnow().isoformat(),
    }
    getattr(_logger, level)(log_data)


async def log_artifact_event(
    artifact_id: str,
    event: str,
    data: Dict[str, Any],
    level: str = "info",
):
    """Log an artifact event."""
    log_data = {
        "artifact_id": artifact_id,
        "event": event,
        "timestamp": datetime.utcnow().isoformat(),
        **data,
    }
    getattr(_logger, level)(log_data)


async def log_permission_event(
    request_id: str,
    event: str,
    data: Dict[str, Any],
    level: str = "info",
):
    """Log a permission event."""
    log_data = {
        "request_id": request_id,
        "event": event,
        "timestamp": datetime.utcnow().isoformat(),
        **data,
    }
    getattr(_audit_logger, level)(log_data)


async def log_audit(
    agent_id: str,
    action: str,
    target: str,
    reason: str,
    result: str,
    risk_level: str,
    artifacts: Optional[list] = None,
):
    """Log an audit entry."""
    log_data = {
        "agent_id": agent_id,
        "action": action,
        "target": target,
        "reason": reason,
        "result": result,
        "risk_level": risk_level,
        "artifacts": artifacts or [],
        "timestamp": datetime.utcnow().isoformat(),
    }
    _audit_logger.info(log_data)