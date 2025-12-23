import os
import sys
import typer
import requests
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

# Load the .env.client from the cli folder relative to this file
env_path = Path(__file__).parent.parent / '.env.client'
load_dotenv(env_path)

# Creating the main Typer instance
app = typer.Typer(help="Nebula Cloud CLI", no_args_is_help=True)
console = Console()


def get_server_url() -> str:
    """
    Auto-detect best server URL.
    Priority: NEBULA_SERVER_URL > NEBULA_LOCAL_URL (if reachable) > NEBULA_REMOTE_URL
    """
    # If explicit URL is set, use it
    explicit_url = os.getenv("NEBULA_SERVER_URL")
    if explicit_url:
        return explicit_url
    
    local_url = os.getenv("NEBULA_LOCAL_URL")
    remote_url = os.getenv("NEBULA_REMOTE_URL")
    
    # If only one is configured, use it
    if local_url and not remote_url:
        return local_url
    if remote_url and not local_url:
        return remote_url
    
    # If both are configured, try local first with quick timeout
    if local_url and remote_url:
        try:
            response = requests.get(f"{local_url}/health", timeout=1.5)
            if response.status_code == 200:
                console.print("[dim]🏠 Using LOCAL network (fast)[/dim]")
                return local_url
        except Exception:
            pass
        console.print("[dim]🌐 Using REMOTE/Tailscale[/dim]")
        return remote_url
    
    # Fallback
    return "http://localhost:8000"


# Get the best available server URL
SERVER_URL = get_server_url()

# Import commands
from .commands.upload import upload_file
from .commands.list import list_files
from .commands.download import download_file
from .commands.status import show_system_health
from .commands.play import play_file
from .commands.transcode import transcode_file, get_transcode_status, list_transcode_jobs, cancel_transcode_job
from .commands.system import show_logs, restart_service, show_container_status
from .commands.benchmark import run_benchmark

@app.command()
def ping():
    """Connectivity check to the remote server."""
    console.print("[yellow]📡 Contacting Nebula Server...[/yellow]")
    try:
        # Calling the health endpoint on your old laptop
        r = requests.get(f"{SERVER_URL}/health", timeout=5)
        if r.status_code == 200:
            console.print("[bold green]🏓 PONG![/bold green] Server is alive.")
        else:
            console.print(f"[yellow]⚠️ Server responded with status: {r.status_code}[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Connection Failed:[/bold red] {e}")

@app.command()
def upload(
    file_path: str = typer.Argument(..., help="Path to the file to upload"),
    description: Optional[str] = typer.Option(None, help="Optional description for the file")
):
    """
    Upload a file to Nebula Cloud
    """
    upload_file(file_path, description=description)

@app.command()
def list(
    limit: int = typer.Option(50, help="Maximum number of files to display"),
    skip: int = typer.Option(0, help="Number of files to skip")
):
    """
    List all uploaded files with metadata
    """
    list_files(limit=limit, skip=skip)

@app.command()
def download(
    file_id: int = typer.Argument(..., help="ID of the file to download"),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path (defaults to original filename)")
):
    """
    Download a file from Nebula Cloud by its ID.

    Preserves original filename if no output path is specified.
    """
    download_file(file_id, output_path)

@app.command()
def status(
    show_local: bool = typer.Option(True, help="Show local system specifications"),
    show_server: bool = typer.Option(True, help="Show server health status")
):
    """
    Display detailed system health and specifications.

    Shows CPU, memory, disk usage, network stats, and server health.
    """
    show_system_health(show_local=show_local, show_server=show_server)

@app.command()
def play(
    file_id: int = typer.Argument(..., help="ID of the video file to play"),
    player: Optional[str] = typer.Option(None, "--player", "-p", help="Media player to use (vlc, mpv)"),
    quality: Optional[int] = typer.Option(None, "--quality", "-q", help="Stream quality (480, 720, 1080). Uses transcoded version if available.")
):
    """
    Stream a video file to VLC or mpv.

    Supports seeking. Use --quality to stream a transcoded version.
    """
    play_file(file_id, player=player, quality=quality)


@app.command()
def transcode(
    file_id: int = typer.Argument(..., help="ID of the video file to transcode"),
    qualities: Optional[str] = typer.Option("480,720", "--qualities", "-q", help="Comma-separated list of target qualities (480, 720, 1080)")
):
    """
    Transcode a video to multiple quality levels.

    Creates 480p and 720p versions by default. Runs in background.
    """
    quality_list = [int(q.strip()) for q in qualities.split(",")]
    transcode_file(file_id, qualities=quality_list)


@app.command("transcode-status")
def transcode_status(
    file_id: int = typer.Argument(..., help="ID of the file to check"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Continuously watch for updates")
):
    """
    Check transcoding status for a file.

    Shows progress of all transcoding jobs for the file.
    """
    get_transcode_status(file_id, watch=watch)


@app.command("transcode-jobs")
def transcode_jobs(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status: pending, processing, completed, failed"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of jobs to display")
):
    """
    List all transcoding jobs.

    Shows recent transcoding jobs across all files.
    """
    list_transcode_jobs(status=status, limit=limit)


@app.command("transcode-cancel")
def transcode_cancel(
    job_id: int = typer.Argument(..., help="ID of the transcoding job to cancel")
):
    """
    Cancel a pending or processing transcoding job.
    """
    cancel_transcode_job(job_id)


@app.command()
def logs(
    service: Optional[str] = typer.Argument(None, help="Service name: api, worker, db, s3, queue (omit for all)"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of log lines to fetch")
):
    """
    View server logs.

    Shows logs from Docker containers. Specify a service or omit for all.
    """
    show_logs(service=service, lines=lines)


@app.command()
def restart(
    service: Optional[str] = typer.Argument(None, help="Service name: api, worker, db, s3, queue (omit for all)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation for dangerous operations")
):
    """
    Restart server containers.

    Restart a specific service or all services. Use with caution.
    """
    restart_service(service=service, force=force)


@app.command()
def containers():
    """
    Show status of all server containers.

    Displays running state of api, worker, db, s3, and queue containers.
    """
    show_container_status()


@app.command()
def benchmark(
    file_path: str = typer.Argument(..., help="Path to video file to benchmark"),
    server_url: Optional[str] = typer.Option(None, "--server", "-s", help="Nebula server URL (uses NEBULA_SERVER_URL env var if not specified)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save results to JSON file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    skip_transcode: bool = typer.Option(False, "--skip-transcode", help="Skip transcoding benchmark (faster)")
):
    """
    Run comprehensive performance benchmark.

    Tests upload, download, streaming, and transcoding performance.
    Measures throughput, latency, and identifies bottlenecks.
    """
    run_benchmark(file_path=file_path, server_url=server_url, output=output, verbose=verbose, skip_transcode=skip_transcode)


# Adding a callback ensures the 'Commands' section is generated
@app.callback()
def main():
    """
    Nebula CLI: Manage your private cloud across machines.
    """
    pass

if __name__ == "__main__":
    app()