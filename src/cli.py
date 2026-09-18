"""CLI - Typer-based local command interface"""
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Optional, List
import typer

from ..core.orchestrator import Orchestrator
from ..core.db import init_db
from ..core.models import ChallengeCategory, ChallengeType, AgentRole
from ..web.automation import CTFAutonomousAgent, CTFCredentials, PLATFORMS


app = typer.Typer(
    name="ctf",
    help="Autonomous CTF Solver - Local-first",
    add_completion=False,
)

# Global orchestrator instance
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator(db_path: str = "ctf.db") -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(db_path)
    return _orchestrator


@app.callback()
def main(
    db: str = typer.Option("ctf.db", "--db", "-d", help="SQLite database path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Autonomous CTF Solver - Local-first"""
    pass


# --- Challenge Commands ---

@app.command("challenge")
def challenge_cmd():
    """Challenge management"""
    pass


@challenge_cmd.command("add")
def challenge_add(
    name: str = typer.Argument(..., help="Challenge name"),
    description: str = typer.Option("", "--desc", "-d", help="Challenge description"),
    category: List[str] = typer.Option([], "--cat", "-c", help="Categories (web,crypto,pwn,reverse,forensics,osint,stego,mobile,malware,cloud,network,supply_chain,ad,web3,ai_security,sidechannel,firmware,social,programming,meta)"),
    challenge_type: str = typer.Option("jeopardy", "--type", "-t", help="Type: jeopardy|machine|attack_defense"),
    flag_format: str = typer.Option("flag{.*}", "--flag-format", help="Flag regex format"),
    target: List[str] = typer.Option([], "--target", help="Target IPs/hosts"),
    dir: Optional[Path] = typer.Option(None, "--dir", help="Import challenge from directory"),
    file: Optional[Path] = typer.Option(None, "--file", help="Import challenge from archive"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
):
    """Add a new challenge"""
    orch = get_orchestrator(db)
    
    if dir:
        import asyncio
        from ..artifacts import get_artifact_manager
        artifact_mgr = asyncio.run(get_artifact_manager())
        artifact_ids = []
        for f in dir.rglob("*"):
            if f.is_file():
                aid = asyncio.run(artifact_mgr.store_file(f, source=str(dir)))
                artifact_ids.append(aid)
        
        challenge = asyncio.run(orch.add_challenge(
            name=name or dir.name,
            description=description or f"Imported from {dir}",
            files=artifact_ids,
            target_info={"targets": target} if target else {},
            challenge_type=ChallengeType(challenge_type),
            flag_format=flag_format,
        ))
    elif file:
        import asyncio
        from ..artifacts import get_artifact_manager
        artifact_mgr = asyncio.run(get_artifact_manager())
        aid = asyncio.run(artifact_mgr.store_file(file))
        
        challenge = asyncio.run(orch.add_challenge(
            name=name or file.stem,
            description=description or f"Imported from {file.name}",
            files=[aid],
            target_info={"targets": target} if target else {},
            challenge_type=ChallengeType(challenge_type),
            flag_format=flag_format,
        ))
    else:
        cats = [ChallengeCategory(c) for c in category] if category else []
        challenge = asyncio.run(orch.add_challenge(
            name=name,
            description=description,
            target_info={"targets": target} if target else {},
            challenge_type=ChallengeType(challenge_type),
            flag_format=flag_format,
        ))
        challenge.category = cats
        orch.session.commit()
    
    typer.echo(f"✓ Challenge created: {challenge.id} ({challenge.name})")
    if target:
        typer.echo(f"  Targets: {', '.join(target)}")


@challenge_cmd.command("list")
def challenge_list(
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List all challenges"""
    orch = get_orchestrator(db)
    challenges = orch.list_challenges()
    
    if json_output:
        typer.echo(json.dumps([
            {"id": c.id, "name": c.name, "categories": [cat.value for cat in c.category], "type": c.challenge_type.value}
            for c in challenges
        ], indent=2))
    else:
        if not challenges:
            typer.echo("No challenges found")
            return
        for c in challenges:
            cats = ", ".join(cat.value for cat in c.category)
            typer.echo(f"  {c.id[:8]}  {c.name:30}  [{cats}]  ({c.challenge_type.value})")


@challenge_cmd.command("inspect")
def challenge_inspect(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Inspect challenge details"""
    orch = get_orchestrator(db)
    challenge = orch.get_challenge(challenge_id)
    if not challenge:
        typer.echo(f"Challenge {challenge_id} not found", err=True)
        raise typer.Exit(1)
    
    if json_output:
        typer.echo(json.dumps({
            "id": challenge.id,
            "name": challenge.name,
            "description": challenge.description,
            "categories": [cat.value for cat in challenge.category],
            "type": challenge.challenge_type.value,
            "flag_format": challenge.flag_format,
            "target_info": challenge.target_info,
            "target_scope": challenge.target_scope,
            "discovery_scope": challenge.discovery_scope,
        }, indent=2))
    else:
        typer.echo(f"ID:          {challenge.id}")
        typer.echo(f"Name:        {challenge.name}")
        typer.echo(f"Description: {challenge.description}")
        typer.echo(f"Categories:  {', '.join(cat.value for cat in challenge.category)}")
        typer.echo(f"Type:        {challenge.challenge_type.value}")
        typer.echo(f"Flag Format: {challenge.flag_format}")
        typer.echo(f"Targets:     {challenge.target_info.get('targets', 'none')}")
        typer.echo(f"Target Scope: {challenge.target_scope}")
        typer.echo(f"Discovery Scope: {challenge.discovery_scope}")


@challenge_cmd.command("delete")
def challenge_delete(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    force: bool = typer.Option(False, "--force", "-f", help="Force delete without confirmation"),
):
    """Delete a challenge"""
    if not force:
        typer.confirm(f"Delete challenge {challenge_id}?", abort=True)
    
    orch = get_orchestrator(db)
    challenge = orch.get_challenge(challenge_id)
    if not challenge:
        typer.echo(f"Challenge {challenge_id} not found", err=True)
        raise typer.Exit(1)
    
    orch.session.delete(challenge)
    orch.session.commit()
    typer.echo(f"✓ Deleted challenge {challenge_id}")


# --- Solve Commands ---

@app.command("solve")
def solve(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    timeout: int = typer.Option(3600, "--timeout", help="Max solve time (seconds)"),
    parallel: int = typer.Option(4, "--parallel", help="Max parallel agents"),
):
    """Solve a challenge autonomously"""
    orch = get_orchestrator(db)
    
    typer.echo(f"🔍 Solving challenge {challenge_id}...")
    typer.echo(f"   Timeout: {timeout}s, Parallel: {parallel}")
    
    try:
        import asyncio
        result = asyncio.run(orch.solve(challenge_id))
        
        if result.success:
            typer.echo(f"✅ SOLVED! Flag: {result.flag}")
            typer.echo(f"   Method: {result.method}")
            typer.echo(f"   Duration: {result.duration_seconds:.1f}s")
            typer.echo(f"   Agents: {len(result.agents_used)}")
        else:
            typer.echo(f"❌ Failed: {result.error or 'Unknown error'}")
            typer.echo(f"   Duration: {result.duration_seconds:.1f}s")
            raise typer.Exit(1)
    except KeyboardInterrupt:
        typer.echo("\n⚠ Interrupted by user")
        raise typer.Exit(130)
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@app.command("status")
def status(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Get challenge solving status"""
    orch = get_orchestrator(db)
    status = orch.get_status(challenge_id)
    
    if json_output:
        typer.echo(json.dumps(status, indent=2))
    else:
        if "error" in status:
            typer.echo(status["error"])
            return
        c = status["challenge"]
        typer.echo(f"Challenge: {c['name']} ({c['id'][:8]})")
        typer.echo(f"Categories: {', '.join(c['categories'])}")
        typer.echo(f"State:      {status['state']}")
        typer.echo(f"Agents:     {len(status['agents'])}")
        for a in status['agents']:
            typer.echo(f"  - {a['role']}: {a['state']}")
        if status['result']:
            r = status['result']
            typer.echo(f"Result:     {'✅ Solved' if r['success'] else '❌ Failed'}")
            if r['flag']:
                typer.echo(f"Flag:       {r['flag']}")


@app.command("report")
def report(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (HTML/JSON)"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
):
    """Generate solve report"""
    orch = get_orchestrator(db)
    report = orch.generate_report(challenge_id)
    
    if output:
        if output.suffix == ".json":
            output.write_text(json.dumps(report, indent=2))
        else:
            html = f"""<html><body><h1>CTF Report: {report['challenge']['name']}</h1>
<p>Success: {report['result']['success'] if report['result'] else 'N/A'}</p>
<p>Flag: {report['result']['flag'] if report['result'] and report['result']['flag'] else 'N/A'}</p>
<h2>Findings ({len(report['findings'])})</h2>
<ul>{''.join(f'<li>{f["title"]} (conf: {f["confidence"]})</li>' for f in report['findings'])}</ul>
<h2>Evidence ({len(report['evidence'])})</h2>
<ul>{''.join(f'<li>{e["title"]} ({e["status"]})</li>' for e in report['evidence'])}</ul>
</body></html>"""
            output.write_text(html)
        typer.echo(f"✓ Report saved to {output}")
    else:
        typer.echo(json.dumps(report, indent=2))


@app.command("replay")
def replay(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    step: Optional[int] = typer.Option(None, "--step", "-s", help="Replay from step"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
):
    """Replay challenge investigation timeline"""
    orch = get_orchestrator(db)
    
    from ..core.models import ToolExecution
    tool_execs = orch.session.query(ToolExecution).filter_by(
        challenge_id=challenge_id
    ).order_by(ToolExecution.executed_at).all()
    
    typer.echo(f"Timeline for {challenge_id}:")
    for i, te in enumerate(tool_execs):
        if step and i < step:
            continue
        status = "✅" if te.success else "❌"
        typer.echo(f"  [{i}] {te.executed_at.strftime('%H:%M:%S')} {status} {te.tool_name} ({te.execution_time:.1f}s)")
        if te.stdout:
            preview = te.stdout[:100].replace('\n', ' ')
            typer.echo(f"       {preview}...")


# --- Debug Commands ---

@app.command("agents")
def agents(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List agents for a challenge"""
    orch = get_orchestrator(db)
    from ..core.models import Agent
    agents = orch.session.query(Agent).filter_by(challenge_id=challenge_id).all()
    
    if json_output:
        typer.echo(json.dumps([{
            "id": a.id, "role": a.role.value, "name": a.name,
            "state": a.state.value, "depth": a.depth,
            "findings": len(a.findings), "tools": len(a.tool_executions)
        } for a in agents], indent=2))
    else:
        for a in agents:
            typer.echo(f"  {a.id[:8]}  {a.role.value:15}  {a.name:30}  {a.state.value:12}  depth={a.depth}")


@app.command("findings")
def findings(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List findings for a challenge"""
    orch = get_orchestrator(db)
    from ..core.models import Finding
    query = orch.session.query(Finding).filter_by(challenge_id=challenge_id)
    if type:
        query = query.filter_by(type=type)
    findings = query.all()
    
    if json_output:
        typer.echo(json.dumps([{
            "id": f.id, "type": f.type, "title": f.title,
            "confidence": f.confidence, "agent_id": f.agent_id
        } for f in findings], indent=2))
    else:
        for f in findings:
            typer.echo(f"  [{f.type}] {f.title} (conf: {f.confidence:.2f})")


@app.command("hypotheses")
def hypotheses(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List hypotheses for a challenge"""
    orch = get_orchestrator(db)
    from ..core.models import Hypothesis, HypothesisStatus
    query = orch.session.query(Hypothesis).filter_by(challenge_id=challenge_id)
    if status:
        query = query.filter_by(status=HypothesisStatus(status))
    hyps = query.all()
    
    if json_output:
        typer.echo(json.dumps([{
            "id": h.id, "description": h.description,
            "confidence": h.confidence, "status": h.status.value,
            "supporting": len(h.supporting_evidence)
        } for h in hyps], indent=2))
    else:
        for h in hyps:
            typer.echo(f"  [{h.status.value}] {h.description[:80]} (conf: {h.confidence:.2f})")


@app.command("experiments")
def experiments(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List experiments for a challenge"""
    orch = get_orchestrator(db)
    from ..core.models import Experiment
    exps = orch.session.query(Experiment).filter_by(challenge_id=challenge_id).all()
    
    if json_output:
        typer.echo(json.dumps([{
            "id": e.id, "hypothesis_id": e.hypothesis_id,
            "tool": e.tool_name, "status": e.status,
            "duration": e.duration_seconds
        } for e in exps], indent=2))
    else:
        for e in exps:
            typer.echo(f"  {e.name} [{e.status}] tool={e.tool_name} ({e.duration_seconds:.1f}s)")


@app.command("evidence")
def evidence(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List verified evidence for a challenge"""
    orch = get_orchestrator(db)
    from ..core.models import Evidence
    ev = orch.session.query(Evidence).filter_by(challenge_id=challenge_id).all()
    
    if json_output:
        typer.echo(json.dumps([{
            "id": e.id, "type": e.type, "title": e.title,
            "status": e.status.value, "confidence": e.confidence
        } for e in ev], indent=2))
    else:
        for e in ev:
            typer.echo(f"  [{e.status.value}] {e.title} (conf: {e.confidence:.2f})")


@app.command("artifacts")
def artifacts(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List artifacts for a challenge"""
    orch = get_orchestrator(db)
    from ..core.models import Artifact
    arts = orch.session.query(Artifact).filter_by(challenge_id=challenge_id).all()
    
    if json_output:
        typer.echo(json.dumps([{
            "id": a.id, "filename": a.filename,
            "mime": a.mime_type, "size": a.size, "sha256": a.sha256[:16]
        } for a in arts], indent=2))
    else:
        for a in arts:
            typer.echo(f"  {a.filename} ({a.mime_type}, {a.size} bytes, {a.sha256[:16]}...)")


@app.command("logs")
def logs(
    challenge_id: str = typer.Argument(..., help="Challenge ID"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max entries"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Show audit log for a challenge"""
    orch = get_orchestrator(db)
    from ..core.models import AuditEvent, Agent
    entries = orch.session.query(AuditEvent).filter(
        AuditEvent.agent_id.in_(
            orch.session.query(Agent.id).filter_by(challenge_id=challenge_id)
        )
    ).order_by(AuditEvent.timestamp.desc()).limit(limit).all()
    
    if json_output:
        typer.echo(json.dumps([{
            "timestamp": e.timestamp.isoformat(),
            "agent": e.agent_id[:8],
            "action": e.action,
            "target": e.target,
            "result": e.result,
            "risk": e.risk_level
        } for e in entries], indent=2))
    else:
        for e in entries:
            typer.echo(f"  {e.timestamp.strftime('%H:%M:%S')} {e.agent_id[:8]} {e.action} {e.target} → {e.result} ({e.risk_level})")


# --- Web Autonomous Agent Commands ---

@app.command("web")
def web_cmd():
    """Web autonomous CTF agent commands"""
    pass


@web_cmd.command("login")
def web_login(
    platform: str = typer.Argument(..., help="Platform: ctfd|rctf|ctfhub"),
    url: str = typer.Argument(..., help="Base URL of CTF platform"),
    username: str = typer.Option(..., "--user", "-u", help="Username"),
    password: str = typer.Option(..., "--pass", "-p", help="Password"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser headless"),
):
    """Test login to CTF platform"""
    from ..web.automation import WebAutomation, CTFPlatform, CTFCredentials, PLATFORMS
    
    platform_config = PLATFORMS.get(platform.lower())
    if not platform_config:
        typer.echo(f"Unknown platform: {platform}. Supported: {list(PLATFORMS.keys())}", err=True)
        raise typer.Exit(1)
    
    platform_config.base_url = url.rstrip("/")
    platform_config.login_url = urljoin(platform_config.base_url, platform_config.login_url)
    
    credentials = CTFCredentials(
        platform=platform,
        username=username,
        password=password,
    )
    
    async def _login():
        web = WebAutomation(headless=headless)
        await web.initialize()
        try:
            success = await web.login(platform_config, credentials)
            if success:
                typer.echo(f"✅ Login successful to {platform}")
            else:
                typer.echo(f"❌ Login failed to {platform}")
                raise typer.Exit(1)
        finally:
            await web.close()
    
    asyncio.run(_login())


@web_cmd.command("discover")
def web_discover(
    platform: str = typer.Argument(..., help="Platform: ctfd|rctf|ctfhub"),
    url: str = typer.Argument(..., help="Base URL of CTF platform"),
    username: str = typer.Option(..., "--user", "-u", help="Username"),
    password: str = typer.Option(..., "--pass", "-p", help="Password"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser headless"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Discover challenges on CTF platform"""
    from ..web.automation import WebAutomation, CTFPlatform, CTFCredentials, PLATFORMS
    
    platform_config = PLATFORMS.get(platform.lower())
    if not platform_config:
        typer.echo(f"Unknown platform: {platform}. Supported: {list(PLATFORMS.keys())}", err=True)
        raise typer.Exit(1)
    
    platform_config.base_url = url.rstrip("/")
    platform_config.challenges_url = urljoin(platform_config.base_url, platform_config.challenges_url)
    
    credentials = CTFCredentials(
        platform=platform,
        username=username,
        password=password,
    )
    
    async def _discover():
        web = WebAutomation(headless=headless)
        await web.initialize()
        try:
            await web.login(platform_config, credentials)
            challenges = await web.discover_challenges(platform_config)
            
            if json_output:
                typer.echo(json.dumps([{
                    "name": c.name,
                    "url": c.url,
                    "category": c.category.value if c.category else None,
                    "points": c.points,
                    "solves": c.solves,
                    "difficulty": c.difficulty,
                } for c in challenges], indent=2))
            else:
                typer.echo(f"Discovered {len(challenges)} challenges on {platform}:")
                for c in challenges:
                    cat = c.category.value if c.category else "unknown"
                    typer.echo(f"  {c.name} [{cat}] pts={c.points} solves={c.solves} diff={c.difficulty}")
        finally:
            await web.close()
    
    asyncio.run(_discover())


@web_cmd.command("autonomous")
def web_autonomous(
    platform: str = typer.Argument(..., help="Platform: ctfd|rctf|ctfhub"),
    url: str = typer.Argument(..., help="Base URL of CTF platform"),
    username: str = typer.Option(..., "--user", "-u", help="Username"),
    password: str = typer.Option(..., "--pass", "-p", help="Password"),
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser headless"),
    interval: int = typer.Option(60, "--interval", "-i", help="Check interval (seconds)"),
):
    """Run fully autonomous CTF solver on platform"""
    from ..web.automation import CTFAutonomousAgent, CTFCredentials, PLATFORMS
    
    platform_config = PLATFORMS.get(platform.lower())
    if not platform_config:
        typer.echo(f"Unknown platform: {platform}. Supported: {list(PLATFORMS.keys())}", err=True)
        raise typer.Exit(1)
    
    platform_config.base_url = url.rstrip("/")
    platform_config.login_url = urljoin(platform_config.base_url, platform_config.login_url)
    platform_config.challenges_url = urljoin(platform_config.base_url, platform_config.challenges_url)
    
    credentials = CTFCredentials(
        platform=platform,
        username=username,
        password=password,
    )
    
    orch = get_orchestrator(db)
    
    agent = CTFAutonomousAgent(
        platform_name=platform,
        base_url=url,
        credentials=credentials,
        orchestrator=orch,
        headless=headless,
    )
    
    typer.echo(f"🤖 Starting autonomous agent on {platform} ({url})")
    typer.echo(f"   Check interval: {interval}s")
    typer.echo("   Press Ctrl+C to stop")
    
    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        typer.echo("\n🛑 Stopping agent...")
        asyncio.run(agent.stop())
        typer.echo("Agent stopped.")


# --- Benchmark & Security Commands ---

@app.command("benchmark")
def benchmark(
    suite: str = typer.Option("web", "--suite", "-s", help="Suite: web|crypto|pwn|reverse|forensics|all"),
    parallel: int = typer.Option(2, "--parallel", "-p", help="Parallel challenges"),
    db: str = typer.Option("benchmark.db", "--db", help="Benchmark database"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Results output file"),
):
    """Run benchmark suite"""
    typer.echo(f"🏃 Running benchmark suite: {suite}")
    typer.echo(f"   Parallel: {parallel}, DB: {db}")
    
    typer.echo("Benchmark structure:")
    typer.echo("  1. Load challenges from examples/challenges/")
    typer.echo("  2. Run each challenge with orchestrator.solve()")
    typer.echo("  3. Collect metrics: solve_rate, time, tokens, tools, agents")
    typer.echo("  4. Output results")
    
    if output:
        typer.echo(f"  Results → {output}")


@app.command("security-audit")
def security_audit(
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Run self-attack security audit"""
    typer.echo("🔒 Running security self-audit...")
    
    checks = [
        ("Scope bypass", "Attempt to access out-of-scope targets"),
        ("Role spoofing", "Attempt to escalate agent role"),
        ("Identity spoofing", "Attempt to forge agent identity"),
        ("Tool injection", "Attempt to execute unauthorized tools"),
        ("Path traversal", "Attempt to escape workspace"),
        ("Credential leakage", "Check for secrets in logs/artifacts"),
        ("Prompt injection", "Test artifact content injection"),
        ("Shell escape", "Test python sandbox escape"),
        ("Docker access", "Test Docker socket access"),
        ("SSRF", "Test internal service access"),
        ("Resource exhaustion", "Test budget limits"),
        ("Recursion explosion", "Test agent depth limits"),
        ("Evidence forgery", "Test flag/evidence tampering"),
    ]
    
    results = []
    for name, desc in checks:
        typer.echo(f"  🔍 {name}: {desc}")
        results.append({"check": name, "status": "not_implemented", "details": desc})
    
    if output:
        output.write_text(json.dumps(results, indent=2))
        typer.echo(f"✓ Results saved to {output}")


# --- Utility Commands ---

@app.command("init")
def init_db_cmd(
    db: str = typer.Option("ctf.db", "--db", help="Database path"),
):
    """Initialize database"""
    engine, _ = init_db(db)
    typer.echo(f"✓ Database initialized: {db}")


@app.command("version")
def version():
    """Show version"""
    typer.echo("ctf-autonomous 0.2.0 (local-first)")


if __name__ == "__main__":
    app()