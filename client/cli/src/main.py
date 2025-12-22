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

SERVER_URL = os.getenv("NEBULA_SERVER_URL")

# Import commands
from .commands.upload import upload_file
from .commands.list import list_files
from .commands.download import download_file
from .commands.status import show_system_health
from .commands.play import play_file

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
    player: Optional[str] = typer.Option(None, "--player", "-p", help="Media player to use (vlc, mpv)")
):
    """
    Stream a video file to VLC or mpv.

    Automatically detects available media player. Supports seeking.
    """
    play_file(file_id, player=player)

# Adding a callback ensures the 'Commands' section is generated
@app.callback()
def main():
    """
    Nebula CLI: Manage your private cloud across machines.
    """
    pass

if __name__ == "__main__":
    app()