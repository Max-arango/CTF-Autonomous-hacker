"""CLI Entry Point"""
import asyncio
import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config.settings import get_settings
from .orchestrator import get_orchestrator, Orchestrator
from .orchestrator.models import Challenge, ChallengeType
from .runtime import get_agent_runtime
from .memory import get_memory_manager
from .artifacts import get_artifact_manager
from .evidence import get_evidence_engine
from .observability import setup_logging

app = typer.Typer(name="ctf", help="Autonomous CTF Environment CLI")
console = Console()


@app.callback()
def callback():
    """Autonomous CTF Environment CLI."""
    setup_logging()


@app.command()
def start():
    """Start the CTF environment (run services)."""
    console.print("[green]Starting CTF environment...[/green]")
    console.print("Use 'docker compose up -d' to start all services")
    console.print("Orchestrator will be available at http://localhost:8000")
    console.print("Permission Manager at http://localhost:8080")


@app.command()
def stop():
    """Stop the CTF environment."""
    console.print("[yellow]Stopping CTF environment...[/yellow]")
    console.print("Use 'docker compose down' to stop all services")


@app.command()
def status():
    """Show environment status."""
    console.print("[blue]CTF Environment Status[/blue]")
    console.print("Use 'docker compose ps' to see service status")


@app.command()
def challenge_add(
    path: Path = typer.Argument(..., help="Path to challenge file or directory"),
    name: Optional[str] = typer.Option(None, help="Challenge name"),
    description: Optional[str] = typer.Option(None, help="Challenge description"),
    challenge_type: ChallengeType = typer.Option(ChallengeType.JEOPARDY, help="Challenge type"),
):
    """Add a challenge."""
    async def _add():
        orchestrator = await get_orchestrator()

        challenge_name = name or path.stem
        challenge_desc = description or f"Imported from {path}"

        challenge = await orchestrator.add_challenge(
            name=challenge_name,
            description=challenge_desc,
            challenge_type=challenge_type,
        )

        # Import files
        await orchestrator.challenge_manager.import_challenge(path)

        console.print(f"[green]Added challenge:[/green] {challenge.name} ({challenge.id})")

    asyncio.run(_add())


@app.command()
def challenge_list():
    """List all challenges."""
    async def _list():
        orchestrator = await get_orchestrator()
        challenges = await orchestrator.list_challenges()

        table = Table(title="Challenges")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Categories", style="yellow")
        table.add_column("Type", style="blue")

        for c in challenges:
            table.add_row(
                c["id"][:8] + "...",
                c["name"],
                ", ".join(c["categories"]),
                c["type"],
            )

        console.print(table)

    asyncio.run(_list())


@app.command()
def challenge_inspect(challenge_id: str):
    """Inspect a challenge."""
    async def _inspect():
        orchestrator = await get_orchestrator()
        status = await orchestrator.get_challenge_status(challenge_id)

        console.print(json.dumps(status, indent=2, default=str))

    asyncio.run(_inspect())


@app.command()
def solve(challenge_id: str):
    """Solve a challenge."""
    async def _solve():
        orchestrator = await get_orchestrator()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Solving challenge {challenge_id}...", total=None)

            try:
                result = await orchestrator.solve_challenge(challenge_id)
                progress.update(task, description=f"[green]Completed![/green]")

                if result.success:
                    console.print(f"[green]SUCCESS![/green] Flag: {result.flag}")
                    console.print(f"Method: {result.method}")
                else:
                    console.print(f"[red]FAILED[/red]")
                    if result.error:
                        console.print(f"Error: {result.error}")

            except Exception as e:
                progress.update(task, description=f"[red]Failed: {e}[/red]")
                console.print(f"[red]Error: {e}[/red]")

    asyncio.run(_solve())


@app.command()
def agents(challenge_id: Optional[str] = None):
    """List active agents."""
    async def _agents():
        runtime = await get_agent_runtime()
        agents = await runtime.list_active_agents()

        table = Table(title="Active Agents")
        table.add_column("ID", style="cyan")
        table.add_column("Role", style="green")
        table.add_column("Name", style="yellow")
        table.add_column("State", style="blue")
        table.add_column("Depth", style="magenta")
        table.add_column("Findings", style="white")

        for a in agents:
            table.add_row(
                a["id"][:8] + "...",
                a["role"],
                a["name"],
                a["state"],
                str(a["depth"]),
                str(a["findings_count"]),
            )

        console.print(table)

    asyncio.run(_agents())


@app.command()
def findings(challenge_id: str):
    """Show findings for a challenge."""
    async def _findings():
        memory = await get_memory_manager()
        findings = await memory.get_findings(challenge_id=challenge_id)

        table = Table(title=f"Findings for {challenge_id}")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Title", style="yellow")
        table.add_column("Confidence", style="blue")
        table.add_column("Agent", style="magenta")

        for f in findings:
            table.add_row(
                f.id[:8] + "...",
                f.type,
                f.title[:50],
                f"{f.confidence:.2f}",
                f.agent_id[:8] + "...",
            )

        console.print(table)

    asyncio.run(_findings())


@app.command()
def experiments(challenge_id: str):
    """Show experiments for a challenge."""
    async def _experiments():
        memory = await get_memory_manager()
        # Would query experiments
        console.print("[yellow]Experiments view not yet implemented[/yellow]")

    asyncio.run(_experiments())


@app.command()
def artifacts(
    query: Optional[str] = None,
    limit: int = 20,
):
    """List or search artifacts."""
    async def _artifacts():
        artifact_manager = await get_artifact_manager()

        if query:
            results = await artifact_manager.search(query, limit=limit)
        else:
            results = await artifact_manager.list(limit=limit)

        table = Table(title="Artifacts")
        table.add_column("ID", style="cyan")
        table.add_column("Filename", style="green")
        table.add_column("Size", style="yellow")
        table.add_column("SHA256", style="blue")
        table.add_column("Creator", style="magenta")

        for a in results:
            table.add_row(
                a.id[:8] + "...",
                a.filename,
                f"{a.size} bytes",
                a.sha256[:16] + "...",
                a.creator[:8] + "..." if a.creator else "",
            )

        console.print(table)

    asyncio.run(_artifacts())


@app.command()
def logs(
    agent_id: Optional[str] = None,
    lines: int = 100,
):
    """View logs."""
    console.print("[yellow]Log viewing not yet implemented - use docker compose logs[/yellow]")


@app.command()
def report(challenge_id: str):
    """Generate challenge report."""
    async def _report():
        orchestrator = await get_orchestrator()
        report = await orchestrator.generate_report(challenge_id)

        console.print(json.dumps(report, indent=2, default=str))

    asyncio.run(_report())


if __name__ == "__main__":
    app()