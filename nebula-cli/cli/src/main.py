import os
import typer
import requests
from typing import Optional
from dotenv import load_dotenv
from rich.console import Console

# Load the .env from the cli folder
load_dotenv()

# Creating the main Typer instance
app = typer.Typer(help="Nebula Cloud CLI", no_args_is_help=True)
console = Console()

SERVER_URL = os.getenv("NEBULA_SERVER_URL")

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

# Adding a callback ensures the 'Commands' section is generated
@app.callback()
def main():
    """
    Nebula CLI: Manage your private cloud across machines.
    """
    pass

if __name__ == "__main__":
    app()