"""Orchestrator FastAPI Application"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from ..orchestrator import get_orchestrator
from ..orchestrator.models import Challenge, ChallengeType, SolveResult
from ..runtime import get_agent_runtime
from ..config.settings import get_settings


class ChallengeCreateRequest(BaseModel):
    name: str
    description: str
    files: List[str] = []
    target_info: Dict[str, Any] = {}
    credentials: Dict[str, str] = {}
    constraints: List[str] = []
    flag_format: str = "flag{.*}"
    challenge_type: ChallengeType = ChallengeType.JEOPARDY


class ChallengeResponse(BaseModel):
    id: str
    name: str
    categories: List[str]
    type: str


class SolveRequest(BaseModel):
    challenge_id: str


class SolveResponse(BaseModel):
    challenge_id: str
    success: bool
    flag: Optional[str] = None
    method: str = ""
    duration_seconds: float = 0.0
    error: Optional[str] = None


def create_app() -> FastAPI:
    """Create FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Autonomous CTF Orchestrator",
        version=settings.system_version,
    )

    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": settings.system_version}

    @app.post("/challenges", response_model=ChallengeResponse)
    async def create_challenge(request: ChallengeCreateRequest):
        orchestrator = await get_orchestrator()
        challenge = await orchestrator.add_challenge(
            name=request.name,
            description=request.description,
            files=request.files,
            target_info=request.target_info,
            credentials=request.credentials,
            constraints=request.constraints,
            flag_format=request.flag_format,
            challenge_type=request.challenge_type,
        )
        return ChallengeResponse(
            id=challenge.id,
            name=challenge.name,
            categories=[c.value for c in challenge.category],
            type=challenge.challenge_type.value,
        )

    @app.get("/challenges", response_model=List[ChallengeResponse])
    async def list_challenges():
        orchestrator = await get_orchestrator()
        challenges = await orchestrator.list_challenges()
        return [
            ChallengeResponse(
                id=c["id"],
                name=c["name"],
                categories=c["categories"],
                type=c["type"],
            )
            for c in challenges
        ]

    @app.get("/challenges/{challenge_id}")
    async def get_challenge(challenge_id: str):
        orchestrator = await get_orchestrator()
        status = await orchestrator.get_challenge_status(challenge_id)
        if "error" in status:
            raise HTTPException(status_code=404, detail="Challenge not found")
        return status

    @app.post("/challenges/{challenge_id}/solve", response_model=SolveResponse)
    async def solve_challenge(challenge_id: str):
        orchestrator = await get_orchestrator()
        try:
            result = await orchestrator.solve_challenge(challenge_id)
            return SolveResponse(
                challenge_id=result.challenge_id,
                success=result.success,
                flag=result.flag,
                method=result.method,
                duration_seconds=result.duration_seconds,
                error=result.error,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/challenges/{challenge_id}/agents")
    async def get_challenge_agents(challenge_id: str):
        orchestrator = await get_orchestrator()
        status = await orchestrator.get_challenge_status(challenge_id)
        return status.get("agents", [])

    @app.get("/challenges/{challenge_id}/findings")
    async def get_challenge_findings(challenge_id: str):
        orchestrator = await get_orchestrator()
        # Would query memory for findings
        return {"findings": []}

    @app.get("/challenges/{challenge_id}/artifacts")
    async def get_challenge_artifacts(challenge_id: str):
        orchestrator = await get_orchestrator()
        # Would query artifact manager
        return {"artifacts": []}

    @app.get("/challenges/{challenge_id}/report")
    async def get_challenge_report(challenge_id: str):
        orchestrator = await get_orchestrator()
        return await orchestrator.generate_report(challenge_id)

    @app.post("/agents/{agent_id}/cancel")
    async def cancel_agent(agent_id: str):
        runtime = await get_agent_runtime()
        await runtime.cancel_agent(agent_id)
        return {"success": True}

    @app.get("/agents")
    async def list_agents():
        runtime = await get_agent_runtime()
        return await runtime.list_active_agents()

    return app